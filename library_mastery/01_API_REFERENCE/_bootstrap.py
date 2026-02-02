from __future__ import annotations

from pathlib import Path
import sys


def bootstrap_langgraph_namespace(*, repo_root: Path | None = None) -> Path:
    """Make `langgraph` imports work from a monorepo checkout (no installation).

    This repo uses a PEP 420 namespace package assembled from multiple `libs/*`
    distributions. When you're running an example script directly, Python won't
    automatically know about those `libs/` roots.

    This helper adds the relevant `libs/*` directories to `sys.path`.

    Returns:
        The repo root path.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]

    # Minimal set to cover `langgraph.*` surfaces described in 01_API_REFERENCE.md.
    # (We intentionally avoid adding every `libs/*` unless needed.)
    lib_roots = (
        "libs/langgraph",
        "libs/checkpoint",
        "libs/prebuilt",
        "libs/checkpoint-sqlite",
        "libs/checkpoint-postgres",
    )

    for rel in lib_roots:
        path = repo_root / rel
        if path.exists():
            sys.path.insert(0, str(path))

    return repo_root

