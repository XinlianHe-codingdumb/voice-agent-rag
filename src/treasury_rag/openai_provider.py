from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .models import SearchResult
from .judging import parse_json_object
from .reranking import extract_ranked_ids, reorder_results
from .voice import validate_transcript


class OpenAIProvider:
    def __init__(
        self,
        api_key: str,
        embedding_model: str,
        chat_model: str,
        asr_model: str = "gpt-4o-transcribe",
        tts_model: str = "gpt-4o-mini-tts",
        tts_voice: str = "alloy",
        embedding_batch_size: int = 64,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The openai package is not installed. Run setup.ps1 or "
                "python -m pip install -e \".[dev]\"."
            ) from exc

        self.client = OpenAI(api_key=api_key)
        self.embedding_model = embedding_model
        self.chat_model = chat_model
        self.asr_model = asr_model
        self.tts_model = tts_model
        self.tts_voice = tts_voice
        self.embedding_batch_size = embedding_batch_size

    def embed(self, texts: Sequence[str], *, show_progress: bool = False) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)

        vectors: list[list[float]] = []
        total_batches = (len(texts) + self.embedding_batch_size - 1) // self.embedding_batch_size
        for batch_number, start in enumerate(
            range(0, len(texts), self.embedding_batch_size), start=1
        ):
            batch = list(texts[start : start + self.embedding_batch_size])
            if show_progress:
                print(f"Embedding batch {batch_number}/{total_batches} ({len(batch)} texts)")
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=batch,
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend(item.embedding for item in ordered)

        matrix = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.clip(norms, 1e-12, None)

    def answer(
        self,
        question: str,
        contexts: Sequence[str],
        history: Sequence[dict[str, str]] = (),
        memories: Sequence[dict[str, object]] = (),
    ) -> str:
        joined_context = "\n\n".join(contexts)
        joined_history = self._format_history(history)
        joined_memories = "\n".join(
            f"- [{item.get('category', 'memory')}] {item.get('content', '')}"
            for item in memories
        )
        instructions = (
            "You answer questions only from the supplied document excerpts. "
            "Use conversation history to resolve follow-up references and to answer questions "
            "about what the user or assistant previously said. Conversation history is not "
            "evidence for facts about the documents. "
            "Do not use outside knowledge. If the excerpts do not support an answer, say "
            "exactly: 'I could not find enough evidence in the report.' Cite every factual "
            "document claim using the citation labels already present in the excerpts. "
            "Long-term memory contains user-approved background and preferences, not document "
            "evidence. Use it for personalization, but the latest user message wins if they "
            "conflict. Conversation-only answers do not need PDF citations. Be concise."
        )
        prompt = (
            f"Long-term user memory:\n{joined_memories or '(none)'}\n\n"
            f"Conversation history:\n{joined_history or '(none)'}\n\n"
            f"Question:\n{question}\n\nDocument excerpts:\n{joined_context or '(none)'}"
        )
        response = self.client.responses.create(
            model=self.chat_model,
            instructions=instructions,
            input=prompt,
        )
        text = getattr(response, "output_text", None)
        if not text:
            raise RuntimeError("The model returned no text output.")
        return text.strip()

    def answer_conversation(
        self,
        question: str,
        history: Sequence[dict[str, str]] = (),
        memories: Sequence[dict[str, object]] = (),
    ) -> str:
        """Answer conversational control and history turns without document constraints."""
        joined_memories = "\n".join(
            f"- [{item.get('category', 'memory')}] {item.get('content', '')}"
            for item in memories
        )
        instructions = (
            "You are a concise conversational voice agent. This turn was classified by the "
            "application as conversation, not a request for document facts. Answer naturally "
            "using recent conversation history and user-approved memory when relevant. Do not "
            "search documents, invent document claims, or add PDF citations. If the user asks "
            "whether you can hear them, confirm that their speech was received. Keep the answer "
            "under 80 words unless they ask for more detail."
        )
        prompt = (
            f"Long-term user memory:\n{joined_memories or '(none)'}\n\n"
            f"Conversation history:\n{self._format_history(history) or '(none)'}\n\n"
            f"Latest user turn:\n{question}"
        )
        response = self.client.responses.create(
            model=self.chat_model,
            instructions=instructions,
            input=prompt,
        )
        text = getattr(response, "output_text", None)
        if not text:
            raise RuntimeError("The conversational responder returned no text output.")
        return text.strip()

    def summarize_conversation(self, messages: Sequence[dict[str, str]]) -> str:
        """Create a compact, durable handoff for one completed chat."""
        transcript = self._format_history(messages)
        instructions = (
            "Summarize this user-assistant conversation for future continuity. "
            "Write 4-7 concise bullet points covering the user's goal, decisions, "
            "important document findings or citations mentioned, and useful next steps. "
            "Do not invent facts, do not expose hidden reasoning, and omit greetings. "
            "Use the language used most by the user. Keep it under 180 words."
        )
        response = self.client.responses.create(
            model=self.chat_model,
            instructions=instructions,
            input=f"Conversation transcript:\n{transcript}",
        )
        text = getattr(response, "output_text", None)
        if not text:
            raise RuntimeError("The conversation summarizer returned no text output.")
        return text.strip()

    def rewrite_for_retrieval(
        self, question: str, history: Sequence[dict[str, str]]
    ) -> str:
        if not history:
            return question
        instructions = (
            "Rewrite the latest user question as a standalone document-search query using the "
            "conversation history. Preserve exact entities, dates, and numbers. If the latest "
            "question only asks about the conversation itself (for example, what the user just "
            "asked), return exactly CONVERSATION_ONLY. Return only the query or that sentinel."
        )
        response = self.client.responses.create(
            model=self.chat_model,
            instructions=instructions,
            input=(
                f"Conversation history:\n{self._format_history(history)}\n\n"
                f"Latest question:\n{question}"
            ),
        )
        text = getattr(response, "output_text", None)
        if not text:
            raise RuntimeError("The query rewriter returned no text output.")
        return text.strip()

    def rerank(
        self, question: str, candidates: Sequence[SearchResult]
    ) -> tuple[list[SearchResult], str]:
        candidate_text = "\n\n".join(
            f"CHUNK_ID: {item.chunk.chunk_id}\n"
            f"DOCUMENT: {item.chunk.document_name or '(single document)'}\n"
            f"PDF_PAGE: {item.chunk.pdf_page}\n"
            f"TEXT:\n{item.chunk.text}"
            for item in candidates
        )
        instructions = (
            "You are a retrieval reranker. Rank the supplied report chunks by how directly "
            "they contain evidence needed to answer the question. Pay special attention to "
            "the exact entity, reporting period, accounting scope, metric, and units. Do not "
            "answer the question and do not use outside knowledge. Return only CHUNK_ID values, "
            "one per line, most relevant first. Include every supplied CHUNK_ID exactly once."
        )
        response = self.client.responses.create(
            model=self.chat_model,
            instructions=instructions,
            input=f"QUESTION:\n{question}\n\nCANDIDATES:\n{candidate_text}",
        )
        raw_text = getattr(response, "output_text", None)
        if not raw_text:
            raise RuntimeError("The reranker returned no text output.")
        allowed_ids = [item.chunk.chunk_id for item in candidates]
        ranked_ids = extract_ranked_ids(raw_text, allowed_ids)
        return reorder_results(candidates, ranked_ids), raw_text.strip()

    def judge_answer(
        self,
        *,
        question: str,
        reference_answer: str,
        candidate_answer: str,
        contexts: Sequence[str],
        answerable: bool,
    ) -> tuple[dict[str, object], str]:
        instructions = (
            "You are a strict RAG evaluator. Use only the supplied evidence and reference. "
            "Return one JSON object and no markdown with keys: correctness (0, 1, or 2), "
            "faithfulness (0, 1, or 2), unanswerable_handling (true, false, or null), and "
            "reason (short string). Correctness: 2 fully matches the reference, 1 partially, "
            "0 wrong or missing. Faithfulness: 2 every factual claim is supported, 1 minor "
            "unsupported detail, 0 major unsupported claim. For an unanswerable question, "
            "correctness is 2 only when the candidate clearly refuses due to insufficient "
            "report evidence; set unanswerable_handling accordingly. For answerable questions "
            "set unanswerable_handling to null."
        )
        evidence = "\n\n".join(contexts)
        prompt = (
            f"ANSWERABLE: {str(answerable).lower()}\n"
            f"QUESTION: {question}\n"
            f"REFERENCE: {reference_answer}\n"
            f"CANDIDATE: {candidate_answer}\n\n"
            f"EVIDENCE:\n{evidence}"
        )
        response = self.client.responses.create(
            model=self.chat_model,
            instructions=instructions,
            input=prompt,
        )
        raw_text = getattr(response, "output_text", None)
        if not raw_text:
            raise RuntimeError("The answer judge returned no text output.")
        return parse_json_object(raw_text), raw_text.strip()

    def transcribe(
        self, audio: bytes, filename: str, content_type: str | None = None,
        language: str = "en",
    ) -> str:
        file_value = (filename, audio, content_type or "application/octet-stream")
        response = self.client.audio.transcriptions.create(
            model=self.asr_model,
            file=file_value,
            response_format="json",
            temperature=0,
            **({"language": language} if language != "auto" else {}),
        )
        text = response if isinstance(response, str) else getattr(response, "text", None)
        return validate_transcript(text)

    def synthesize(self, text: str) -> bytes:
        response = self.client.audio.speech.create(
            model=self.tts_model,
            voice=self.tts_voice,
            input=text,
            response_format="mp3",
        )
        return response.content

    @staticmethod
    def _format_history(history: Sequence[dict[str, str]]) -> str:
        return "\n".join(
            f"{message.get('role', 'unknown').upper()}: {message.get('content', '')}"
            for message in history
        )
