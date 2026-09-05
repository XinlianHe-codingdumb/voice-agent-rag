from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from treasury_rag.config import Settings  # noqa: E402
from treasury_rag.io import write_json  # noqa: E402
from treasury_rag.pdf import inspect_pdf  # noqa: E402


def main() -> None:
    settings = Settings.load()
    inspection = inspect_pdf(settings.pdf_path)
    output_path = Path(__file__).resolve().parent / "artifacts" / "pdf_inspection.json"
    write_json(output_path, asdict(inspection))

    print(f"PDF: {inspection.path}")
    print(f"Pages: {inspection.pages}")
    print(
        f"Text coverage: {inspection.pages_with_text}/{inspection.pages} "
        f"({inspection.text_coverage:.1%})"
    )
    print(f"Extracted characters: {inspection.total_characters:,}")
    print(f"Bookmarks: {len(inspection.bookmarks)}")
    print("\nBookmark structure:")
    for item in inspection.bookmarks:
        indent = "  " * item["level"]
        print(f"{indent}- {item['title']} [PDF page {item['pdf_page']}]")
    print(f"\nFull JSON inspection written to {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

