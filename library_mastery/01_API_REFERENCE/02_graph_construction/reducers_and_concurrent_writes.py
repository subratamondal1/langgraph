from __future__ import annotations

from pathlib import Path
import sys
from typing import Annotated

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def append(left: list[str], right: list[str] | None) -> list[str]:
    return left + (right or [])


def demo_error_two_writers() -> None:
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
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )

    banner("Two writers -> InvalidUpdateError")
    try:
        graph.invoke({"x": 0})
    except InvalidUpdateError as e:
        print("Caught:", type(e).__name__)
        print(str(e).splitlines()[0])


def demo_fix_with_reducer() -> None:
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph

    class State(TypedDict):
        events: Annotated[list[str], append]

    def a(_: State) -> State:
        return {"events": ["from a"]}

    def b(_: State) -> State:
        return {"events": ["from b"]}

    graph = (
        StateGraph(State)
        .add_node("a", a)
        .add_node("b", b)
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )

    banner("Same pattern, but reducer makes it safe")
    out = graph.invoke({"events": []})
    show("output", out)

    # Internal view: the state key compiled into a channel.
    channel = graph.channels.get("events")
    print("\nCompiled channel type for 'events':", type(channel).__name__)


def main() -> None:
    bootstrap_langgraph_namespace()
    demo_error_two_writers()
    demo_fix_with_reducer()


if __name__ == "__main__":
    main()
