from __future__ import annotations

import re
from collections.abc import Sequence

from .models import SearchResult


_CLAUSE_BOUNDARY = re.compile(
    r"\s*,?\s+and\s+(?=(?:what|which|how|where|when|why|who)\b)",
    flags=re.IGNORECASE,
)


def decompose_question(question: str) -> list[str]:
    """Split explicit coordinated questions without inventing new subqueries."""
    clauses = [part.strip(" ,") for part in _CLAUSE_BOUNDARY.split(question)]
    return [clause for clause in clauses if clause]


def round_robin_unique(
    rankings: Sequence[Sequence[SearchResult]], top_k: int
) -> list[SearchResult]:
    """Interleave ranked lists so each subquery receives evidence coverage."""
    selected: list[SearchResult] = []
    seen: set[str] = set()
    depth = 0
    while len(selected) < top_k and any(depth < len(items) for items in rankings):
        for items in rankings:
            if depth >= len(items):
                continue
            item = items[depth]
            if item.chunk.chunk_id not in seen:
                seen.add(item.chunk.chunk_id)
                selected.append(item)
                if len(selected) == top_k:
                    break
        depth += 1
    return [
        SearchResult(rank=rank, score=1.0 / rank, chunk=item.chunk)
        for rank, item in enumerate(selected, start=1)
    ]
