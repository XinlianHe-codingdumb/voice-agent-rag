from treasury_rag.models import Chunk, SearchResult
from treasury_rag.multi_query import decompose_question, round_robin_unique


def result(chunk_id: str, rank: int) -> SearchResult:
    return SearchResult(rank, 1.0, Chunk(chunk_id, rank, 0, chunk_id, 0, 1))


def test_decompose_explicit_coordinated_question() -> None:
    question = "What was the first value, and which section gives the second value?"
    assert decompose_question(question) == [
        "What was the first value",
        "which section gives the second value?",
    ]


def test_round_robin_preserves_subquery_coverage_and_deduplicates() -> None:
    first = [result("a", 1), result("shared", 2), result("c", 3)]
    second = [result("b", 1), result("shared", 2), result("d", 3)]
    merged = round_robin_unique([first, second], top_k=5)
    assert [item.chunk.chunk_id for item in merged] == ["a", "b", "shared", "c", "d"]
    assert [item.rank for item in merged] == [1, 2, 3, 4, 5]
