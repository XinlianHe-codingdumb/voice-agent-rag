from dataclasses import replace

from treasury_rag import api
from treasury_rag.config import Settings


def test_fresh_install_starts_without_pdf_index_or_key(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'CONVERSATION_DB', tmp_path / 'conversations.sqlite3')
    monkeypatch.setattr(api, 'DOCUMENT_CATALOG', tmp_path / 'catalog.json')
    settings = replace(Settings.load(), pdf_path=tmp_path / 'missing.pdf',
                       artifact_dir=tmp_path / 'indexes', openai_api_key=None)
    state = api.BackendState(settings)
    assert state.list_documents() == []
    assert state.memory.list_conversations()[0]['conversation_id'] == 'default'
