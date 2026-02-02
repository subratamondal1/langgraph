from __future__ import annotations

from pathlib import Path
import sys


def _bootstrap_langgraph_namespace() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    for rel in ("libs/langgraph", "libs/checkpoint", "libs/prebuilt"):
        sys.path.insert(0, str(repo_root / rel))


def main() -> None:
    _bootstrap_langgraph_namespace()

    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph
    from langgraph.managed import IsLastStep, RemainingSteps

    class State(TypedDict, total=False):
        remaining: RemainingSteps
        is_last: IsLastStep
        seen: list[str]

    def observe(state: State) -> State:
        remaining = state.get("remaining")
        is_last = state.get("is_last")
        return {"seen": (state.get("seen") or []) + [f"remaining={remaining}, is_last={is_last}"]}

    graph = (
        StateGraph(State)
        .add_node("observe", observe)
        .add_edge(START, "observe")
        .add_edge("observe", END)
        .compile()
    )

    out = graph.invoke({"seen": []}, {"recursion_limit": 5})
    print(out["seen"][-1])


if __name__ == "__main__":
    main()
