from pathlib import Path
import sys


def bootstrap_langgraph_namespace(repo_root: Path | None = None) -> Path:
    """
    Make `import langgraph...` work from a monorepo checkout (no pip install).

    Why this exists:
    - In this repo, `langgraph` is spread across multiple `libs/*` folders.
    - When you run a single script directly, Python doesn't automatically know those paths.
    - So we add the relevant `libs/*` roots to `sys.path`.

    You only need this for scripts that import `langgraph.*`.
    """
    if repo_root is None:
        # file: library_mastery/00_COOKBOOK/_bootstrap.py
        # parents[0] = 00_COOKBOOK
        # parents[1] = library_mastery
        # parents[2] = repo root
        repo_root = Path(__file__).resolve().parents[2]

    lib_roots = [
        "libs/langgraph",
        "libs/checkpoint",
        "libs/prebuilt",
        "libs/checkpoint-sqlite",
        "libs/checkpoint-postgres",
    ]

    for rel in lib_roots:
        path = repo_root / rel
        if path.exists():
            sys.path.insert(0, str(path))

    return repo_root

