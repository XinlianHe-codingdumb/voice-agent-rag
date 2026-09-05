from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class MemoryCandidate:
    category: str
    content: str

    @property
    def key(self) -> str:
        if self.category == "goal":
            return "goal:primary"
        normalized = re.sub(r"\s+", " ", self.content.casefold()).strip()
        digest = hashlib.sha256(f"{self.category}\0{normalized}".encode("utf-8")).hexdigest()
        return f"{self.category}:{digest[:24]}"


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "explicit",
        re.compile(r"^(?:please\s+)?remember(?:\s+that)?\s+(.+)$", re.IGNORECASE),
    ),
    ("explicit", re.compile(r"^(?:请)?记住[：:，,]?\s*(.+)$")),
    (
        "goal",
        re.compile(r"^my\s+(?:current\s+)?(?:goal|objective)\s+is\s+(.+)$", re.IGNORECASE),
    ),
    ("goal", re.compile(r"^我的(?:当前)?目标是[：:，,]?\s*(.+)$")),
    ("preference", re.compile(r"^i\s+prefer\s+(.+)$", re.IGNORECASE)),
    ("preference", re.compile(r"^我(?:更)?(?:喜欢|偏好)[：:，,]?\s*(.+)$")),
    (
        "preference",
        re.compile(r"^我希望你以后[：:，,]?\s*(.+)$"),
    ),
    (
        "background",
        re.compile(r"^my\s+background\s+is\s+(.+)$", re.IGNORECASE),
    ),
    ("background", re.compile(r"^我的背景是[：:，,]?\s*(.+)$")),
)

_MEMORY_QUERY_MARKERS = (
    "what do you remember about me",
    "what do you know about me",
    "what is my goal",
    "你记得我什么",
    "你记住了什么",
    "你知道我的什么",
    "我的目标是什么",
)


def extract_explicit_memories(text: str) -> list[MemoryCandidate]:
    """Extract only explicit durable facts; ordinary turns are never silently stored."""
    candidates: list[MemoryCandidate] = []
    for sentence in _sentences(text):
        for category, pattern in _PATTERNS:
            match = pattern.match(sentence)
            if not match:
                continue
            content = match.group(1).strip(" .。!！?？")
            if 2 <= len(content) <= 500:
                candidates.append(MemoryCandidate(category, content))
            break
    return _unique(candidates)


def is_memory_query(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.casefold()).strip(" .?!。？！")
    return any(marker in normalized for marker in _MEMORY_QUERY_MARKERS)


def format_memories(memories: Iterable[dict[str, object]]) -> str:
    lines = [f"- [{item['category']}] {item['content']}" for item in memories]
    return "\n".join(lines) or "(none)"


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[\r\n]+", text) if part.strip()]


def _unique(candidates: Iterable[MemoryCandidate]) -> list[MemoryCandidate]:
    selected: list[MemoryCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.key not in seen:
            seen.add(candidate.key)
            selected.append(candidate)
    return selected
