from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .chunking import chunk_pages
from .config import Settings
from .io import read_chunks, read_json, sha256_file, write_chunks, write_json
from .models import Chunk, SearchResult
from .openai_provider import OpenAIProvider
from .pdf import extract_pages


CHUNKS_FILENAME = "chunks.jsonl"
CHUNK_MANIFEST_FILENAME = "chunk_manifest.json"
VECTORS_FILENAME = "vectors.npy"
MANIFEST_FILENAME = "manifest.json"


class BaselineIndex:
    def __init__(self, chunks: list[Chunk], vectors: np.ndarray, manifest: dict) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Chunk and vector counts do not match")
        self.chunks = chunks
        self.vectors = vectors.astype(np.float32, copy=False)
        self.manifest = manifest

    @classmethod
    def load(cls, artifact_dir: Path) -> "BaselineIndex":
        chunks_path = artifact_dir / CHUNKS_FILENAME
        vectors_path = artifact_dir / VECTORS_FILENAME
        manifest_path = artifact_dir / MANIFEST_FILENAME
        missing = [
            str(path)
            for path in (chunks_path, vectors_path, manifest_path)
            if not path.exists()
        ]
        if missing:
            raise FileNotFoundError(
                "Baseline index is incomplete. Run 02_build_baseline_index.py first. "
                f"Missing: {', '.join(missing)}"
            )
        return cls(
            chunks=read_chunks(chunks_path),
            vectors=np.load(vectors_path),
            manifest=read_json(manifest_path),
        )

    def search(self, query_vector: np.ndarray, top_k: int) -> list[SearchResult]:
        query = np.asarray(query_vector, dtype=np.float32).reshape(-1)
        query /= max(float(np.linalg.norm(query)), 1e-12)
        if query.shape[0] != self.vectors.shape[1]:
            raise ValueError(
                f"Query dimension {query.shape[0]} does not match index dimension "
                f"{self.vectors.shape[1]}"
            )
        scores = self.vectors @ query
        top_k = min(top_k, len(scores))
        candidate_ids = np.argpartition(-scores, top_k - 1)[:top_k]
        ordered_ids = candidate_ids[np.argsort(-scores[candidate_ids])]
        return [
            SearchResult(
                rank=rank,
                score=float(scores[index]),
                chunk=self.chunks[int(index)],
            )
            for rank, index in enumerate(ordered_ids, start=1)
        ]


def create_provider(settings: Settings) -> OpenAIProvider:
    return OpenAIProvider(
        api_key=settings.require_api_key(),
        embedding_model=settings.embedding_model,
        chat_model=settings.chat_model,
        asr_model=settings.asr_model,
        tts_model=settings.tts_model,
        tts_voice=settings.tts_voice,
        embedding_batch_size=settings.embedding_batch_size,
    )


def build_index(settings: Settings, *, force: bool = False) -> BaselineIndex:
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = settings.artifact_dir / MANIFEST_FILENAME
    expected = {
        "pdf_sha256": sha256_file(settings.pdf_path),
        "embedding_model": settings.embedding_model,
        "chunk_words": settings.chunk_words,
        "overlap_words": settings.overlap_words,
    }
    if not force and manifest_path.exists():
        existing = read_json(manifest_path)
        if all(existing.get(key) == value for key, value in expected.items()):
            print("Cached baseline index matches the current document and settings.")
            return BaselineIndex.load(settings.artifact_dir)

    chunks = load_or_create_chunks(settings, force=force)

    provider = create_provider(settings)
    vectors = provider.embed([chunk.text for chunk in chunks], show_progress=True)
    manifest = {
        **expected,
        "pdf_path": str(settings.pdf_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "pages": max(chunk.pdf_page for chunk in chunks),
        "chunks": len(chunks),
        "vector_dimensions": int(vectors.shape[1]),
        "baseline": "page-local fixed-size chunks + dense cosine retrieval",
    }
    write_chunks(settings.artifact_dir / CHUNKS_FILENAME, chunks)
    np.save(settings.artifact_dir / VECTORS_FILENAME, vectors)
    write_json(manifest_path, manifest)
    return BaselineIndex(chunks, vectors, manifest)


def load_or_create_chunks(settings: Settings, *, force: bool = False) -> list[Chunk]:
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = settings.artifact_dir / CHUNKS_FILENAME
    manifest_path = settings.artifact_dir / CHUNK_MANIFEST_FILENAME
    expected = {
        "pdf_sha256": sha256_file(settings.pdf_path),
        "chunk_words": settings.chunk_words,
        "overlap_words": settings.overlap_words,
    }
    if not force and chunks_path.exists() and manifest_path.exists():
        existing = read_json(manifest_path)
        if all(existing.get(key) == value for key, value in expected.items()):
            print("Cached chunks match the current document and settings.")
            return read_chunks(chunks_path)

    print(f"Extracting text from {settings.pdf_path.name} ...")
    extraction_trace = []
    pages = extract_pages(settings.pdf_path, extraction_trace=extraction_trace)
    write_json(settings.artifact_dir / "extraction.json", {
        "parser": "pypdf + sparse-page RapidOCR 1.4.4", "ocr_threshold_characters": 80,
        "pages": extraction_trace,
    })
    chunks = chunk_pages(pages, settings.chunk_words, settings.overlap_words)
    if not chunks:
        raise RuntimeError("No text chunks were produced from the PDF")
    print(f"Created {len(chunks)} baseline chunks from {len(pages)} PDF pages.")
    write_chunks(chunks_path, chunks)
    write_json(
        manifest_path,
        {
            **expected,
            "pdf_path": str(settings.pdf_path),
            "pages": len(pages),
            "chunks": len(chunks),
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    return chunks


def retrieve(
    question: str,
    index: BaselineIndex,
    provider: OpenAIProvider,
    top_k: int,
) -> list[SearchResult]:
    query_vector = provider.embed([question])[0]
    return index.search(query_vector, top_k)


def answer_question(
    question: str,
    results: list[SearchResult],
    provider: OpenAIProvider,
) -> str:
    contexts = [
        f"[PDF page {result.chunk.pdf_page}]\n{result.chunk.text}"
        for result in results
    ]
    return provider.answer(question, contexts)
