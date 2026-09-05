from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from treasury_rag.baseline import BaselineIndex, create_provider, retrieve  # noqa: E402
from treasury_rag.bm25 import BM25Index  # noqa: E402
from treasury_rag.config import PROJECT_ROOT, Settings  # noqa: E402
from treasury_rag.evaluation import evaluate_retrieval, write_evaluation_report  # noqa: E402
from treasury_rag.experiments import (  # noqa: E402
    append_history,
    create_run_dir,
    publish_latest,
    snapshot_environment,
    write_run_manifest,
)
from treasury_rag.hybrid import reciprocal_rank_fusion  # noqa: E402


RETRIEVER_CANDIDATE_K = 20
RERANK_CANDIDATE_K = 12
RRF_K = 60


def main() -> None:
    settings = Settings.load()
    dense_index = BaselineIndex.load(settings.artifact_dir)
    bm25_index = BM25Index(dense_index.chunks)
    provider = create_provider(settings)
    rerank_traces: list[dict[str, object]] = []

    def reranked_retriever(question, index, active_provider, top_k):
        dense_results = retrieve(
            question, dense_index, active_provider, RETRIEVER_CANDIDATE_K
        )
        bm25_results = bm25_index.search(question, RETRIEVER_CANDIDATE_K)
        fused = reciprocal_rank_fusion(
            [dense_results, bm25_results],
            top_k=RERANK_CANDIDATE_K,
            rrf_k=RRF_K,
        )
        reranked, raw_output = active_provider.rerank(question, fused)
        rerank_traces.append(
            {
                "question": question,
                "input_chunk_ids": [item.chunk.chunk_id for item in fused],
                "output_chunk_ids": [item.chunk.chunk_id for item in reranked],
                "raw_model_output": raw_output,
            }
        )
        return reranked[:top_k]

    metrics, predictions = evaluate_retrieval(
        settings.gold_dataset_path,
        dense_index,
        provider,
        settings.top_k,
        settings.eval_split,
        retriever=reranked_retriever,
    )
    pipeline = "hybrid_rrf_llm_reranker"
    run_config = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "pipeline": pipeline,
        "retrievers": [f"dense:{settings.embedding_model}", "BM25:k1=1.5,b=0.75"],
        "fusion": "unweighted reciprocal rank fusion",
        "rrf_k": RRF_K,
        "candidate_k_per_retriever": RETRIEVER_CANDIDATE_K,
        "reranker": settings.chat_model,
        "rerank_candidate_k": RERANK_CANDIDATE_K,
        "pdf": settings.pdf_path.name,
        "embedding_model": settings.embedding_model,
        "chunk_words": settings.chunk_words,
        "overlap_words": settings.overlap_words,
        "top_k": settings.top_k,
        "eval_split": settings.eval_split,
        "cases": metrics["cases"],
    }
    run_id, run_dir = create_run_dir(settings.runs_dir, pipeline, settings.eval_split)
    run_config["run_id"] = run_id
    run_config["environment"] = snapshot_environment(PROJECT_ROOT)
    write_evaluation_report(run_dir, metrics, predictions, run_config)
    with (run_dir / "rerank_traces.jsonl").open("w", encoding="utf-8") as stream:
        for trace in rerank_traces:
            stream.write(json.dumps(trace, ensure_ascii=False) + "\n")
    write_run_manifest(run_dir, {"run_config": run_config, "metrics": metrics})
    publish_latest(run_dir, settings.report_dir)
    append_history(
        PROJECT_ROOT / "reports" / "experiment_history.csv",
        run_id,
        pipeline,
        settings.eval_split,
        metrics,
        run_dir,
    )

    print("\nHybrid RRF + LLM reranker results")
    print(f"Hit rate@{settings.top_k}: {metrics['hit_rate_at_k']:.3f}")
    print(f"Mean Recall@{settings.top_k}: {metrics['mean_recall_at_k']:.3f}")
    print(f"MRR: {metrics['mrr']:.3f}")
    print(f"Run ID: {run_id}")
    print(f"Immutable run directory: {run_dir}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise
