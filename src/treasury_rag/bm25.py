from __future__ import annotations

import math
import re
from collections import Counter

from .models import Chunk, SearchResult


_TOKEN = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in _TOKEN.finditer(text)]


class BM25Index:
    """Small, dependency-free BM25 implementation for a reproducible baseline."""

    def __init__(self, chunks: list[Chunk], *, k1: float = 1.5, b: float = 0.75) -> None:
        if not chunks:
            raise ValueError("BM25 requires at least one chunk")
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.term_frequencies = [Counter(tokenize(chunk.text)) for chunk in chunks]
        self.doc_lengths = [sum(counts.values()) for counts in self.term_frequencies]
        self.average_doc_length = sum(self.doc_lengths) / len(self.doc_lengths)
        document_frequency: Counter[str] = Counter()
        for counts in self.term_frequencies:
            document_frequency.update(counts.keys())
        total = len(chunks)
        self.idf = {
            term: math.log(1.0 + (total - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        query_terms = tokenize(query)
        scores: list[tuple[float, int]] = []
        for index, (counts, length) in enumerate(
            zip(self.term_frequencies, self.doc_lengths, strict=True)
        ):
            score = 0.0
            for term in query_terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                denominator = frequency + self.k1 * (
                    1.0 - self.b + self.b * length / self.average_doc_length
                )
                score += self.idf.get(term, 0.0) * (
                    frequency * (self.k1 + 1.0) / denominator
                )
            scores.append((score, index))
        ordered = sorted(scores, key=lambda item: (-item[0], item[1]))[:top_k]
        return [
            SearchResult(rank=rank, score=score, chunk=self.chunks[index])
            for rank, (score, index) in enumerate(ordered, start=1)
        ]

