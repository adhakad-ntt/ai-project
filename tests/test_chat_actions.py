import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from services import project_service
from services.chat_actions import apply_change, prepare_change
from services.chat_service import agent_reply
from services.langgraph_workflow import RequirementAnalysisWorkflow
from services.llm_service import LLMService


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(project_service, 'PROJECTS', tmp_path)
    project_service.create_project('Alpha', 'Original description')
    project_service.create_project('Beta', 'Other project')


def test_explicit_approval_scoped_and_single_use(project):
    proposal = prepare_change('alpha', 'chat-1',
        {'target': 'project_description', 'value': 'Updated description'})
    original = project_service.load_json('alpha', 'project.json', {})
    assert original['description'] == 'Original description'
    with pytest.raises(ValueError, match='fresh approval'):
        apply_change(proposal, 'alpha', 'chat-1')
    for pid, chat in [('beta', 'chat-1'), ('alpha', 'chat-2')]:
        with pytest.raises(ValueError, match='another project or conversation'):
            apply_change(proposal, pid, chat, approved=True)
    assert project_service.load_json('alpha', 'project.json', {}) == original
    apply_change(proposal, 'alpha', 'chat-1', approved=True)
    saved = project_service.load_json('alpha', 'project.json', {})
    assert saved['description'] == 'Updated description'
    assert saved['_chat_changes'][0]['before'] == 'Original description'
    with pytest.raises(ValueError, match='fresh approval'):
        apply_change(proposal, 'alpha', 'chat-1', approved=True)


def test_stale_proposal_cannot_overwrite_data(project):
    proposal = prepare_change('alpha', 'chat',
        {'target': 'project_description', 'value': 'Proposed'})
    current = project_service.load_json('alpha', 'project.json', {})
    current['description'] = 'Concurrent edit'
    project_service.save_json('alpha', 'project.json', current)
    with pytest.raises(ValueError, match='changed since this preview'):
        apply_change(proposal, 'alpha', 'chat', approved=True)
    assert project_service.load_json('alpha', 'project.json', {}) == current


def test_requirement_approval_survives_reanalysis(project):
    requirement = {'id': 'REQ-001', 'title': 'Approval', 'description': 'Manager approval required'}
    proposal = prepare_change('alpha', 'chat', {'target': 'requirement', 'value': requirement})
    assert not project_service.load_json('alpha', 'knowledge/analysis.json', {})
    apply_change(proposal, 'alpha', 'chat', approved=True)
    previous = project_service.load_json('alpha', 'knowledge/analysis.json', {})
    workflow = RequirementAnalysisWorkflow()
    result = workflow._reconcile_changes({'previous_analysis': previous, 'analysis': {
        'requirements': [dict(requirement, description='Old extracted description')],
        'gaps': [], 'assumptions': [], 'contradictions': [],
    }})['analysis']
    assert result['requirements'][0]['description'] == 'Manager approval required'
    assert result['_chat_changes'] == previous['_chat_changes']


@pytest.mark.parametrize('change', [
    {'target': '../../.env', 'value': 'bad'},
    {'target': 'requirement', 'value': {'id': 'REQ-001'}},
    {'target': 'project_description', 'value': 'New', 'approved': True},
])
def test_invalid_actions_never_write(project, change):
    before = project_service.load_json('alpha', 'project.json', {})
    with pytest.raises(ValueError):
        prepare_change('alpha', 'chat', change)
    assert project_service.load_json('alpha', 'project.json', {}) == before


def test_malformed_model_response_fails_closed(project, monkeypatch):
    monkeypatch.setattr(LLMService, 'chat_messages', lambda *args: 'I updated it!')
    with pytest.raises(ValueError, match='No changes were made'):
        agent_reply('alpha', 'Update the description', LLMService(), [], 'chat')
    assert project_service.load_json('alpha', 'project.json', {})['description'] == 'Original description'


def test_ui_reject_then_approve_each_change(project, monkeypatch):
    monkeypatch.setattr(LLMService, 'configured', lambda self: True)
    values = iter(['Rejected description', 'Approved description', 'Another proposal'])
    def respond(self, messages):
        return json.dumps({'answer': 'Proposed update', 'change': {
            'target': 'project_description', 'value': next(values)}})
    monkeypatch.setattr(LLMService, 'chat_messages', respond)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=20).run()
    app.sidebar.selectbox[0].select('Alpha (alpha)').run()
    app.chat_input[0].set_value('Update the description').run()
    assert not app.exception
    pending = app.session_state['pending_change']
    assert app.chat_input[0].disabled
    assert app.table[0].value.to_dict('records') == [{
        'Field': 'Description', 'Existing information': 'Original description',
        'Proposed change': 'Rejected description', 'Change': 'Updated',
    }]
    assert not app.code
    assert project_service.load_json('alpha', 'project.json', {})['description'] == 'Original description'
    app.button(key=f"reject_{pending['id']}").click().run()
    assert app.session_state['pending_change'] is None
    assert project_service.load_json('alpha', 'project.json', {})['description'] == 'Original description'
    app.chat_input[0].set_value('Update the description again').run()
    pending = app.session_state['pending_change']
    app.button(key=f"approve_{pending['id']}").click().run()
    assert not app.exception
    assert app.session_state['pending_change'] is None
    assert project_service.load_json('alpha', 'project.json', {})['description'] == 'Approved description'
    app.chat_input[0].set_value('Update it once more').run()
    assert app.session_state['pending_change'] is not None
    assert project_service.load_json('alpha', 'project.json', {})['description'] == 'Approved description'
    app.sidebar.selectbox[0].select('Beta (beta)').run()
    assert app.session_state['pending_change'] is None
    assert project_service.load_json('beta', 'project.json', {})['description'] == 'Other project'
    assert not app.exception


def test_requirement_review_shows_changed_fields_and_related_context(project):
    from models.schemas import Requirement
    requirement = Requirement(id='REQ-001', title='Internal demo',
        description='Complete onboarding by 28 February.', priority='high',
        source_refs=['meeting.txt#chunk-1']).model_dump()
    project_service.save_json('alpha', 'knowledge/analysis.json', {
        'requirements': [requirement],
        'gaps': [{'id': 'GAP-001', 'question': 'Who approves the demo?',
                  'severity': 'high', 'related_requirement_ids': ['REQ-001']}],
    })
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=20).run()
    app.sidebar.selectbox[0].select('Alpha (alpha)').run()
    chat_id = app.session_state['active_chats']['alpha']['id']
    app.session_state['pending_change'] = prepare_change('alpha', chat_id, {
        'target': 'requirement', 'value': dict(requirement, description='Complete onboarding by 15 March.')})
    app.run()
    assert not app.exception
    rows = app.table[0].value.to_dict('records')
    assert rows[0] == {'Field': 'Description',
        'Existing information': r'Complete onboarding by 28 February\.',
        'Proposed change': r'Complete onboarding by 15 March\.', 'Change': 'Updated'}
    assert next(row for row in rows if row['Field'] == 'Priority')['Change'] == 'Unchanged'
    assert next(row for row in rows if row['Field'] == 'Source references')['Existing information']
    assert app.table[1].value.iloc[0]['Question'] == 'Who approves the demo?'
    # Saved analysis has a share-text preview; the proposed edit is reviewed in a table.
    assert not any('15 March' in block.value for block in app.code)
    assert not app.json
