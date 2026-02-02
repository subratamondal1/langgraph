from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace


def main() -> None:
    bootstrap_langgraph_namespace()

    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph
    from langgraph.managed import IsLastStep, RemainingSteps

    # This script defines the schema inside `main()`, but LangGraph evaluates
    # schema annotations using the module globals. With `from __future__ import annotations`,
    # the annotations are stored as strings, so we expose these names globally.
    globals().update({"IsLastStep": IsLastStep, "RemainingSteps": RemainingSteps})

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
