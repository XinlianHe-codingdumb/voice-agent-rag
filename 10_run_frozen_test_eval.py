from __future__ import annotations

import os
import runpy
from pathlib import Path


# Deliberately force the held-out split while reusing the frozen pipeline script.
# Do not edit the test questions or tune the pipeline after inspecting this run.
os.environ["RAG_EVAL_SPLIT"] = "test"
runpy.run_path(
    str(Path(__file__).resolve().parent / "09_run_llm_reranker_eval.py"),
    run_name="__main__",
)
