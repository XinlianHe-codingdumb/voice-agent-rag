import threading
from types import SimpleNamespace as NS
import numpy as np
from treasury_rag.api import BackendState, build_realtime_session
from treasury_rag.memory import ConversationStore
from treasury_rag.openai_provider import OpenAIProvider


def state_fixture(tmp_path):
    state = object.__new__(BackendState)
    state._lock = threading.RLock()
    state.memory = ConversationStore(tmp_path / 'test.sqlite3')
    provider = NS(embed=lambda texts: np.array([[1., 0.]]))
    def record(doc_id, vector):
        return NS(document_id=doc_id, name=doc_id + '.pdf', pipeline=NS(
            index=NS(vectors=np.array([vector])), provider=provider))
    state.documents = {'book': record('book', [1., 0.]), 'other': record('other', [0., 1.])}
    return state


def test_accept_resumes_original_and_only_attaches_in_origin_chat(tmp_path):
    state = state_fixture(tmp_path)
    question = 'Where is DPO discussed?'
    proposal = state.prepare_turn(question, 'a')
    assert proposal['document_access']['status'] == 'pending'
    assert 'text' not in proposal['document_access']
    assert state.memory.document_ids('a') == []
    state.prepare_turn('yes', 'b')
    assert state.memory.document_ids('b') == []
    accepted = state.prepare_turn('yes please', 'a')
    assert accepted['question'] == question
    assert state.memory.document_ids('a') == ['book']
    assert state.memory.pending_access('a') is None


def test_decline_and_changed_question_do_not_attach(tmp_path):
    state = state_fixture(tmp_path)
    state.prepare_turn('Where is DPO discussed?', 'a')
    assert state.prepare_turn('不要', 'a')['document_access']['status'] == 'declined'
    assert state.memory.document_ids('a') == []
    state.prepare_turn('Where is DPO discussed?', 'a')
    state.prepare_turn('Can you hear me?', 'a')
    state.prepare_turn('yes', 'a')
    assert state.memory.document_ids('a') == []


def test_selected_best_document_does_not_trigger_proposal(tmp_path):
    state = state_fixture(tmp_path)
    state.memory.attach_document('a', 'book')
    assert 'document_access' not in state.prepare_turn('Where is DPO discussed?', 'a')


def test_pending_survives_restart_and_expires(tmp_path):
    state = state_fixture(tmp_path)
    state.prepare_turn('Where is DPO discussed?', 'a')
    reopened = ConversationStore(tmp_path / 'test.sqlite3')
    assert reopened.pending_access('a')['document_id'] == 'book'
    with reopened._connection:
        reopened._connection.execute('UPDATE pending_document_access SET created_at=0')
    assert reopened.resolve_access('a', True) is None
    assert reopened.document_ids('a') == []


def test_both_asr_paths_receive_explicit_language():
    settings = NS(realtime_model='test', asr_model='test', realtime_voice='marin')
    for language in ('en', 'zh', 'auto'):
        session = build_realtime_session(settings, '', '', '', language)
        received = {}
        def transcribe(**kwargs):
            received.update(kwargs)
            return NS(text='Hello there')
        provider = object.__new__(OpenAIProvider)
        provider.asr_model = 'test'
        provider.client = NS(audio=NS(transcriptions=NS(create=transcribe)))
        provider.transcribe(b'audio', 'a.mp3', language=language)
        expected = None if language == 'auto' else language
        assert received.get('language') == expected
        assert session['audio']['input']['transcription'].get('language') == expected
