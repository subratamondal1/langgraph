from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace


def main() -> None:
    bootstrap_langgraph_namespace()

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
