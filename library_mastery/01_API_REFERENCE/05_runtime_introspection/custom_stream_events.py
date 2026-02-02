from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner


def main() -> None:
    bootstrap_langgraph_namespace()

    from typing import TypedDict

    from langgraph.config import get_stream_writer
    from langgraph.graph import END, START, StateGraph

    class State(TypedDict):
        n: int

    def tick(state: State) -> State:
        writer = get_stream_writer()
        writer({"event": "tick", "n": state["n"]})
        return {"n": state["n"] + 1}

    graph = (
        StateGraph(State)
        .add_node("tick", tick)
        .add_edge(START, "tick")
        .add_edge("tick", END)
        .compile()
    )

    banner("stream(mode='custom') consumes StreamWriter events")
    for chunk in graph.stream({"n": 1}, stream_mode="custom"):
        print(chunk)


if __name__ == "__main__":
    main()

