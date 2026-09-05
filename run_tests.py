from __future__ import annotations

import subprocess
import sys
import shutil
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "tests"],
        cwd=root,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(completed.returncode)
    node = shutil.which("node")
    if not node:
        print("Node.js not found; browser turn-policy tests were skipped.")
        raise SystemExit(0)
    browser_tests = subprocess.run(
        [node, "--test", "tests/test_realtime_turns.js", "tests/test_document_access.js", "tests/test_recorder_composer.js"],
        cwd=root,
        check=False,
    )
    raise SystemExit(browser_tests.returncode)


if __name__ == "__main__":
    main()
