from treasury_rag.memory import ConversationStore


def test_conversation_store_isolates_sessions_and_trims_old_messages() -> None:
    store = ConversationStore(max_sessions=2, max_messages=2)
    store.append_turn("a", "first", "answer one")
    store.append_turn("a", "second", "answer two")
    store.append_turn("b", "other", "other answer")

    assert store.get("a") == [
        {"role": "user", "content": "second"},
        {"role": "assistant", "content": "answer two"},
    ]
    assert store.get("b")[0]["content"] == "other"


def test_conversation_store_clear() -> None:
    store = ConversationStore()
    store.append_turn("session", "hello", "hi")
    store.clear("session")
    assert store.get("session") == []


def test_conversation_store_persists_and_isolates_documents(tmp_path) -> None:
    database = tmp_path / "conversations.sqlite3"
    first = ConversationStore(database)
    first.create("First", "first")
    first.create("Second", "second")
    first.attach_document("first", "doc-a")
    first.append_turn("first", "hello", "hi")

    reopened = ConversationStore(database)
    assert reopened.document_ids("first") == ["doc-a"]
    assert reopened.document_ids("second") == []
    assert reopened.get("first")[-1]["content"] == "hi"


def test_first_message_sets_conversation_title() -> None:
    store = ConversationStore()
    store.create(conversation_id="chat")
    store.append_turn("chat", "What should I learn from this book?", "Start with RAG.")
    assert store.get_conversation("chat")["title"] == "What should I learn from this book?"
