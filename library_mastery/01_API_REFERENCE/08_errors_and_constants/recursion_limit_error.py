from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner


def main() -> None:
    bootstrap_langgraph_namespace()

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
        .add_edge("loop", "loop")
        .compile()
    )

    banner("GraphRecursionError example")
    try:
        graph.invoke({"n": 0}, {"recursion_limit": 3})
    except GraphRecursionError as e:
        print("Caught:", type(e).__name__)
        print("Message first line:", str(e).splitlines()[0])


if __name__ == "__main__":
    main()

