from __future__ import annotations

from pathlib import Path
import sys
import uuid
from typing import Optional, TypedDict

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


class State(TypedDict):
    n: int


class InterruptState(TypedDict):
    question: str
    answer: Optional[str]


def recipe_checkpoint_state_history() -> None:
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph

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

    banner("Checkpointing: invoke() with thread_id")
    show("output", graph.invoke({"n": 1}, cfg))

    banner("Checkpointing: get_state() snapshot")
    snap = graph.get_state(cfg)
    show("values", snap.values)
    show("metadata", snap.metadata)

    banner("Checkpointing: get_state_history() (oldest → newest)")
    history = list(graph.get_state_history(cfg))
    show("steps", [h.metadata.get("step") if h.metadata else None for h in history])


def recipe_interrupt_and_resume() -> None:
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.constants import START
    from langgraph.graph import StateGraph
    from langgraph.types import Command, interrupt

    def ask(state: InterruptState) -> InterruptState:
        answer = interrupt({"question": state["question"]})
        return {"answer": str(answer)}

    graph = (
        StateGraph(InterruptState)
        .add_node("ask", ask)
        .add_edge(START, "ask")
        .compile(checkpointer=InMemorySaver())
    )

    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}}

    banner("Interrupt: stream until __interrupt__ event")
    for chunk in graph.stream({"question": "approve deploy?", "answer": None}, cfg):
        print(chunk)

    banner("Interrupt: inspect snapshot.interrupts before resuming")
    snap = graph.get_state(cfg)
    show("interrupts", snap.interrupts)

    banner("Interrupt: resume with Command(resume=...)")
    for chunk in graph.stream(Command(resume="yes"), cfg):
        print(chunk)


def main() -> None:
    bootstrap_langgraph_namespace()
    recipe_checkpoint_state_history()
    recipe_interrupt_and_resume()


if __name__ == "__main__":
    main()

