from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PageText:
    pdf_page: int
    text: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    pdf_page: int
    chunk_index: int
    text: str
    word_start: int
    word_end: int
    document_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Chunk":
        return cls(**value)


@dataclass(frozen=True)
class SearchResult:
    rank: int
    score: float
    chunk: Chunk

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "score": self.score,
            "chunk": self.chunk.to_dict(),
        }
