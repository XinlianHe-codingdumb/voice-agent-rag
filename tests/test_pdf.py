from pathlib import Path

from treasury_rag.config import DEFAULT_PDF_PATH
from treasury_rag.pdf import inspect_pdf


def test_source_pdf_is_valid_long_form_document() -> None:
    inspection = inspect_pdf(Path(DEFAULT_PDF_PATH))

    assert inspection.pages == 300
    assert inspection.text_coverage > 0.95
    assert len(inspection.bookmarks) >= 10
    assert inspection.metadata.get("Author") == "HM Treasury"

