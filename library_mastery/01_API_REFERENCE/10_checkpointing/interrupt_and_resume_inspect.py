from __future__ import annotations

from pathlib import Path
import uuid
import sys
from typing import Optional

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from typing import TypedDict

    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.constants import START
    from langgraph.graph import StateGraph
    from langgraph.types import Command, interrupt

    class State(TypedDict):
        question: str
        answer: Optional[str]

    def ask(state: State) -> State:
        answer = interrupt({"question": state["question"]})
        return {"answer": answer}

    graph = (
        StateGraph(State)
        .add_node("ask", ask)
        .add_edge(START, "ask")
        .compile(checkpointer=InMemorySaver())
    )

    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}}

    banner("Run until interrupt")
    for chunk in graph.stream({"question": "What is your role?", "answer": None}, cfg):
        print(chunk)

    banner("Inspect checkpointed state before resume")
    snap = graph.get_state(cfg)
    show("values", snap.values)
    show("interrupts", snap.interrupts)

    banner("Resume with Command(resume=...)")
    for chunk in graph.stream(Command(resume="founding engineer"), cfg):
        print(chunk)

    banner("Inspect final state")
    show("final values", graph.get_state(cfg).values)


if __name__ == "__main__":
    main()
