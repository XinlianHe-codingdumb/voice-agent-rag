from treasury_rag.api import BackendState
from treasury_rag.memory import ConversationStore


class FakeSummaryProvider:
    def __init__(self) -> None:
        self.transcript = []

    def summarize_conversation(self, messages):
        self.transcript = messages
        return "- User is learning AI agents.\n- Next step: study retrieval first."


def summary_state(tmp_path):
    state = object.__new__(BackendState)
    state.memory = ConversationStore(tmp_path / "conversations.sqlite3")
    provider = FakeSummaryProvider()
    state.provider = lambda: provider
    return state, provider


def test_chat_summary_is_created_only_after_ten_user_turns(tmp_path) -> None:
    state, provider = summary_state(tmp_path)
    for number in range(10):
        state.memory.append_turn("chat-a", f"question {number}", f"answer {number}")

    assert state._capture_conversation_summary("chat-a") is None
    assert provider.transcript == []

    state.memory.append_turn("chat-a", "question 10", "answer 10")
    saved = state._capture_conversation_summary("chat-a")

    assert saved is not None
    assert saved["category"] == "conversation_summary"
    assert saved["memory_key"] == "conversation-summary:chat-a"
    assert len(provider.transcript) == 22
    assert "AI agents" in saved["content"]


def test_chat_summary_is_not_duplicated_after_it_has_been_saved(tmp_path) -> None:
    state, provider = summary_state(tmp_path)
    for number in range(11):
        state.memory.append_turn("chat-a", f"question {number}", f"answer {number}")

    assert state._capture_conversation_summary("chat-a") is not None
    state.memory.append_turn("chat-a", "follow up", "follow-up answer")
    assert state._capture_conversation_summary("chat-a") is None
    assert len(state.memory.list_memories()) == 1
    assert len(provider.transcript) == 22


def test_summary_failure_does_not_break_a_completed_chat(tmp_path) -> None:
    state, provider = summary_state(tmp_path)
    for number in range(11):
        state.memory.append_turn("chat-a", f"question {number}", f"answer {number}")

    provider.summarize_conversation = lambda messages: (_ for _ in ()).throw(RuntimeError("temporary"))
    assert state._capture_conversation_summary("chat-a") is None
    assert state.memory.list_memories() == []
