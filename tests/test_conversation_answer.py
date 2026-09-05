from types import SimpleNamespace

from treasury_rag.openai_provider import OpenAIProvider


class FakeResponses:
    def __init__(self) -> None:
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(output_text="Yes, I can hear you.")


def test_conversation_answer_has_no_document_evidence_constraint() -> None:
    provider = object.__new__(OpenAIProvider)
    responses = FakeResponses()
    provider.client = SimpleNamespace(responses=responses)
    provider.chat_model = "test-model"

    answer = provider.answer_conversation("Can you hear me?")

    assert answer == "Yes, I can hear you."
    assert "classified by the application as conversation" in responses.request["instructions"]
    assert "Document excerpts" not in responses.request["input"]
