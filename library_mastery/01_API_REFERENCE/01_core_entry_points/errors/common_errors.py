from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace


def demo_recursion_limit() -> None:
    from typing import TypedDict

    from langgraph.errors import GraphRecursionError
    from langgraph.graph import START, StateGraph

    class State(TypedDict):
        n: int

    def loop(state: State) -> State:
        return {"n": state["n"] + 1}

    graph = (
        StateGraph(State)
        .add_node("loop", loop)
        .add_edge(START, "loop")
        .add_edge("loop", "loop")  # cycle!
        .compile()
    )

    try:
        graph.invoke({"n": 0}, {"recursion_limit": 3})
    except GraphRecursionError as e:
        print("Caught GraphRecursionError:", type(e).__name__)


def demo_invalid_concurrent_update() -> None:
    from typing import TypedDict

    from langgraph.errors import InvalidUpdateError
    from langgraph.graph import END, START, StateGraph

    class State(TypedDict):
        x: int

    def a(_: State) -> State:
        return {"x": 1}

    def b(_: State) -> State:
        return {"x": 2}

    graph = (
        StateGraph(State)
        .add_node("a", a)
        .add_node("b", b)
        # Both run in the first step:
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )

    try:
        graph.invoke({"x": 0})
    except InvalidUpdateError as e:
        print("Caught InvalidUpdateError (two writers, no reducer).")
        print(str(e).splitlines()[0])


def main() -> None:
    bootstrap_langgraph_namespace()
    demo_recursion_limit()
    demo_invalid_concurrent_update()


if __name__ == "__main__":
    main()
