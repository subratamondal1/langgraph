from __future__ import annotations

from pathlib import Path
import uuid
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.func import entrypoint

    @entrypoint(checkpointer=InMemorySaver())
    def counter(_: int, *, previous: int | None = None) -> int:
        # `previous` is the last return value for this thread_id (if any).
        return (previous or 0) + 1

    thread_id = uuid.uuid4()
    config = {"configurable": {"thread_id": thread_id}}

    banner("First invocation (no previous yet)")
    show("result", counter.invoke(0, config))

    banner("Second invocation (previous injected from checkpoint)")
    show("result", counter.invoke(0, config))


if __name__ == "__main__":
    main()
