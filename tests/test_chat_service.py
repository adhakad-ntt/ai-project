from pathlib import Path
import json

import pytest
from streamlit.testing.v1 import AppTest

from services import project_service
from services.chat_service import answer_question, new_conversation, list_conversations, save_conversation
from services.llm_service import LLMService


@pytest.fixture
def projects(tmp_path, monkeypatch):
    monkeypatch.setattr(project_service, 'PROJECTS', tmp_path)
    for name in ['Alpha', 'Beta']:
        project_service.create_project(name, f'{name} workspace')
    project_service.save_json('alpha', 'knowledge/sources.json', {
        'meeting.txt': {'chunks': ['Order renewals require manager approval.']},
    })
    project_service.save_json('alpha', 'knowledge/analysis.json', {
        'requirements': [{'id': 'REQ-001', 'title': 'Manager approval'}],
    })


def test_conversation_storage_and_context(projects, monkeypatch):
    calls = []
    def respond(self, messages):
        calls.append(messages)
        return 'Manager approval [REQ-001].'
    monkeypatch.setattr(LLMService, 'chat_messages', respond)
    chat = new_conversation()
    answer = answer_question('alpha', 'Explain renewals', LLMService(), chat['messages'])
    chat = save_conversation('alpha', chat, 'Explain renewals', answer)
    answer_question('alpha', 'Who approves them?', LLMService(), chat['messages'])
    assert calls[1][2:4] == chat['messages']
    assert 'REQ-001' in calls[1][1]['content']
    assert list_conversations('alpha') == [chat]
    assert list_conversations('beta') == []
    other = save_conversation('alpha', new_conversation(), 'Other question', 'Other answer')
    assert [c['id'] for c in list_conversations('alpha')] == [other['id'], chat['id']]


def test_ui_recent_chats_and_minimize(projects, monkeypatch):
    calls = []
    def respond(self, messages):
        calls.append(messages)
        return json.dumps({'answer': 'Saved answer', 'change': None})
    monkeypatch.setattr(LLMService, 'configured', lambda self: True)
    monkeypatch.setattr(LLMService, 'chat_messages', respond)
    path = str(Path(__file__).resolve().parents[1] / 'app.py')
    app = AppTest.from_file(path, default_timeout=20).run()
    app.sidebar.selectbox[0].select('Alpha (alpha)').run()
    assert not app.exception
    assert not app.sidebar.chat_input
    app.chat_input[0].set_value('Explain renewals').run()
    assert not app.exception
    assert len(app.chat_message) == 2
    chat_id = list_conversations('alpha')[0]['id']
    app.button(key='toggle_chat').click().run()
    assert not app.chat_input
    app.button(key='toggle_chat').click().run()
    assert len(app.chat_message) == 2
    app.button(key='new_chat').click().run()
    assert not app.chat_message
    app.button(key=f'recent_alpha_{chat_id}').click().run()
    assert len(app.chat_message) == 2
    app.chat_input[0].set_value('Who approves them?').run()
    assert not app.exception
    assert calls[1][2]['content'] == 'Explain renewals'
    assert len(app.chat_message) == 4
    app.sidebar.selectbox[0].select('Beta (beta)').run()
    assert not app.chat_message
    assert not list_conversations('beta')
    fresh = AppTest.from_file(path, default_timeout=20).run()
    fresh.sidebar.selectbox[0].select('Alpha (alpha)').run()
    assert not fresh.chat_message
    fresh.button(key=f'recent_alpha_{chat_id}').click().run()
    assert len(fresh.chat_message) == 4
    assert not fresh.exception


def test_failed_reply_does_not_save_and_explains_error(projects, monkeypatch):
    from services.llm_service import RateLimitError
    monkeypatch.setattr(LLMService, 'configured', lambda self: True)
    def fail(self, messages):
        raise RateLimitError('Account quota reached. Try again later.')
    monkeypatch.setattr(LLMService, 'chat_messages', fail)
    path = str(Path(__file__).resolve().parents[1] / 'app.py')
    app = AppTest.from_file(path, default_timeout=20).run()
    app.sidebar.selectbox[0].select('Alpha (alpha)').run()
    app.chat_input[0].set_value('What is missing?').run()
    assert not app.exception
    assert 'quota' in app.error[0].value
    assert not list_conversations('alpha')
    assert app.session_state['active_chats']['alpha']['messages'] == []


def test_legacy_history_is_available_but_not_default(projects, monkeypatch):
    old = [{'role': 'user', 'content': 'Old question'}, {'role': 'assistant', 'content': 'Old answer'}]
    project_service.save_json('alpha', 'knowledge/chat_history.json', old)
    assert list_conversations('alpha')[0]['messages'] == old
    assert new_conversation()['messages'] == []
    chat = save_conversation('alpha', list_conversations('alpha')[0], 'Follow up', 'New answer')
    assert len(chat['messages']) == 4
    assert project_service.load_json('alpha', 'knowledge/chat_history.json', []) == old
