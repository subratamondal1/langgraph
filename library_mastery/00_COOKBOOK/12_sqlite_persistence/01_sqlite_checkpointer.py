from pathlib import Path
import sys
from typing import TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("01 — SQLite checkpointer (durable state by thread_id)")

bootstrap_langgraph_namespace()

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.constants import START
from langgraph.graph import StateGraph


class State(TypedDict):
    n: int


def add_one(state: State) -> State:
    return {"n": state["n"] + 1}


scratch = COOKBOOK_ROOT / "_scratch"
scratch.mkdir(parents=True, exist_ok=True)
db_path = scratch / "checkpoints.db"

thread_id = "thread-demo-1"
config = {"configurable": {"thread_id": thread_id}}


with SqliteSaver.from_conn_string(str(db_path)) as checkpointer:
    graph = (
        StateGraph(State)
        .add_node("add_one", add_one)
        .add_edge(START, "add_one")
        .compile(checkpointer=checkpointer)
    )

    step("First run (writes checkpoint)")
    out1 = graph.invoke({"n": 0}, config)
    show("out1", out1)

    step("Second run (same thread_id) (writes another checkpoint)")
    out2 = graph.invoke({"n": out1["n"]}, config)
    show("out2", out2)

    step("Load the latest saved snapshot for this thread_id")
    snap = graph.get_state(config)
    show("snapshot.values", snap.values)
    show("snapshot.metadata", snap.metadata)

