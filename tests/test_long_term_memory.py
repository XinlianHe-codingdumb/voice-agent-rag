from treasury_rag.long_term_memory import extract_explicit_memories, is_memory_query
from treasury_rag.memory import ConversationStore


def test_extracts_only_explicit_durable_memory_phrases() -> None:
    english = extract_explicit_memories("My goal is to get an AI engineering job")
    chinese = extract_explicit_memories("我希望你以后用中文简短回答")

    assert [(item.category, item.content) for item in english] == [
        ("goal", "to get an AI engineering job")
    ]
    assert [(item.category, item.content) for item in chinese] == [
        ("preference", "用中文简短回答")
    ]
    assert extract_explicit_memories("Where does the book discuss DPO?") == []


def test_detects_memory_questions_in_both_languages() -> None:
    assert is_memory_query("What do you remember about me?")
    assert is_memory_query("你记住了什么？")
    assert not is_memory_query("What does the report say about memory?")


def test_long_term_memory_persists_across_conversations_and_can_be_deleted(tmp_path) -> None:
    database = tmp_path / "memory.sqlite3"
    first = ConversationStore(database)
    candidate = extract_explicit_memories("I prefer concise answers")[0]
    stored = first.remember(
        memory_key=candidate.key,
        category=candidate.category,
        content=candidate.content,
        source_conversation_id="chat-a",
    )

    reopened = ConversationStore(database)
    memories = reopened.list_memories()
    assert memories[0]["content"] == "concise answers"
    assert memories[0]["source_conversation_id"] == "chat-a"
    assert reopened.forget_memory(int(stored["memory_id"]))
    assert reopened.list_memories() == []


def test_new_explicit_goal_replaces_the_previous_goal() -> None:
    store = ConversationStore()
    first, second = (
        extract_explicit_memories("My goal is to learn RAG")[0],
        extract_explicit_memories("My goal is to build a voice agent")[0],
    )
    for candidate in (first, second):
        store.remember(
            memory_key=candidate.key,
            category=candidate.category,
            content=candidate.content,
        )

    memories = store.list_memories()
    assert len(memories) == 1
    assert memories[0]["content"] == "to build a voice agent"
