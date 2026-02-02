from pathlib import Path
import sys
from typing import Annotated, TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("01 — Conditional edges (route to different nodes)")

bootstrap_langgraph_namespace()

from langgraph.graph import END, START, StateGraph


def append(left: list[str], right: list[str] | None) -> list[str]:
    return left + (right or [])


class State(TypedDict, total=False):
    n: int
    parity: str
    result: str
    log: Annotated[list[str], append]


def classify(state: State) -> State:
    n = state["n"]
    parity = "even" if n % 2 == 0 else "odd"
    return {"parity": parity, "log": [f"classify(n={n}) -> {parity}"]}


def even_node(state: State) -> State:
    return {"result": f"{state['n']} is even", "log": ["even_node()"]}


def odd_node(state: State) -> State:
    return {"result": f"{state['n']} is odd", "log": ["odd_node()"]}


def route(state: State) -> str:
    # This decides which node runs next.
    return "even" if state["parity"] == "even" else "odd"


builder = StateGraph(State)
builder.add_node("classify", classify)
builder.add_node("even", even_node)
builder.add_node("odd", odd_node)
builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", route, {"even": "even", "odd": "odd"})
builder.add_edge("even", END)
builder.add_edge("odd", END)
graph = builder.compile()

input_state = {"n": 7, "log": []}
show("input_state", input_state)
out = graph.invoke(input_state)
show("out", out)

