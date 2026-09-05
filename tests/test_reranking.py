from treasury_rag.models import Chunk, SearchResult
from treasury_rag.reranking import extract_ranked_ids, reorder_results


def result(chunk_id: str, rank: int) -> SearchResult:
    return SearchResult(
        rank=rank,
        score=1.0,
        chunk=Chunk(chunk_id, rank, 0, chunk_id, 0, 1),
    )


def test_extract_and_apply_partial_ranking_stably() -> None:
    candidates = [
        result("p0001-c000", 1),
        result("p0002-c000", 2),
        result("p0003-c000", 3),
    ]
    raw = "1. p0003-c000\n2. p0001-c000\n3. p0003-c000\nnot-a-candidate"

    ids = extract_ranked_ids(raw, [item.chunk.chunk_id for item in candidates])
    reranked = reorder_results(candidates, ids)

    assert ids == ["p0003-c000", "p0001-c000"]
    assert [item.chunk.chunk_id for item in reranked] == [
        "p0003-c000",
        "p0001-c000",
        "p0002-c000",
    ]
    assert [item.rank for item in reranked] == [1, 2, 3]
