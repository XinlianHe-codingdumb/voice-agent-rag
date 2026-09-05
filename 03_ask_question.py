from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from treasury_rag.baseline import (  # noqa: E402
    BaselineIndex,
    answer_question,
    create_provider,
    retrieve,
)
from treasury_rag.config import Settings  # noqa: E402


def main() -> None:
    settings = Settings.load()
    index = BaselineIndex.load(settings.artifact_dir)
    provider = create_provider(settings)

    print("HM Treasury baseline RAG")
    print("Press Enter on an empty question to exit.\n")
    while True:
        question = input("Question: ").strip()
        if not question:
            break
        results = retrieve(question, index, provider, settings.top_k)
        print("\nRetrieved evidence:")
        for result in results:
            preview = result.chunk.text[:320]
            print(
                f"{result.rank}. PDF page {result.chunk.pdf_page} | "
                f"score={result.score:.4f}\n   {preview}..."
            )
        print("\nAnswer:")
        print(answer_question(question, results, provider))
        print()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise

