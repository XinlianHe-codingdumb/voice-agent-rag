import pytest

from treasury_rag.voice import text_for_speech, validate_transcript


def test_text_for_speech_removes_visual_citations_and_markdown() -> None:
    answer = (
        "The value was **£23.6 billion**. "
        "[Document HM Treasury Report.pdf, PDF page 22]"
    )
    assert text_for_speech(answer) == "The value was £23.6 billion."


def test_validate_transcript_accepts_spoken_question() -> None:
    assert validate_transcript("What were the staff costs?") == "What were the staff costs?"


def test_validate_transcript_rejects_previous_prompt_echo() -> None:
    echoed = (
        "context: ### A spoken question about uploaded PDF documents. "
        "Preserve names, acronyms, dates, percentages, currencies, and numbers exactly. ###"
    )
    with pytest.raises(RuntimeError, match="No speech was detected"):
        validate_transcript(echoed)
