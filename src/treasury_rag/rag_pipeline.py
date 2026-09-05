from __future__ import annotations

from typing import Any

from .baseline import BaselineIndex, create_provider, retrieve
from .bm25 import BM25Index
from .config import Settings
from .hybrid import reciprocal_rank_fusion
from .models import SearchResult
from .multi_query import decompose_question, round_robin_unique
from .openai_provider import OpenAIProvider


class HybridRAGPipeline:
    def __init__(
        self,
        settings: Settings,
        *,
        retriever_candidate_k: int = 20,
        rerank_candidate_k: int = 12,
        rrf_k: int = 60,
    ) -> None:
        self.settings = settings
        self.index = BaselineIndex.load(settings.artifact_dir)
        self.bm25 = BM25Index(self.index.chunks)
        self.provider: OpenAIProvider = create_provider(settings)
        self.retriever_candidate_k = retriever_candidate_k
        self.rerank_candidate_k = rerank_candidate_k
        self.rrf_k = rrf_k

    def _retrieve_clause(
        self, clause: str, traces: list[dict[str, Any]]
    ) -> list[SearchResult]:
        dense_results = retrieve(
            clause,
            self.index,
            self.provider,
            self.retriever_candidate_k,
        )
        bm25_results = self.bm25.search(clause, self.retriever_candidate_k)
        fused = reciprocal_rank_fusion(
            [dense_results, bm25_results],
            top_k=self.rerank_candidate_k,
            rrf_k=self.rrf_k,
        )
        reranked, raw_output = self.provider.rerank(clause, fused)
        traces.append(
            {
                "clause": clause,
                "input_chunk_ids": [item.chunk.chunk_id for item in fused],
                "output_chunk_ids": [item.chunk.chunk_id for item in reranked],
                "raw_model_output": raw_output,
            }
        )
        return reranked

    def retrieve(
        self, question: str, top_k: int | None = None
    ) -> tuple[list[SearchResult], list[dict[str, Any]]]:
        top_k = top_k or self.settings.top_k
        traces: list[dict[str, Any]] = []
        clauses = decompose_question(question)
        if len(clauses) == 1:
            return self._retrieve_clause(question, traces)[:top_k], traces
        rankings = [self._retrieve_clause(question, traces)]
        rankings.extend(self._retrieve_clause(clause, traces) for clause in clauses)
        return round_robin_unique(rankings, top_k), traces

    def retrieve_fast(self, question: str, top_k: int | None = None) -> list[SearchResult]:
        """Hybrid retrieval without an LLM rerank, for interactive agent tools."""
        top_k = top_k or self.settings.top_k
        dense_results = retrieve(
            question,
            self.index,
            self.provider,
            self.retriever_candidate_k,
        )
        bm25_results = self.bm25.search(question, self.retriever_candidate_k)
        return reciprocal_rank_fusion(
            [dense_results, bm25_results],
            top_k=top_k,
            rrf_k=self.rrf_k,
        )

    def answer(
        self,
        question: str,
        top_k: int | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[str, list[SearchResult], list[dict[str, Any]]]:
        history = history or []
        search_question = self.provider.rewrite_for_retrieval(question, history)
        if search_question == "CONVERSATION_ONLY":
            return self.provider.answer(question, [], history), [], []
        results, traces = self.retrieve(search_question, top_k)
        contexts = [
            f"[PDF page {item.chunk.pdf_page}]\n{item.chunk.text}" for item in results
        ]
        answer = self.provider.answer(question, contexts, history)
        return answer, results, traces
