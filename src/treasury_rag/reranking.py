from __future__ import annotations

import re
from collections.abc import Sequence

from .models import SearchResult


def extract_ranked_ids(text: str, allowed_ids: Sequence[str]) -> list[str]:
    """Extract allowed chunk IDs in model-output order, ignoring duplicates."""
    allowed = set(allowed_ids)
    ranked: list[str] = []
    for token in re.findall(r"[A-Za-z0-9_-]+", text):
        if token in allowed and token not in ranked:
            ranked.append(token)
    return ranked


def reorder_results(
    candidates: Sequence[SearchResult], ranked_ids: Sequence[str]
) -> list[SearchResult]:
    """Apply a partial ranking and append any omitted candidates stably."""
    by_id = {item.chunk.chunk_id: item for item in candidates}
    ordered_ids: list[str] = []
    for chunk_id in ranked_ids:
        if chunk_id in by_id and chunk_id not in ordered_ids:
            ordered_ids.append(chunk_id)
    ordered_ids.extend(
        item.chunk.chunk_id
        for item in candidates
        if item.chunk.chunk_id not in ordered_ids
    )
    return [
        SearchResult(rank=rank, score=1.0 / rank, chunk=by_id[chunk_id].chunk)
        for rank, chunk_id in enumerate(ordered_ids, start=1)
    ]
