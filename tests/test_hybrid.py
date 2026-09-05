from treasury_rag.hybrid import reciprocal_rank_fusion
from treasury_rag.models import Chunk, SearchResult


def result(chunk_id: str, page: int, rank: int) -> SearchResult:
    return SearchResult(
        rank=rank,
        score=1.0,
        chunk=Chunk(chunk_id, page, 0, chunk_id, 0, 1),
    )


def test_rrf_rewards_agreement_between_retrievers() -> None:
    dense = [result("dense-only", 1, 1), result("shared", 2, 2)]
    lexical = [result("lexical-only", 3, 1), result("shared", 2, 2)]

    fused = reciprocal_rank_fusion([dense, lexical], top_k=3, rrf_k=60)

    assert fused[0].chunk.chunk_id == "shared"
    assert {item.chunk.chunk_id for item in fused[1:]} == {
        "dense-only",
        "lexical-only",
    }

