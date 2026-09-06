import sqlite3
import threading
from types import SimpleNamespace
from fastapi.testclient import TestClient
from treasury_rag import api
from treasury_rag.memory import ConversationStore


def test_evidence_survives_restart_and_chat_switch(tmp_path):
    path = tmp_path / 'history.sqlite3'
    store = ConversationStore(path, max_messages=2)
    sources = [{'document_name': 'book.pdf', 'pdf_page': 6, 'snippet': 'Original excerpt', 'chunk_id': 'p6'}]
    store.append_turn('a', 'Question', 'Answer [1]', sources=sources)
    for _ in range(8):
        store.append_turn('a', 'Followup', 'Okay')
    store.append_turn('b', 'Other chat', 'Other answer')
    reopened = ConversationStore(path, max_messages=2)
    assert reopened.get_conversation('b')['messages'][-1]['sources'] == []
    history = reopened.get_conversation('a')['messages']
    assert len(history) == 18
    assert history[1]['sources'] == sources
    assert len(reopened.get('a')) == 2
    assert 'sources' not in reopened.get('a')[0]


def test_migrates_existing_messages_without_losing_text(tmp_path):
    path = tmp_path / 'legacy.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE messages (message_id INTEGER PRIMARY KEY, conversation_id TEXT, role TEXT, content TEXT, created_at TEXT)')
        db.execute("INSERT INTO messages VALUES (1,'old','assistant','Old answer [1]','today')")
    store = ConversationStore(path)
    assert store.history('old')[0]['content'] == 'Old answer [1]'
    assert store.history('old')[0]['sources'] == []
    assert ConversationStore(path).history('old') == store.history('old')


def test_live_segments_keep_their_own_source_numbering(monkeypatch):
    state = object.__new__(api.BackendState)
    state._lock = threading.RLock()
    state.memory = ConversationStore()
    state.documents = {}
    monkeypatch.setattr(api, 'BackendState', lambda settings: state)
    segments = [
        {'content': 'Let me check.', 'sources': []},
        {'content': 'First answer [1]', 'sources': [{'document_name': 'a.pdf', 'pdf_page': 2, 'snippet': 'A'}]},
        {'content': 'Second answer [1]', 'sources': [{'document_name': 'b.pdf', 'pdf_page': 8, 'snippet': 'B'}]},
    ]
    with TestClient(api.create_app()) as client:
        result = client.post('/api/realtime/turn', json={'conversation_id': 'live', 'user': 'Compare', 'assistant': 'Combined', 'assistant_messages': segments})
        assert result.status_code == 200
        history = client.get('/api/conversations/live').json()['messages']
        assert [{k: m[k] for k in ('content', 'sources')} for m in history[1:]] == segments
