from __future__ import annotations

from pathlib import Path
import sys
from typing import Annotated

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def append(left: list[int], right: list[int] | None) -> list[int]:
    return left + (right or [])


def main() -> None:
    bootstrap_langgraph_namespace()

    from typing import TypedDict

    from langgraph.errors import InvalidUpdateError
    from langgraph.graph import END, START, StateGraph

    banner("InvalidUpdateError: two writers to a LastValue channel")

    class BadState(TypedDict):
        x: int

    def a(_: BadState) -> BadState:
        return {"x": 1}

    def b(_: BadState) -> BadState:
        return {"x": 2}

    bad = (
        StateGraph(BadState)
        .add_node("a", a)
        .add_node("b", b)
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )

    try:
        bad.invoke({"x": 0})
    except InvalidUpdateError as e:
        print("Caught:", type(e).__name__)
        print(str(e).splitlines()[0])

    banner("Fix: make the key reducible (list append)")

    class GoodState(TypedDict):
        xs: Annotated[list[int], append]

    def a2(_: GoodState) -> GoodState:
        return {"xs": [1]}

    def b2(_: GoodState) -> GoodState:
        return {"xs": [2]}

    good = (
        StateGraph(GoodState)
        .add_node("a", a2)
        .add_node("b", b2)
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )

    show("output", good.invoke({"xs": []}))


if __name__ == "__main__":
    main()
