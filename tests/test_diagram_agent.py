import json
from unittest.mock import Mock

import pytest

from agents import diagram_agent


def test_diagram_uses_selected_project_description_analysis_and_sources(monkeypatch):
    records = {
        'project.json': {'name': 'Actual project', 'description': 'Real project scope'},
        'knowledge/analysis.json': {
            'requirements': [{'id': 'REQ-090', 'description': 'Real requirement'}],
            'gaps': [{'id': 'GAP-009', 'question': 'Unresolved choice'}],
            '_chat_requirement_overrides': {'REQ-090': {'description': 'Approved change'}},
        },
    }

    def load(pid, path, default):
        assert pid == 'selected-project'
        return records[path]

    def chunks(pid):
        assert pid == 'selected-project'
        return [{'id': 'actual.txt#chunk-1', 'text': 'Uploaded project evidence'}]

    monkeypatch.setattr(diagram_agent, 'load_json', load)
    monkeypatch.setattr(diagram_agent, 'all_chunks', chunks)
    directory = Mock()
    directory.__truediv__ = Mock(return_value=directory)
    monkeypatch.setattr(diagram_agent, 'project_path', lambda pid: directory)
    llm = Mock()
    llm.chat.return_value = 'flowchart TD\nA[Real capability]'
    diagram_agent.generate('selected-project', llm, 'Architecture')
    context = json.loads(llm.chat.call_args.args[1].split('PROJECT DATA:\n')[1])
    assert context['project']['description'] == 'Real project scope'
    assert context['analysis']['requirements'][0]['id'] == 'REQ-090'
    assert context['source_passages'][0]['text'] == 'Uploaded project evidence'
    assert context['approved_requirement_overrides']['REQ-090']['description'] == 'Approved change'
    directory.write_text.assert_called_once()


def test_missing_analysis_does_not_generate_generic_diagram(monkeypatch):
    monkeypatch.setattr(diagram_agent, 'load_json', lambda *args: {})
    monkeypatch.setattr(diagram_agent, 'all_chunks', lambda pid: [])
    llm = Mock()
    with pytest.raises(ValueError, match='Run Requirement and Gap Analysis'):
        diagram_agent.generate('empty-project', llm, 'Architecture')
    llm.chat.assert_not_called()
