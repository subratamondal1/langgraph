from pathlib import Path
import sys
from typing import TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import step, title


title("02 — stream(mode='tasks') shows execution tasks (lower level)")

bootstrap_langgraph_namespace()

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    text: str


def node1(state: State) -> State:
    return {"text": state["text"] + "!"}


def node2(state: State) -> State:
    return {"text": state["text"] + "?"}


builder = StateGraph(State)
builder.add_node("node1", node1)
builder.add_node("node2", node2)
builder.add_edge(START, "node1")
builder.add_edge("node1", "node2")
builder.add_edge("node2", END)
graph = builder.compile()

step("Streaming tasks")
for task_event in graph.stream({"text": "hi"}, stream_mode="tasks"):
    print(task_event)

