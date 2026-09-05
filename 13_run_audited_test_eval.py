from __future__ import annotations

import os
import runpy
from pathlib import Path


# Post-hoc audit only: the test labels were already inspected after Run 012.
# This must not be presented as a fresh held-out estimate.
os.environ["RAG_EVAL_SPLIT"] = "test"
runpy.run_path(
    str(Path(__file__).resolve().parent / "11_run_multi_query_eval.py"),
    run_name="__main__",
)
