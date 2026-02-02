from __future__ import annotations

from pathlib import Path
import operator
import sys
import uuid
from typing import Annotated, TypedDict

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


class FanOutState(TypedDict):
    subjects: list[str]
    jokes: Annotated[list[str], operator.add]


def append_path(left: list[str], right: list[str] | None) -> list[str]:
    return left + (right or [])


class GotoState(TypedDict):
    x: int
    path: Annotated[list[str], append_path]


class InterruptState(TypedDict):
    question: str
    answer: str | None


def recipe_send_fan_out() -> None:
    from langgraph.constants import END, START
    from langgraph.graph import StateGraph
    from langgraph.types import Send

    graph = (
        StateGraph(FanOutState)
        .add_node("joke", lambda state: {"jokes": [f"joke({state['subject']})"]})
        .add_conditional_edges(
            START,
            lambda state: [Send("joke", {"subject": s}) for s in state["subjects"]],
        )
        .add_edge("joke", END)
        .compile()
    )

    banner("Send fan-out")
    show("output", graph.invoke({"subjects": ["cats", "dogs"], "jokes": []}))


def recipe_command_goto() -> None:
    from langgraph.constants import END, START
    from langgraph.graph import StateGraph
    from langgraph.types import Command

    graph = (
        StateGraph(GotoState)
        .add_node(
            "router",
            lambda state: Command(
                goto="neg" if state["x"] < 0 else "pos", update={"path": ["router"]}
            ),
            destinations=("neg", "pos"),
        )
        .add_node("neg", lambda state: {"path": ["neg"], "x": state["x"] - 1})
        .add_node("pos", lambda state: {"path": ["pos"], "x": state["x"] + 1})
        .add_edge(START, "router")
        .add_edge("neg", END)
        .add_edge("pos", END)
        .compile()
    )

    banner("Command(goto=...) routing")
    show("x=-1", graph.invoke({"x": -1, "path": []}))
    show("x=1", graph.invoke({"x": 1, "path": []}))


def recipe_interrupt_resume() -> None:
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.constants import START
    from langgraph.graph import StateGraph
    from langgraph.types import Command, interrupt

    graph = (
        StateGraph(InterruptState)
        .add_node(
            "ask",
            lambda state: {
                "answer": str(interrupt({"question": state["question"]}))
            },
        )
        .add_edge(START, "ask")
        .compile(checkpointer=InMemorySaver())
    )

    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}}

    banner("interrupt + Command(resume=...)")
    for chunk in graph.stream({"question": "ship?", "answer": None}, cfg):
        print(chunk)
    for chunk in graph.stream(Command(resume="yes"), cfg):
        print(chunk)


def recipe_overwrite_in_aggregate() -> None:
    from langgraph.channels import BinaryOperatorAggregate
    from langgraph.types import Overwrite

    agg = BinaryOperatorAggregate(int, operator.add)
    agg.update([1, 2, 3])
    banner("Overwrite semantics")
    show("after add", agg.get())
    agg.update([Overwrite(10), 999])
    show("after overwrite", agg.get())


def main() -> None:
    bootstrap_langgraph_namespace()
    recipe_send_fan_out()
    recipe_command_goto()
    recipe_interrupt_resume()
    recipe_overwrite_in_aggregate()


if __name__ == "__main__":
    main()
