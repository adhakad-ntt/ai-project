from io import BytesIO
from unittest.mock import Mock

import pytest

from services import project_service
from services.ingestion_service import ingest_upload, ingest_transcript, all_chunks
from agents.requirement_agent import run


def test_analysis_combines_upload_and_transcript_and_updates(tmp_path, monkeypatch):
    monkeypatch.setattr(project_service, 'PROJECTS', tmp_path)
    project_service.create_project('Alpha')
    project_service.create_project('Beta')
    upload = BytesIO(b'Document: create invoices.')
    upload.name = 'requirements.txt'
    ingest_upload('alpha', upload)
    assert ingest_transcript('alpha', 'Planning meeting', 'Alice: require approval.')['change'] == 'new'
    assert ingest_transcript('alpha', 'Planning meeting', 'Alice: require approval.')['change'] == 'unchanged'
    assert ingest_transcript('alpha', 'Planning meeting', 'Alice: require manager approval.')['change'] == 'updated'
    llm = Mock()
    llm.json_chat.return_value = {'requirements': [], 'gaps': [], 'assumptions': [], 'contradictions': []}
    run('alpha', llm)
    prompt = llm.json_chat.call_args.args[1]
    assert 'Document: create invoices.' in prompt
    assert 'Alice: require manager approval.' in prompt
    assert 'pasted_transcripts/planning-meeting.txt#chunk-1' in prompt
    assert len(all_chunks('alpha')) == 2
    assert not all_chunks('beta')
    ingest_transcript('alpha', 'Second meeting', 'Bob: retain history.')
    assert len(all_chunks('alpha')) == 3


def test_blank_transcript_rejected():
    with pytest.raises(ValueError, match='Paste a transcript'):
        ingest_transcript('alpha', 'Meeting', '   ')
    with pytest.raises(ValueError, match='title'):
        ingest_transcript('alpha', '!!!', 'Meeting text')
