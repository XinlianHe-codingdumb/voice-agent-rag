from __future__ import annotations

import re
import unicodedata


_WHITESPACE = re.compile(r"\s+")
_BROKEN_HYPHEN = re.compile(r"(?<=\w)-\s+(?=[a-z])")
_REPORT_HEADER = re.compile(
    r"HM Treasury Annual Report\s*&\s*Accounts\s*2025\s*[–-]\s*26",
    re.IGNORECASE,
)
_REPORT_NAVIGATION = re.compile(
    r"ACCOUNTABILITY\s+REPORT\s+FINANCIAL\s+REVIEW\s+PERFORMANCE\s+REPORT\s+"
    r"FINANCIAL\s+STATEMENTS\s+ANNEXES\s+TRUST\s+STATEMENT",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    """Apply conservative cleanup without changing document facts."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\x00", " ")
    text = text.replace("�", "'")
    text = _BROKEN_HYPHEN.sub("", text)
    return _WHITESPACE.sub(" ", text).strip()


def remove_report_boilerplate(text: str) -> str:
    """Remove only exact repeated report chrome, not substantive content."""
    text = _REPORT_HEADER.sub(" ", text)
    text = _REPORT_NAVIGATION.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()
