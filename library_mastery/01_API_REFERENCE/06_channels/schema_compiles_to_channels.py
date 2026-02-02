from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from typing import Annotated, TypedDict

    from langgraph.graph import END, START, StateGraph

    def append(left: list[str], right: list[str] | None) -> list[str]:
        return left + (right or [])

    class State(TypedDict):
        x: int
        events: Annotated[list[str], append]

    def node(state: State) -> State:
        return {"x": state["x"] + 1, "events": [f"saw {state['x']}"]}

    graph = (
        StateGraph(State)
        .add_node("node", node)
        .add_edge(START, "node")
        .add_edge("node", END)
        .compile()
    )

    banner("Compiled channel types")
    for key in ("x", "events"):
        ch = graph.channels[key]
        print(f"{key}: {type(ch).__name__}")

    banner("Run")
    out = graph.invoke({"x": 1, "events": []})
    show("output", out)


if __name__ == "__main__":
    main()

