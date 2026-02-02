from pathlib import Path
import sys
from typing import TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("02 — First StateGraph (single node)")

bootstrap_langgraph_namespace()

from langgraph.graph import END, START, StateGraph


step("1) Define the State shape (TypedDict)")
class State(TypedDict):
    count: int


step("2) Define a node function: (state) -> dict update")
def inc(state: State) -> State:
    print("Inside inc(...)")
    show("state (inside)", state)
    return {"count": state["count"] + 1}


step("3) Build the graph")
builder = StateGraph(State)
builder.add_node("inc", inc)
builder.add_edge(START, "inc")
builder.add_edge("inc", END)

step("4) Compile (turn builder into runnable graph)")
graph = builder.compile()

step("5) Invoke (run once with an input state)")
input_state = {"count": 0}
show("input_state", input_state)
output_state = graph.invoke(input_state)
show("output_state", output_state)

