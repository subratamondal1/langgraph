from __future__ import annotations

from pathlib import Path
import sys


def _bootstrap_langgraph_namespace() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    for rel in ("libs/langgraph", "libs/checkpoint", "libs/prebuilt"):
        sys.path.insert(0, str(repo_root / rel))


def main() -> None:
    _bootstrap_langgraph_namespace()

    from langgraph.constants import END, START, TAG_HIDDEN, TAG_NOSTREAM

    print("START:", START)
    print("END:", END)
    print("TAG_NOSTREAM:", TAG_NOSTREAM)
    print("TAG_HIDDEN:", TAG_HIDDEN)

    # Where tags often show up: RunnableConfig passed at invoke/stream time.
    example_config = {"tags": [TAG_HIDDEN, TAG_NOSTREAM]}
    print("Example config snippet:", example_config)


if __name__ == "__main__":
    main()

