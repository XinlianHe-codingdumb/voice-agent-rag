from __future__ import annotations

import csv
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from .baseline import BaselineIndex, retrieve
from .io import read_jsonl, write_json, write_jsonl
from .openai_provider import OpenAIProvider


def evaluate_retrieval(
    dataset_path: Path,
    index: BaselineIndex,
    provider: OpenAIProvider,
    top_k: int,
    split: str = "dev",
    retriever=retrieve,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases = read_jsonl(dataset_path)
    if split != "all":
        cases = [case for case in cases if case.get("split") == split]
    if not cases:
        raise ValueError(f"No evaluation cases found for split: {split}")
    predictions: list[dict[str, Any]] = []
    for number, case in enumerate(cases, start=1):
        print(f"Evaluating {number}/{len(cases)}: {case['id']}")
        results = retriever(case["question"], index, provider, top_k)
        evidence_sets = _gold_evidence_sets(case)
        gold_pages = set().union(*evidence_sets)
        retrieved_pages = [result.chunk.pdf_page for result in results]
        relevant_ranks = [
            rank
            for rank, page in enumerate(retrieved_pages, start=1)
            if page in gold_pages
        ]
        recalls = [
            len(evidence_set.intersection(retrieved_pages)) / len(evidence_set)
            for evidence_set in evidence_sets
        ]
        recall_at_k = max(recalls)
        matched_evidence_set = evidence_sets[recalls.index(recall_at_k)]
        reciprocal_rank = 1.0 / relevant_ranks[0] if relevant_ranks else 0.0
        predictions.append(
            {
                **case,
                "retrieved_pdf_pages": retrieved_pages,
                "retrieved": [result.to_dict() for result in results],
                "hit_at_k": bool(relevant_ranks),
                "recall_at_k": recall_at_k,
                "reciprocal_rank": reciprocal_rank,
                "first_relevant_rank": relevant_ranks[0] if relevant_ranks else None,
                "matched_gold_evidence_set": sorted(matched_evidence_set),
            }
        )

    metrics = {
        "cases": len(predictions),
        "split": split,
        "top_k": top_k,
        "hit_rate_at_k": mean(float(row["hit_at_k"]) for row in predictions),
        "mean_recall_at_k": mean(row["recall_at_k"] for row in predictions),
        "mrr": mean(row["reciprocal_rank"] for row in predictions),
    }
    metrics["by_category"] = _category_metrics(predictions)
    return metrics, predictions


def _gold_evidence_sets(case: dict[str, Any]) -> list[set[int]]:
    """Return alternative evidence sets; every page within one set is required."""
    raw_sets = case.get("gold_evidence_sets")
    if raw_sets is None:
        raw_sets = [case["gold_pdf_pages"]]
    evidence_sets = [set(int(page) for page in pages) for pages in raw_sets]
    if not evidence_sets or any(not pages for pages in evidence_sets):
        raise ValueError(f"Case {case.get('id')} has an empty gold evidence set")
    return evidence_sets


def write_evaluation_report(
    report_dir: Path,
    metrics: dict[str, Any],
    predictions: list[dict[str, Any]],
    run_config: dict[str, Any],
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(report_dir / "predictions.jsonl", predictions)
    write_json(report_dir / "metrics.json", metrics)
    write_json(report_dir / "run_config.json", run_config)
    _write_failures(report_dir / "failures.csv", predictions)
    (report_dir / "summary.md").write_text(
        _markdown_summary(metrics, predictions, run_config), encoding="utf-8"
    )
    (report_dir / "summary.html").write_text(
        _html_summary(metrics, predictions, run_config), encoding="utf-8"
    )


def _category_metrics(predictions: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    categories = sorted({row["category"] for row in predictions})
    output: dict[str, dict[str, float]] = {}
    for category in categories:
        rows = [row for row in predictions if row["category"] == category]
        output[category] = {
            "cases": len(rows),
            "hit_rate_at_k": mean(float(row["hit_at_k"]) for row in rows),
            "mean_recall_at_k": mean(row["recall_at_k"] for row in rows),
            "mrr": mean(row["reciprocal_rank"] for row in rows),
        }
    return output


def _write_failures(path: Path, predictions: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "id",
                "category",
                "question",
                "gold_pdf_pages",
                "retrieved_pdf_pages",
                "first_relevant_rank",
            ],
        )
        writer.writeheader()
        for row in predictions:
            if not row["hit_at_k"]:
                writer.writerow(
                    {
                        "id": row["id"],
                        "category": row["category"],
                        "question": row["question"],
                        "gold_pdf_pages": row["gold_pdf_pages"],
                        "retrieved_pdf_pages": row["retrieved_pdf_pages"],
                        "first_relevant_rank": row["first_relevant_rank"],
                    }
                )


def _markdown_summary(
    metrics: dict[str, Any],
    predictions: list[dict[str, Any]],
    run_config: dict[str, Any],
) -> str:
    lines = [
        "# Baseline retrieval evaluation",
        "",
        f"- Cases: {metrics['cases']}",
        f"- Split: {metrics['split']}",
        f"- Top K: {metrics['top_k']}",
        f"- Hit rate@K: {metrics['hit_rate_at_k']:.3f}",
        f"- Mean Recall@K: {metrics['mean_recall_at_k']:.3f}",
        f"- MRR: {metrics['mrr']:.3f}",
        "",
        "## Results by category",
        "",
        "| Category | Cases | Hit rate@K | Recall@K | MRR |",
        "|---|---:|---:|---:|---:|",
    ]
    for category, values in metrics["by_category"].items():
        lines.append(
            f"| {category} | {int(values['cases'])} | "
            f"{values['hit_rate_at_k']:.3f} | {values['mean_recall_at_k']:.3f} | "
            f"{values['mrr']:.3f} |"
        )
    failures = [row for row in predictions if not row["hit_at_k"]]
    lines.extend(
        [
            "",
            "## Failed cases",
            "",
            f"{len(failures)} of {len(predictions)} cases had no gold page in the top K.",
            "See `failures.csv` and `predictions.jsonl` for details.",
            "",
            "## Run configuration",
            "",
            "```json",
            json.dumps(run_config, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _html_summary(
    metrics: dict[str, Any],
    predictions: list[dict[str, Any]],
    run_config: dict[str, Any],
) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(row['id'])}</td>"
        f"<td>{html.escape(row['category'])}</td>"
        f"<td>{html.escape(row['question'])}</td>"
        f"<td>{html.escape(str(row['gold_pdf_pages']))}</td>"
        f"<td>{html.escape(str(row['retrieved_pdf_pages']))}</td>"
        f"<td class={'pass' if row['hit_at_k'] else 'fail'}>"
        f"{'PASS' if row['hit_at_k'] else 'FAIL'}</td>"
        "</tr>"
        for row in predictions
    )
    generated = datetime.now(timezone.utc).isoformat()
    model_label = run_config.get("embedding_model", run_config.get("retriever", "unknown"))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Baseline Retrieval Evaluation</title>
  <style>
    body {{ font-family: Inter, system-ui, sans-serif; margin: 0; background: #f5f3ef; color: #20231f; }}
    main {{ max-width: 1180px; margin: 40px auto; padding: 0 24px 60px; }}
    h1 {{ font-size: 34px; margin-bottom: 6px; }}
    .subtle {{ color: #676b64; }}
    .metrics {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin: 28px 0; }}
    .card {{ background: white; border: 1px solid #dedbd4; border-radius: 14px; padding: 20px; }}
    .value {{ font-size: 34px; font-weight: 700; color: #8f1d21; }}
    table {{ width: 100%; border-collapse: collapse; background: white; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid #e5e1da; text-align: left; vertical-align: top; padding: 12px; }}
    th {{ background: #262a26; color: white; position: sticky; top: 0; }}
    .pass {{ color: #176b3a; font-weight: 700; }}
    .fail {{ color: #b42318; font-weight: 700; }}
    code {{ background: #ebe8e1; padding: 2px 5px; border-radius: 4px; }}
    @media (max-width: 760px) {{ .metrics {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
<main>
  <h1>Baseline retrieval evaluation</h1>
  <p class="subtle">Generated {html.escape(generated)} using <code>{html.escape(str(model_label))}</code></p>
  <section class="metrics">
    <div class="card"><div>Hit rate@{metrics['top_k']}</div><div class="value">{metrics['hit_rate_at_k']:.3f}</div></div>
    <div class="card"><div>Mean Recall@{metrics['top_k']}</div><div class="value">{metrics['mean_recall_at_k']:.3f}</div></div>
    <div class="card"><div>MRR</div><div class="value">{metrics['mrr']:.3f}</div></div>
  </section>
  <h2>Per-question evidence retrieval</h2>
  <table>
    <thead><tr><th>ID</th><th>Category</th><th>Question</th><th>Gold pages</th><th>Retrieved pages</th><th>Result</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</main>
</body>
</html>"""
