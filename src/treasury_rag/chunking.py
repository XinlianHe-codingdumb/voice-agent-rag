from __future__ import annotations

from collections.abc import Iterable

from .models import Chunk, PageText


def chunk_pages(
    pages: Iterable[PageText], chunk_words: int, overlap_words: int
) -> list[Chunk]:
    if chunk_words <= 0:
        raise ValueError("chunk_words must be greater than zero")
    if overlap_words < 0 or overlap_words >= chunk_words:
        raise ValueError("overlap_words must be >= 0 and smaller than chunk_words")

    step = chunk_words - overlap_words
    chunks: list[Chunk] = []
    for page in pages:
        words = page.text.split()
        if not words:
            continue
        chunk_index = 0
        for start in range(0, len(words), step):
            end = min(start + chunk_words, len(words))
            text = " ".join(words[start:end]).strip()
            if not text:
                continue
            chunks.append(
                Chunk(
                    chunk_id=f"p{page.pdf_page:04d}-c{chunk_index:03d}",
                    pdf_page=page.pdf_page,
                    chunk_index=chunk_index,
                    text=text,
                    word_start=start,
                    word_end=end,
                )
            )
            chunk_index += 1
            if end >= len(words):
                break
    return chunks

