from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from treasury_rag.baseline import BaselineIndex, create_provider  # noqa: E402
from treasury_rag.config import PROJECT_ROOT, Settings  # noqa: E402
from treasury_rag.evaluation import evaluate_retrieval, write_evaluation_report  # noqa: E402
from treasury_rag.experiments import (  # noqa: E402
    append_history,
    create_run_dir,
    publish_latest,
    snapshot_environment,
    write_run_manifest,
)


def main() -> None:
    settings = Settings.load()
    index = BaselineIndex.load(settings.artifact_dir)
    provider = create_provider(settings)
    metrics, predictions = evaluate_retrieval(
        settings.gold_dataset_path,
        index,
        provider,
        settings.top_k,
        settings.eval_split,
    )
    run_config = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "pipeline": "baseline_dense",
        "pdf": settings.pdf_path.name,
        "embedding_model": settings.embedding_model,
        "chunk_words": settings.chunk_words,
        "overlap_words": settings.overlap_words,
        "top_k": settings.top_k,
        "eval_split": settings.eval_split,
        "cases": metrics["cases"],
    }
    run_id, run_dir = create_run_dir(settings.runs_dir, "baseline_dense", settings.eval_split)
    run_config["run_id"] = run_id
    run_config["environment"] = snapshot_environment(PROJECT_ROOT)
    write_evaluation_report(run_dir, metrics, predictions, run_config)
    write_run_manifest(run_dir, {"run_config": run_config, "metrics": metrics})
    publish_latest(run_dir, settings.report_dir)
    append_history(
        PROJECT_ROOT / "reports" / "experiment_history.csv",
        run_id,
        "baseline_dense",
        settings.eval_split,
        metrics,
        run_dir,
    )

    print("\nBaseline retrieval results")
    print(f"Hit rate@{settings.top_k}: {metrics['hit_rate_at_k']:.3f}")
    print(f"Mean Recall@{settings.top_k}: {metrics['mean_recall_at_k']:.3f}")
    print(f"MRR: {metrics['mrr']:.3f}")
    print(f"Run ID: {run_id}")
    print(f"Immutable run directory: {run_dir}")
    print(f"\nOpen this report in a browser:\n{settings.report_dir / 'summary.html'}")
    print(f"\nSend these files back for review:\n{settings.report_dir / 'summary.md'}\n{settings.report_dir / 'failures.csv'}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise
