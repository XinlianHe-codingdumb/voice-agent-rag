import json

from treasury_rag.evaluation import evaluate_retrieval
from treasury_rag.models import Chunk, SearchResult


def test_evaluation_filters_split_and_computes_metrics(tmp_path, monkeypatch) -> None:
    dataset = tmp_path / "gold.jsonl"
    rows = [
        {
            "id": "dev-1",
            "split": "dev",
            "category": "semantic",
            "question": "dev question",
            "gold_pdf_pages": [10],
        },
        {
            "id": "test-1",
            "split": "test",
            "category": "lexical",
            "question": "test question",
            "gold_pdf_pages": [20],
        },
    ]
    dataset.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )

    fake_results = [
        SearchResult(
            rank=1,
            score=0.9,
            chunk=Chunk("p0010-c000", 10, 0, "evidence", 0, 1),
        )
    ]
    fake_retriever = lambda *args, **kwargs: fake_results

    metrics, predictions = evaluate_retrieval(
        dataset,
        index=None,
        provider=None,
        top_k=5,
        split="dev",
        retriever=fake_retriever,
    )

    assert metrics["cases"] == 1
    assert metrics["split"] == "dev"
    assert metrics["hit_rate_at_k"] == 1.0
    assert metrics["mrr"] == 1.0
    assert [row["id"] for row in predictions] == ["dev-1"]


def test_evaluation_supports_alternative_complete_evidence_sets(tmp_path) -> None:
    dataset = tmp_path / "gold.jsonl"
    row = {
        "id": "alternatives",
        "split": "dev",
        "category": "lexical",
        "question": "question",
        "gold_pdf_pages": [58, 185],
        "gold_evidence_sets": [[58], [185]],
    }
    dataset.write_text(json.dumps(row) + "\n", encoding="utf-8")
    fake_results = [
        SearchResult(1, 1.0, Chunk("p0185-c000", 185, 0, "evidence", 0, 1))
    ]

    metrics, predictions = evaluate_retrieval(
        dataset,
        index=None,
        provider=None,
        top_k=5,
        retriever=lambda *args, **kwargs: fake_results,
    )

    assert metrics["hit_rate_at_k"] == 1.0
    assert metrics["mean_recall_at_k"] == 1.0
    assert metrics["mrr"] == 1.0
    assert predictions[0]["matched_gold_evidence_set"] == [185]
