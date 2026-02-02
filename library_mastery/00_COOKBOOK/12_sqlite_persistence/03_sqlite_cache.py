from pathlib import Path
import sys
import time
from typing import TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("03 — SQLite cache (avoid recomputing expensive nodes)")

bootstrap_langgraph_namespace()

from langgraph.cache.sqlite import SqliteCache
from langgraph.graph import END, START, StateGraph
from langgraph.types import CachePolicy


class State(TypedDict, total=False):
    x: int
    y: int


scratch = COOKBOOK_ROOT / "_scratch"
scratch.mkdir(parents=True, exist_ok=True)
cache_db = scratch / "cache.db"

cache = SqliteCache(path=str(cache_db))

calls = {"count": 0}


def expensive(state: State) -> State:
    calls["count"] += 1
    time.sleep(0.1)  # simulate slowness
    return {"y": state["x"] * 10}


graph = (
    StateGraph(State)
    .add_node("expensive", expensive, cache_policy=CachePolicy())
    .add_edge(START, "expensive")
    .add_edge("expensive", END)
    .compile(cache=cache)
)

step("First run computes")
out1 = graph.invoke({"x": 2})
show("out1", out1)
show("calls", calls)

step("Second run hits cache (same input)")
out2 = graph.invoke({"x": 2})
show("out2", out2)
show("calls", calls)

