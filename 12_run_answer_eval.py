from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from treasury_rag.config import PROJECT_ROOT, Settings  # noqa: E402
from treasury_rag.experiments import (  # noqa: E402
    create_run_dir,
    publish_latest,
    snapshot_environment,
    write_run_manifest,
)
from treasury_rag.io import read_jsonl, write_json, write_jsonl  # noqa: E402
from treasury_rag.judging import cited_pdf_pages  # noqa: E402
from treasury_rag.rag_pipeline import HybridRAGPipeline  # noqa: E402


DATASET = PROJECT_ROOT / "eval" / "gold_answers.jsonl"
LATEST = PROJECT_ROOT / "reports" / "latest_answer"


def main() -> None:
    settings = Settings.load()
    pipeline = HybridRAGPipeline(settings)
    cases = read_jsonl(DATASET)
    predictions: list[dict[str, object]] = []

    for number, case in enumerate(cases, start=1):
        print(f"Evaluating answer {number}/{len(cases)}: {case['id']}")
        answer, results, retrieval_traces = pipeline.answer(case["question"])
        contexts = [
            f"[PDF page {item.chunk.pdf_page}]\n{item.chunk.text}" for item in results
        ]
        judgment, raw_judgment = pipeline.provider.judge_answer(
            question=case["question"],
            reference_answer=case["reference_answer"],
            candidate_answer=answer,
            contexts=contexts,
            answerable=bool(case["answerable"]),
        )
        cited_pages = cited_pdf_pages(answer)
        retrieved_pages = [item.chunk.pdf_page for item in results]
        citation_valid = (
            bool(cited_pages)
            and set(cited_pages).issubset(set(retrieved_pages))
            if case["answerable"]
            else set(cited_pages).issubset(set(retrieved_pages))
        )
        predictions.append(
            {
                **case,
                "answer": answer,
                "retrieved_pdf_pages": retrieved_pages,
                "cited_pdf_pages": cited_pages,
                "citation_valid": citation_valid,
                "correctness": int(judgment["correctness"]),
                "faithfulness": int(judgment["faithfulness"]),
                "unanswerable_handling": judgment.get("unanswerable_handling"),
                "judge_reason": judgment.get("reason"),
                "raw_judgment": raw_judgment,
                "retrieval_traces": retrieval_traces,
            }
        )

    answerable_rows = [row for row in predictions if row["answerable"]]
    unanswerable_rows = [row for row in predictions if not row["answerable"]]
    metrics = {
        "cases": len(predictions),
        "answerable_cases": len(answerable_rows),
        "unanswerable_cases": len(unanswerable_rows),
        "mean_correctness": mean(row["correctness"] / 2 for row in predictions),
        "mean_faithfulness": mean(row["faithfulness"] / 2 for row in predictions),
        "citation_validity_rate": mean(
            float(row["citation_valid"]) for row in answerable_rows
        ),
        "unanswerable_handling_rate": mean(
            float(row["unanswerable_handling"] is True) for row in unanswerable_rows
        ),
    }
    pipeline_name = "answer-quality-multi-query-rag"
    run_id, run_dir = create_run_dir(settings.runs_dir, pipeline_name, "dev")
    run_config = {
        "run_id": run_id,
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "pipeline": pipeline_name,
        "dataset": str(DATASET.relative_to(PROJECT_ROOT)),
        "chat_model": settings.chat_model,
        "embedding_model": settings.embedding_model,
        "top_k": settings.top_k,
        "judge": "same configured chat model; strict 0/1/2 rubric",
        "environment": snapshot_environment(PROJECT_ROOT),
    }
    write_json(run_dir / "metrics.json", metrics)
    write_jsonl(run_dir / "predictions.jsonl", predictions)
    write_json(run_dir / "run_config.json", run_config)
    summary = (
        "# Answer-quality evaluation\n\n"
        f"- Cases: {metrics['cases']}\n"
        f"- Normalized correctness: {metrics['mean_correctness']:.3f}\n"
        f"- Normalized faithfulness: {metrics['mean_faithfulness']:.3f}\n"
        f"- Citation validity: {metrics['citation_validity_rate']:.3f}\n"
        f"- Unanswerable handling: {metrics['unanswerable_handling_rate']:.3f}\n\n"
        "The judge is model-based; inspect `predictions.jsonl` and do not treat the "
        "aggregate as a substitute for human review.\n"
    )
    (run_dir / "summary.md").write_text(summary, encoding="utf-8")
    write_run_manifest(run_dir, {"run_config": run_config, "metrics": metrics})
    publish_latest(run_dir, LATEST)

    print("\nAnswer-quality results")
    print(f"Correctness: {metrics['mean_correctness']:.3f}")
    print(f"Faithfulness: {metrics['mean_faithfulness']:.3f}")
    print(f"Citation validity: {metrics['citation_validity_rate']:.3f}")
    print(f"Unanswerable handling: {metrics['unanswerable_handling_rate']:.3f}")
    print(f"Run ID: {run_id}")
    print(f"Immutable run directory: {run_dir}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise
