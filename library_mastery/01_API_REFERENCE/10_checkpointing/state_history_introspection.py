from __future__ import annotations

from pathlib import Path
import uuid
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from typing import TypedDict

    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph

    class State(TypedDict):
        n: int

    def step_a(state: State) -> State:
        return {"n": state["n"] + 1}

    def step_b(state: State) -> State:
        return {"n": state["n"] * 10}

    graph = (
        StateGraph(State)
        .add_node("a", step_a)
        .add_node("b", step_b)
        .add_edge(START, "a")
        .add_edge("a", "b")
        .add_edge("b", END)
        .compile(checkpointer=InMemorySaver())
    )

    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}}

    banner("invoke()")
    out = graph.invoke({"n": 1}, cfg)
    show("output", out)

    banner("get_state() (latest snapshot)")
    snap = graph.get_state(cfg)
    show("values", snap.values)
    show("next", snap.next)
    show("metadata", snap.metadata)

    banner("get_state_history() (oldest → newest)")
    for s in graph.get_state_history(cfg):
        step = None if s.metadata is None else s.metadata.get("step")
        print({"step": step, "next": s.next, "values": s.values})


if __name__ == "__main__":
    main()

