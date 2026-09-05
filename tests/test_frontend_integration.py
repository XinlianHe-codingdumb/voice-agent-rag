from types import SimpleNamespace
from fastapi.testclient import TestClient
from treasury_rag import api
from treasury_rag.memory import ConversationStore


def test_transcription_endpoint_does_not_answer_or_write_conversation(monkeypatch):
    state = object.__new__(api.BackendState)
    state.memory = ConversationStore()
    state.provider = lambda: SimpleNamespace(transcribe=lambda *args, **kwargs: 'Review this transcript before sending.')
    state._answer = lambda *args: (_ for _ in ()).throw(AssertionError('Transcription must not perform RAG'))
    monkeypatch.setattr(api, 'BackendState', lambda settings: state)
    with TestClient(api.create_app()) as client:
        response = client.post('/api/transcribe', data={'language': 'en', 'duration_ms': '1500', 'peak_rms':'0.05'},
                               files={'file': ('question.webm', b'a'*1000, 'audio/webm')})
        assert response.status_code == 200
        assert response.json()['transcript'] == 'Review this transcript before sending.'
        assert 'answer' not in response.json()
        assert state.memory.list_conversations() == []
        assert client.post('/api/transcribe', data={'language':'invalid'}, files={'file':('bad.webm',b'a'*1000)}).status_code == 400


def test_edit_memory_persists_and_keeps_source(tmp_path):
    store = ConversationStore(tmp_path / 'memory.sqlite3')
    original = store.remember(memory_key='test', category='preference', content='Concise answers', source_conversation_id='origin')
    assert store.edit_memory(original['memory_id'], 'Detailed answers')
    updated = ConversationStore(tmp_path / 'memory.sqlite3').list_memories()[0]
    assert updated['content'] == 'Detailed answers'
    assert updated['source_conversation_id'] == 'origin'
    assert updated['created_at'] == original['created_at']
    assert not store.edit_memory(9999, 'Missing')
