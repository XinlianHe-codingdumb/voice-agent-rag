from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader

from .models import PageText
from .text import normalize_text, remove_report_boilerplate


@dataclass(frozen=True)
class Bookmark:
    level: int
    title: str
    pdf_page: int | None


@dataclass(frozen=True)
class PdfInspection:
    path: str
    pages: int
    encrypted: bool
    pages_with_text: int
    text_coverage: float
    total_characters: int
    metadata: dict[str, str]
    bookmarks: list[dict[str, Any]]


def inspect_pdf(path: Path) -> PdfInspection:
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    reader = PdfReader(str(path))
    page_character_counts = [len(normalize_text(page.extract_text() or "")) for page in reader.pages]
    pages_with_text = sum(count > 30 for count in page_character_counts)
    bookmarks = [asdict(item) for item in _flatten_outline(reader, reader.outline)]
    metadata = {
        str(key).lstrip("/"): normalize_text(str(value))
        for key, value in (reader.metadata or {}).items()
        if value is not None
    }
    return PdfInspection(
        path=str(path),
        pages=len(reader.pages),
        encrypted=reader.is_encrypted,
        pages_with_text=pages_with_text,
        text_coverage=pages_with_text / len(reader.pages) if reader.pages else 0.0,
        total_characters=sum(page_character_counts),
        metadata=metadata,
        bookmarks=bookmarks,
    )


def extract_pages(path: Path, *, clean_boilerplate: bool = False, ocr: bool = True,
                  extraction_trace: list | None = None) -> list[PageText]:
    reader = PdfReader(str(path))
    output: list[PageText] = []
    for index, page in enumerate(reader.pages):
        text = normalize_text(page.extract_text() or "")
        original_length = len(text)
        used_ocr = False
        if ocr and len(text) < 80:
            from .ocr import read_scanned_page
            try:
                scanned = normalize_text(read_scanned_page(path, index))
            except Exception as exc:
                raise RuntimeError(f"OCR failed on PDF page {index + 1}: {exc}") from exc
            if len(scanned) > len(text):
                text = scanned
                used_ocr = True
            print(f"OCR page {index + 1}: {len(text)} characters")
        if extraction_trace is not None:
            extraction_trace.append({"pdf_page": index + 1, "native_characters": original_length,
                                     "characters": len(text), "source": "ocr" if used_ocr else "text",
                                     "ocr_attempted": ocr and original_length < 80})
        if clean_boilerplate:
            text = remove_report_boilerplate(text)
        output.append(PageText(pdf_page=index + 1, text=text))
    return output


def _flatten_outline(
    reader: PdfReader, items: Iterable[Any], level: int = 0
) -> list[Bookmark]:
    output: list[Bookmark] = []
    for item in items:
        if isinstance(item, list):
            output.extend(_flatten_outline(reader, item, level + 1))
            continue
        try:
            page = reader.get_destination_page_number(item) + 1
        except Exception:
            page = None
        title = normalize_text(str(getattr(item, "title", item)))
        output.append(Bookmark(level=level, title=title, pdf_page=page))
    return output
