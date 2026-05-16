"""Allow examples to run from a source checkout without installation."""

from __future__ import annotations

import sys
from pathlib import Path


def add_src_to_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def print_runtime_error(exc: RuntimeError) -> int:
    print(f"error: {exc}", file=sys.stderr)
    print("hint: run poetry install from the repo root, then use poetry run", file=sys.stderr)
    return 1
