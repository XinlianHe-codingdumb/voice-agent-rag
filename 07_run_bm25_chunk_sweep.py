from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from treasury_rag.bm25 import BM25Index  # noqa: E402
from treasury_rag.chunking import chunk_pages  # noqa: E402
from treasury_rag.config import PROJECT_ROOT, Settings  # noqa: E402
from treasury_rag.evaluation import evaluate_retrieval, write_evaluation_report  # noqa: E402
from treasury_rag.experiments import (  # noqa: E402
    append_history,
    create_run_dir,
    publish_latest,
    snapshot_environment,
    write_run_manifest,
)
from treasury_rag.pdf import extract_pages  # noqa: E402


CONFIGURATIONS = [(120, 20), (160, 30), (220, 40), (300, 50)]


def main() -> None:
    settings = Settings.load()
    pages = extract_pages(settings.pdf_path)
    summaries = []

    def bm25_retriever(question, index, provider, top_k):
        return index.search(question, top_k)

    for chunk_words, overlap_words in CONFIGURATIONS:
        chunks = chunk_pages(pages, chunk_words, overlap_words)
        index = BM25Index(chunks)
        metrics, predictions = evaluate_retrieval(
            settings.gold_dataset_path,
            index,
            provider=None,
            top_k=settings.top_k,
            split=settings.eval_split,
            retriever=bm25_retriever,
        )
        pipeline = f"bm25_w{chunk_words}_o{overlap_words}"
        run_config = {
            "run_at_utc": datetime.now(timezone.utc).isoformat(),
            "pipeline": pipeline,
            "retriever": "dependency-free BM25(k1=1.5,b=0.75)",
            "experiment": "chunk-size sweep; all other variables fixed",
            "pdf": settings.pdf_path.name,
            "chunk_words": chunk_words,
            "overlap_words": overlap_words,
            "chunks": len(chunks),
            "top_k": settings.top_k,
            "eval_split": settings.eval_split,
            "cases": metrics["cases"],
        }
        run_id, run_dir = create_run_dir(settings.runs_dir, pipeline, settings.eval_split)
        run_config["run_id"] = run_id
        run_config["environment"] = snapshot_environment(PROJECT_ROOT)
        write_evaluation_report(run_dir, metrics, predictions, run_config)
        write_run_manifest(run_dir, {"run_config": run_config, "metrics": metrics})
        append_history(
            PROJECT_ROOT / "reports" / "experiment_history.csv",
            run_id,
            pipeline,
            settings.eval_split,
            metrics,
            run_dir,
        )
        summaries.append((metrics["mrr"], metrics["hit_rate_at_k"], run_id, run_dir, metrics))

    best = max(summaries, key=lambda row: (row[0], row[1]))
    publish_latest(best[3], settings.report_dir)
    print("\nChunk sweep comparison (sorted by configuration order)")
    for _, _, run_id, _, metrics in summaries:
        print(
            f"{run_id}: Hit@{settings.top_k}={metrics['hit_rate_at_k']:.3f}, "
            f"Recall@{settings.top_k}={metrics['mean_recall_at_k']:.3f}, "
            f"MRR={metrics['mrr']:.3f}"
        )
    print(f"\nBest by MRR then Hit@K: {best[2]}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise

