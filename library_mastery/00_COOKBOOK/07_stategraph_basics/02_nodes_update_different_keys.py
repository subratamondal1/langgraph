from pathlib import Path
import sys
from typing import TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("02 — Nodes can update different keys in the same State dict")

bootstrap_langgraph_namespace()

from langgraph.graph import END, START, StateGraph


class State(TypedDict, total=False):
    a: int
    b: int


def set_a(_: State) -> State:
    return {"a": 1}


def set_b(_: State) -> State:
    return {"b": 2}


builder = StateGraph(State)
builder.add_node("set_a", set_a)
builder.add_node("set_b", set_b)
builder.add_edge(START, "set_a")
builder.add_edge("set_a", "set_b")
builder.add_edge("set_b", END)
graph = builder.compile()

step("Input state can be empty because our nodes fill it")
out = graph.invoke({})
show("out", out)

