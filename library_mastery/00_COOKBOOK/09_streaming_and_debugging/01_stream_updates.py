from pathlib import Path
import sys
from typing import TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("01 — stream(mode='updates') shows state updates per node")

bootstrap_langgraph_namespace()

from langgraph.graph import END, START, StateGraph


class State(TypedDict, total=False):
    x: int
    y: int


def compute_y(state: State) -> State:
    return {"y": state["x"] * 10}


def compute_z(state: State) -> State:
    return {"y": state["y"] + 1}


builder = StateGraph(State)
builder.add_node("compute_y", compute_y)
builder.add_node("compute_z", compute_z)
builder.add_edge(START, "compute_y")
builder.add_edge("compute_y", "compute_z")
builder.add_edge("compute_z", END)
graph = builder.compile()

step("Input")
show("input", {"x": 2})

step("Streaming updates")
for chunk in graph.stream({"x": 2}, stream_mode="updates"):
    print(chunk)

