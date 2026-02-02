from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from typing import TypedDict

    from langgraph.cache.memory import InMemoryCache
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import CachePolicy

    calls = {"count": 0}

    class State(TypedDict):
        x: int
        y: int

    def expensive(state: State) -> State:
        calls["count"] += 1
        return {"y": state["x"] * 10}

    cache = InMemoryCache()

    graph = (
        StateGraph(State)
        .add_node("expensive", expensive, cache_policy=CachePolicy())
        .add_edge(START, "expensive")
        .add_edge("expensive", END)
        .compile(cache=cache)
    )

    banner("First invoke (computes)")
    show("output", graph.invoke({"x": 2, "y": 0}))
    show("calls", calls)

    banner("Second invoke with same input (cached)")
    show("output", graph.invoke({"x": 2, "y": 0}))
    show("calls", calls)

    banner("Different input (computes again)")
    show("output", graph.invoke({"x": 3, "y": 0}))
    show("calls", calls)


if __name__ == "__main__":
    main()

