from pathlib import Path
import sys
from typing import TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("02 — Loops and recursion_limit")

bootstrap_langgraph_namespace()

from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    n: int


def bump(state: State) -> State:
    return {"n": state["n"] + 1}


def keep_going(state: State) -> str:
    # Stop when n reaches 3
    return END if state["n"] >= 3 else "bump"


step("Part A) A safe loop that stops")
builder_ok = StateGraph(State)
builder_ok.add_node("bump", bump)
builder_ok.add_edge(START, "bump")
builder_ok.add_conditional_edges("bump", keep_going)
graph_ok = builder_ok.compile()

out_ok = graph_ok.invoke({"n": 0})
show("out_ok", out_ok)


step("Part B) A broken loop (no stop) -> GraphRecursionError")
def never_stop(_: State) -> str:
    return "bump"


builder_bad = StateGraph(State)
builder_bad.add_node("bump", bump)
builder_bad.add_edge(START, "bump")
builder_bad.add_conditional_edges("bump", never_stop)
graph_bad = builder_bad.compile()

try:
    graph_bad.invoke({"n": 0}, {"recursion_limit": 3})
except GraphRecursionError as e:
    print("\nCaught GraphRecursionError:")
    print(str(e).splitlines()[0])

