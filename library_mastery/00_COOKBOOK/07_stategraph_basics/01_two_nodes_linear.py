from pathlib import Path
import sys
from typing import TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("01 — Two nodes in a line: START -> a -> b -> END")

bootstrap_langgraph_namespace()

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    text: str


def add_hello(state: State) -> State:
    print("Inside add_hello(...)")
    show("state (inside)", state)
    return {"text": "hello " + state["text"]}


def add_exclamation(state: State) -> State:
    print("Inside add_exclamation(...)")
    show("state (inside)", state)
    return {"text": state["text"] + "!"}


builder = StateGraph(State)
builder.add_node("a", add_hello)
builder.add_node("b", add_exclamation)
builder.add_edge(START, "a")
builder.add_edge("a", "b")
builder.add_edge("b", END)
graph = builder.compile()

input_state = {"text": "world"}
show("input_state", input_state)
out = graph.invoke(input_state)
show("out", out)

