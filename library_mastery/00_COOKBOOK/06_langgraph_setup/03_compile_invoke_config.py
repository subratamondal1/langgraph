from pathlib import Path
import sys
import uuid
from typing import TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("03 — compile(), invoke(), and config (thread_id)")

bootstrap_langgraph_namespace()

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    n: int


def plus_one(state: State) -> State:
    return {"n": state["n"] + 1}


builder = StateGraph(State)
builder.add_node("plus_one", plus_one)
builder.add_edge(START, "plus_one")
builder.add_edge("plus_one", END)
graph = builder.compile()

step("1) A config is just a dict (used for things like persistence keys)")
config = {"configurable": {"thread_id": str(uuid.uuid4())}}
show("config", config)

step("2) invoke(input, config)")
out = graph.invoke({"n": 1}, config)
show("out", out)

