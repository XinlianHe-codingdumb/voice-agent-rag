from treasury_rag.agent import needs_agent_harness


def test_indirect_learning_request_uses_agent_harness() -> None:
    assert needs_agent_harness("I want an AI job. What should I study in this book?")
    assert needs_agent_harness("为了找工作，这本书哪些章节最值得学习？")


def test_simple_fact_question_keeps_fast_rag_path() -> None:
    assert not needs_agent_harness("What was the cash balance in 2025-26?")
