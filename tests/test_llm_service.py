import json
from unittest.mock import Mock

import pytest
import requests

from services.llm_service import LLMService, RateLimitError, retry_delay
from services.langgraph_workflow import RequirementAnalysisWorkflow


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'test-key')
    post = Mock()
    monkeypatch.setattr('services.llm_service.requests.post', post)
    return post


def response(content, finish_reason='stop'):
    result = Mock(status_code=200)
    result.json.return_value = {
        'choices': [{'message': {'content': content}, 'finish_reason': finish_reason}],
    }
    return result


def test_json_mode_is_requested(provider):
    provider.return_value = response('{"requirements": []}')
    assert LLMService().json_chat('Analyze', 'Source') == {'requirements': []}
    assert provider.call_args.kwargs['json']['response_format'] == {'type': 'json_object'}
    assert provider.call_args.kwargs['json']['max_completion_tokens'] == 4096


@pytest.mark.parametrize('invalid', [
    '{"requirements": [] "gaps": []}',  # Missing comma, as in the screenshot.
    '{"requirements": [',
    '[]',
    '',
    None,
])
def test_invalid_output_is_regenerated(provider, invalid):
    provider.side_effect = [response(invalid), response('{"requirements": []}')]
    assert LLMService().json_chat('Analyze', 'Source') == {'requirements': []}
    assert provider.call_count == 2


def test_truncated_output_is_retried_even_if_valid_json(provider):
    provider.side_effect = [response('{}', 'length'), response('{"complete": true}')]
    assert LLMService().json_chat('Analyze', 'Source') == {'complete': True}
    assert provider.call_count == 2


def test_complete_fence_and_literal_braces(provider):
    provider.return_value = response('```json\n{"description": "Use {order_id}"}\n```')
    assert LLMService().json_chat('Analyze', 'Source')['description'] == 'Use {order_id}'


def test_provider_json_validation_failure_is_retried(provider):
    invalid = Mock(status_code=400)
    invalid.json.return_value = {'error': {'code': 'json_validate_failed'}}
    provider.side_effect = [invalid, response('{}')]
    assert LLMService().json_chat('Analyze', 'Source') == {}
    assert provider.call_count == 2


def test_authentication_failure_is_not_retried(provider):
    invalid = Mock(status_code=401)
    invalid.raise_for_status.side_effect = requests.HTTPError('Unauthorized')
    provider.return_value = invalid
    with pytest.raises(requests.HTTPError):
        LLMService().json_chat('Analyze', 'Source')
    assert provider.call_count == 1


def test_repeated_invalid_output_preserves_saved_analysis(provider, monkeypatch):
    provider.return_value = response('{"requirements": [] "gaps": []}')
    monkeypatch.setattr('agents.requirement_agent.all_chunks', lambda pid: [
        {'id': 'meeting#1', 'text': 'Orders need approval.'},
    ])
    monkeypatch.setattr('services.langgraph_workflow.load_json', lambda *args: {'requirements': []})
    save = Mock()
    monkeypatch.setattr('services.langgraph_workflow.save_json', save)
    with pytest.raises(ValueError, match='after two attempts') as error:
        RequirementAnalysisWorkflow().analyze('demo')
    assert not isinstance(error.value, json.JSONDecodeError)
    assert provider.call_count == 2
    save.assert_not_called()


def test_plain_chat_remains_plain_text(provider):
    provider.return_value = response('Hello')
    assert LLMService().chat('Assistant', 'Hi') == 'Hello'
    assert 'response_format' not in provider.call_args.kwargs['json']


def rate_limited(retry_after='2'):
    return Mock(status_code=429, headers={'retry-after': retry_after})


def test_analysis_recovers_from_rate_limit(provider, monkeypatch):
    sleep = Mock()
    monkeypatch.setattr('services.llm_service.time.sleep', sleep)
    monkeypatch.setattr('agents.requirement_agent.all_chunks', lambda pid: [
        {'id': 'meeting#1', 'text': 'Orders need approval.'},
    ])
    monkeypatch.setattr('services.langgraph_workflow.load_json', lambda *args: {})
    save = Mock()
    monkeypatch.setattr('services.langgraph_workflow.save_json', save)
    expected = {'requirements': [], 'gaps': [], 'assumptions': [], 'contradictions': []}
    provider.side_effect = [rate_limited('3'), response(json.dumps(expected))]
    assert RequirementAnalysisWorkflow().analyze('demo') == expected
    sleep.assert_called_once_with(3)
    save.assert_called_once_with('demo', 'knowledge/analysis.json', expected)


def test_rate_limit_retries_are_bounded_and_preserve_saved_analysis(provider, monkeypatch):
    sleep = Mock()
    monkeypatch.setattr('services.llm_service.time.sleep', sleep)
    monkeypatch.setattr('agents.requirement_agent.all_chunks', lambda pid: [
        {'id': 'meeting#1', 'text': 'Orders need approval.'},
    ])
    monkeypatch.setattr('services.langgraph_workflow.load_json', lambda *args: {'requirements': []})
    save = Mock()
    monkeypatch.setattr('services.langgraph_workflow.save_json', save)
    provider.return_value = rate_limited()
    with pytest.raises(RateLimitError, match='quota'):
        RequirementAnalysisWorkflow().analyze('demo')
    assert provider.call_count == 3
    assert sleep.call_count == 2
    save.assert_not_called()


def test_long_cooldown_does_not_retry_early(provider, monkeypatch):
    sleep = Mock()
    monkeypatch.setattr('services.llm_service.time.sleep', sleep)
    provider.return_value = rate_limited('3600')
    with pytest.raises(RateLimitError, match='3600 seconds'):
        LLMService().json_chat('Analyze', 'Source')
    assert provider.call_count == 1
    sleep.assert_not_called()


@pytest.mark.parametrize('value', [None, '', 'unknown', 'nan', 'inf'])
def test_missing_or_invalid_retry_header(value):
    assert retry_delay(value, 5) == 5


def test_connection_disconnect_is_retried(provider, monkeypatch):
    monkeypatch.setattr('services.llm_service.time.sleep', Mock())
    provider.side_effect = [requests.ConnectionError('Disconnected'), response('{}')]
    assert LLMService().json_chat('Analyze', 'Source') == {}
    assert provider.call_count == 2


def test_certificate_failure_is_not_retried(provider):
    provider.side_effect = requests.exceptions.SSLError('Invalid certificate')
    with pytest.raises(RuntimeError, match='certificate'):
        LLMService().json_chat('Analyze', 'Source')
    assert provider.call_count == 1
