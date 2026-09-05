from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def create_run_dir(runs_dir: Path, pipeline: str, split: str) -> tuple[str, Path]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{timestamp}_{_slug(pipeline)}_{_slug(split)}"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


def snapshot_environment(project_root: Path) -> dict[str, Any]:
    packages = {}
    for name in ("numpy", "openai", "pypdf", "python-dotenv"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
        "code_fingerprint": code_fingerprint(project_root),
    }


def code_fingerprint(project_root: Path) -> str:
    digest = hashlib.sha256()
    paths = sorted((project_root / "src").rglob("*.py"))
    paths += sorted(project_root.glob("*.py"))
    paths += [project_root / "pyproject.toml", project_root / "eval" / "gold_retrieval.jsonl"]
    for path in paths:
        if path.exists():
            digest.update(str(path.relative_to(project_root)).encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def publish_latest(run_dir: Path, latest_dir: Path) -> None:
    # Avoid deleting the directory: on Windows, a browser or editor may hold a
    # handle to it. The immutable run directory is the source of truth; latest
    # is only a convenience mirror whose standard files can be overwritten.
    shutil.copytree(run_dir, latest_dir, dirs_exist_ok=True)


def append_history(
    history_path: Path,
    run_id: str,
    pipeline: str,
    split: str,
    metrics: dict[str, Any],
    run_dir: Path,
) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    exists = history_path.exists()
    if exists:
        with history_path.open("r", encoding="utf-8-sig", newline="") as stream:
            if any(row.get("run_id") == run_id for row in csv.DictReader(stream)):
                return
    with history_path.open("a", encoding="utf-8-sig", newline="") as stream:
        fieldnames = [
            "run_id",
            "pipeline",
            "split",
            "cases",
            "top_k",
            "hit_rate_at_k",
            "mean_recall_at_k",
            "mrr",
            "run_dir",
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(
            {
                "run_id": run_id,
                "pipeline": pipeline,
                "split": split,
                "cases": metrics["cases"],
                "top_k": metrics["top_k"],
                "hit_rate_at_k": f"{metrics['hit_rate_at_k']:.6f}",
                "mean_recall_at_k": f"{metrics['mean_recall_at_k']:.6f}",
                "mrr": f"{metrics['mrr']:.6f}",
                "run_dir": str(run_dir),
            }
        )


def write_run_manifest(run_dir: Path, value: dict[str, Any]) -> None:
    (run_dir / "run_manifest.json").write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _slug(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value).strip("-")
