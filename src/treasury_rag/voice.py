from __future__ import annotations

import re


_ASR_PROMPT_ECHO_MARKERS = (
    "a spoken question about uploaded pdf documents",
    "preserve names acronyms dates percentages currencies and numbers exactly",
)


def validate_transcript(transcript: str | None) -> str:
    """Reject empty ASR output and the known instruction-echo failure mode."""
    text = (transcript or "").strip()
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    if not text or any(marker in normalized for marker in _ASR_PROMPT_ECHO_MARKERS):
        raise RuntimeError(
            "No speech was detected. Check the selected microphone and input level, "
            "then record for at least one second."
        )
    return text


def text_for_speech(answer: str) -> str:
    """Remove visual citation/markdown syntax while retaining the spoken answer."""
    text = re.sub(
        r"\s*\[(?:Document [^\]]+,\s*)?PDF page \d+\]", "", answer
    )
    text = text.replace("**", "").replace("__", "")
    return re.sub(r"\s+", " ", text).strip()
