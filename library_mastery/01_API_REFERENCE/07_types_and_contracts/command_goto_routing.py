from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from typing import Annotated, Literal, TypedDict

    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command

    def append_path(left: list[str], right: list[str] | None) -> list[str]:
        return left + (right or [])

    class State(TypedDict):
        x: int
        path: Annotated[list[str], append_path]

    def router(state: State) -> Command[Literal["neg", "pos"]]:
        goto = "neg" if state["x"] < 0 else "pos"
        return Command(goto=goto, update={"path": ["router"]})

    def neg(state: State) -> State:
        return {"path": ["neg"], "x": state["x"] - 1}

    def pos(state: State) -> State:
        return {"path": ["pos"], "x": state["x"] + 1}

    graph = (
        StateGraph(State)
        .add_node("router", router, destinations=("neg", "pos"))
        .add_node("neg", neg)
        .add_node("pos", pos)
        .add_edge(START, "router")
        .add_edge("neg", END)
        .add_edge("pos", END)
        .compile()
    )

    banner("ASCII Graph (destinations affect rendering)")
    print(graph.get_graph().draw_ascii())

    banner("x < 0 routes to 'neg'")
    show("output", graph.invoke({"x": -2, "path": []}))

    banner("x >= 0 routes to 'pos'")
    show("output", graph.invoke({"x": 3, "path": []}))


if __name__ == "__main__":
    main()

