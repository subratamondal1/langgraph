from __future__ import annotations

from pathlib import Path
import sys
import time
from typing import TypedDict

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


class State(TypedDict):
    x: int
    y: int


def recipe_cache_direct() -> None:
    from langgraph.cache.memory import InMemoryCache

    cache = InMemoryCache()

    banner("Cache: direct set/get (namespace + key)")
    cache.set({(("demo",), "k1"): ({"v": 123}, None)})
    show("get", cache.get([(("demo",), "k1")]))

    banner("Cache: TTL expiry")
    cache.set({(("demo",), "k2"): ({"v": "short"}, 1)})
    show("immediate", cache.get([(("demo",), "k2")]))
    time.sleep(1.1)
    show("expired", cache.get([(("demo",), "k2")]))


def recipe_cache_in_graph_node() -> None:
    from langgraph.cache.memory import InMemoryCache
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import CachePolicy

    calls = {"count": 0}

    def expensive(state: State) -> State:
        calls["count"] += 1
        return {"y": state["x"] * 10}

    graph = (
        StateGraph(State)
        .add_node("expensive", expensive, cache_policy=CachePolicy())
        .add_edge(START, "expensive")
        .add_edge("expensive", END)
        .compile(cache=InMemoryCache())
    )

    banner("CachePolicy: first invoke computes")
    show("out1", graph.invoke({"x": 2, "y": 0}))
    show("calls", calls)

    banner("CachePolicy: second invoke hits cache (same input)")
    show("out2", graph.invoke({"x": 2, "y": 0}))
    show("calls", calls)


def main() -> None:
    bootstrap_langgraph_namespace()
    recipe_cache_direct()
    recipe_cache_in_graph_node()


if __name__ == "__main__":
    main()

