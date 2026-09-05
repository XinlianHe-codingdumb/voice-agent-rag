from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from treasury_rag.baseline import build_index  # noqa: E402
from treasury_rag.config import Settings  # noqa: E402


def main() -> None:
    settings = Settings.load()
    index = build_index(settings)
    print("\nBaseline index ready.")
    print(f"Chunks: {len(index.chunks)}")
    print(f"Vector dimensions: {index.vectors.shape[1]}")
    print(f"Artifacts: {settings.artifact_dir}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise

