import pytest

from services import project_service
from services.chat_actions import prepare_change, apply_change


@pytest.fixture
def diagram(tmp_path, monkeypatch):
    monkeypatch.setattr(project_service, 'PROJECTS', tmp_path)
    project_service.create_project('Alpha')
    path = project_service.project_path('alpha') / 'diagrams/process_flow.mmd'
    path.write_text('flowchart TD\nA[Start] --> B[End]', encoding='utf-8')
    return path


def proposal():
    return prepare_change('alpha', 'chat', {'target': 'diagram', 'value': {
        'diagram_type': 'Process Flow', 'code': 'flowchart TD\nA[Start] --> C[Review] --> B[End]'}})


def test_diagram_edit_requires_approval_and_is_single_use(diagram):
    original = diagram.read_text(encoding='utf-8')
    change = proposal()
    assert diagram.read_text(encoding='utf-8') == original
    with pytest.raises(ValueError, match='fresh approval'):
        apply_change(change, 'alpha', 'chat')
    with pytest.raises(ValueError, match='another project or conversation'):
        apply_change(change, 'alpha', 'different-chat', approved=True)
    apply_change(change, 'alpha', 'chat', approved=True)
    assert diagram.read_text(encoding='utf-8') == change['after']['code']
    assert 'C["Review"]' in diagram.read_text(encoding='utf-8')
    with pytest.raises(ValueError, match='fresh approval'):
        apply_change(change, 'alpha', 'chat', approved=True)


def test_stale_diagram_edit_is_rejected(diagram):
    change = proposal()
    diagram.write_text('flowchart TD\nX --> Y', encoding='utf-8')
    with pytest.raises(ValueError, match='changed since this preview'):
        apply_change(change, 'alpha', 'chat', approved=True)
    assert diagram.read_text(encoding='utf-8') == 'flowchart TD\nX --> Y'


def test_missing_diagram_and_wrong_type_are_rejected(diagram):
    with pytest.raises(ValueError, match='Generate this diagram'):
        prepare_change('alpha', 'chat', {'target': 'diagram', 'value': {
            'diagram_type': 'Sequence', 'code': 'sequenceDiagram\nA->>B: Hello'}})
    with pytest.raises(ValueError, match='complete diagram'):
        prepare_change('alpha', 'chat', {'target': 'diagram', 'value': {
            'diagram_type': 'Process Flow', 'code': 'sequenceDiagram\nA->>B: Hello'}})


def test_chat_receives_diagram_and_previews_before_approval(diagram, monkeypatch):
    import json
    from pathlib import Path
    from unittest.mock import Mock
    from streamlit.testing.v1 import AppTest
    from services.chat_service import agent_reply
    monkeypatch.setattr('services.chat_service.retrieve', lambda *args, **kwargs: [])
    llm = Mock()
    llm.chat_messages.return_value = json.dumps({'answer': 'Add review', 'change': {
        'target': 'diagram', 'value': {'diagram_type': 'Process Flow',
        'code': 'flowchart TD\nA[Start] --> C[Review] --> B[End]'}}})
    _, change = agent_reply('alpha', 'Add review before End in Process Flow', llm, [], 'chat')
    assert 'A[Start] --> B[End]' in llm.chat_messages.call_args.args[0][1]['content']
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=20).run()
    app.sidebar.selectbox[0].select('Alpha (alpha)').run()
    change['conversation_id'] = app.session_state['active_chats']['alpha']['id']
    app.session_state['pending_change'] = change
    app.run()
    assert not app.exception
    assert any('C["Review"]' in block.value for block in app.code)
    assert 'Review' not in diagram.read_text(encoding='utf-8')
    next(button for button in app.button if button.label == 'Approve change').click().run()
    assert not app.exception
    assert 'C["Review"]' in diagram.read_text(encoding='utf-8')
