from __future__ import annotations

from pathlib import Path
import uuid
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner


def main() -> None:
    bootstrap_langgraph_namespace()

    from typing import TypedDict

    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph

    class State(TypedDict):
        n: int

    def inc(state: State) -> State:
        return {"n": state["n"] + 1}

    graph = (
        StateGraph(State)
        .add_node("inc", inc)
        .add_edge(START, "inc")
        .add_edge("inc", END)
        .compile(checkpointer=InMemorySaver())
    )

    cfg = {"configurable": {"thread_id": uuid.uuid4()}}

    for mode in ("values", "updates", "tasks", "debug", "checkpoints"):
        banner(f"stream_mode={mode!r}")
        for chunk in graph.stream({"n": 1}, cfg, stream_mode=mode):  # type: ignore[arg-type]
            print(chunk)


if __name__ == "__main__":
    main()

