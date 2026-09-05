import pytest

from treasury_rag.intent import (
    CONVERSATION,
    DOCUMENT_FACT,
    DOCUMENT_TASK,
    MEMORY,
    classify_intent,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Can you hear me?", CONVERSATION),
        ("你能听见我吗？", CONVERSATION),
        ("What did I just ask you?", CONVERSATION),
        ("我们刚才聊了什么？", CONVERSATION),
        ("What was the cash balance in 2025-26?", DOCUMENT_FACT),
        ("DPO 在哪一页？", DOCUMENT_FACT),
        ("What should I study in this book for an AI job?", DOCUMENT_TASK),
        ("为了找工作，这本书哪些章节值得学习？", DOCUMENT_TASK),
        ("Remember that I prefer concise answers", MEMORY),
        ("你记住了什么？", MEMORY),
    ],
)
def test_shared_intent_router(text: str, expected: str) -> None:
    assert classify_intent(text).intent == expected


def test_document_flags_are_exposed_for_realtime() -> None:
    fact = classify_intent("Where does the book discuss DPO?")
    task = classify_intent("Recommend chapters for learning agents")
    chat = classify_intent("Can you hear me?")

    assert fact.requires_documents and not fact.uses_agent_harness
    assert task.requires_documents and task.uses_agent_harness
    assert not chat.requires_documents and not chat.uses_agent_harness
