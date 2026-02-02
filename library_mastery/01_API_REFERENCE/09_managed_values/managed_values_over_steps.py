from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner

bootstrap_langgraph_namespace()

from typing import Annotated, TypedDict

from langgraph.errors import GraphRecursionError
from langgraph.graph import START, StateGraph
from langgraph.managed import IsLastStep, RemainingSteps


def append(left: list[str], right: list[str] | None) -> list[str]:
    return left + (right or [])


class State(TypedDict):
    remaining: RemainingSteps
    is_last: IsLastStep
    log: Annotated[list[str], append]


def observe(state: State) -> State:
    return {"log": [f"remaining={state['remaining']}, is_last={state['is_last']}"]}


def main() -> None:
    graph = (
        StateGraph(State)
        .add_node("observe", observe)
        .add_edge(START, "observe")
        .add_edge("observe", "observe")  # cycle to consume steps
        .compile()
    )

    banner("Streaming values until recursion limit is hit (watch managed values change)")
    try:
        for chunk in graph.stream({"log": []}, {"recursion_limit": 4}, stream_mode="values"):
            if chunk.get("log"):
                print(chunk["log"][-1])
            else:
                # First emitted value can be the initial state snapshot.
                print({"log": chunk.get("log")})
    except GraphRecursionError as e:
        print("Caught:", type(e).__name__)
        print(str(e).splitlines()[0])


if __name__ == "__main__":
    main()
