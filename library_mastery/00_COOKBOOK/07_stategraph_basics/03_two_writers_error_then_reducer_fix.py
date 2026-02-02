from pathlib import Path
import sys
from typing import Annotated, TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("03 — Two writers in the same step: error, then reducer fix")

bootstrap_langgraph_namespace()

from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph


def append(left: list[str], right: list[str] | None) -> list[str]:
    return left + (right or [])


step("Part A) The problem: two nodes write the same key 'log' in the same step")
class StateBad(TypedDict):
    log: list[str]


def node_a(_: StateBad) -> StateBad:
    return {"log": ["from A"]}


def node_b(_: StateBad) -> StateBad:
    return {"log": ["from B"]}


builder_bad = StateGraph(StateBad)
builder_bad.add_node("a", node_a)
builder_bad.add_node("b", node_b)

# Both nodes are triggered directly from START (same step).
builder_bad.add_edge(START, "a")
builder_bad.add_edge(START, "b")
builder_bad.add_edge("a", END)
builder_bad.add_edge("b", END)
graph_bad = builder_bad.compile()

try:
    graph_bad.invoke({"log": []})
except InvalidUpdateError as e:
    print("\nCaught InvalidUpdateError (this is a common beginner error):")
    print(str(e).splitlines()[0])


step("Part B) The fix: make the key reducible with Annotated[..., reducer]")
class StateGood(TypedDict):
    log: Annotated[list[str], append]


def node_a2(_: StateGood) -> StateGood:
    return {"log": ["from A"]}


def node_b2(_: StateGood) -> StateGood:
    return {"log": ["from B"]}


builder_good = StateGraph(StateGood)
builder_good.add_node("a", node_a2)
builder_good.add_node("b", node_b2)
builder_good.add_edge(START, "a")
builder_good.add_edge(START, "b")
builder_good.add_edge("a", END)
builder_good.add_edge("b", END)
graph_good = builder_good.compile()

out = graph_good.invoke({"log": []})
show("out", out)

