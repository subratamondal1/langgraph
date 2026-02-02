from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner

bootstrap_langgraph_namespace()

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.managed import IsLastStep, RemainingSteps


class State(TypedDict, total=False):
    remaining: RemainingSteps
    is_last: IsLastStep
    note: str


def observe(state: State) -> State:
    return {"note": f"remaining={state.get('remaining')}, is_last={state.get('is_last')}"}


def main() -> None:
    graph = (
        StateGraph(State)
        .add_node("observe", observe)
        .add_edge(START, "observe")
        .add_edge("observe", END)
        .compile()
    )

    banner("Managed values appear in state during execution")
    out = graph.invoke({"note": ""}, {"recursion_limit": 5})
    print(out["note"])


if __name__ == "__main__":
    main()

