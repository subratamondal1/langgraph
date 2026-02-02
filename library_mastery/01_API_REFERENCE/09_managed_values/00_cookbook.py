from __future__ import annotations

from pathlib import Path
import sys
from typing import Annotated, TypedDict

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def append(left: list[str], right: list[str] | None) -> list[str]:
    return left + (right or [])


def recipe_managed_values_to_stop_before_recursion() -> None:
    from langgraph.constants import END, START
    from langgraph.graph import StateGraph
    from langgraph.managed import IsLastStep, RemainingSteps

    # With `from __future__ import annotations`, these names must be resolvable from module globals
    # when LangGraph evaluates schema annotations via `typing.get_type_hints(...)`.
    globals().update({"IsLastStep": IsLastStep, "RemainingSteps": RemainingSteps})

    class State(TypedDict, total=False):
        remaining: RemainingSteps
        is_last: IsLastStep
        log: Annotated[list[str], append]

    # Make `State` resolvable when LangGraph calls `typing.get_type_hints(...)` on the
    # node/router functions (which reads from the function's module globals).
    globals().update({"State": State})

    def observe(state: State) -> State:
        return {"log": [f"remaining={state.get('remaining')}, is_last={state.get('is_last')}"]}

    def should_continue(state: State) -> str:
        # Stop cleanly one step before the runtime would raise GraphRecursionError.
        return END if state.get("is_last") else "observe"

    graph = (
        StateGraph(State)
        .add_node("observe", observe)
        .add_edge(START, "observe")
        .add_conditional_edges("observe", should_continue)
        .compile()
    )

    banner("Managed values: loop with graceful stop using IsLastStep")
    out = graph.invoke({"log": []}, {"recursion_limit": 5})
    show("log", out["log"])


def recipe_managed_values_forbidden_in_input_output() -> None:
    from langgraph.graph import StateGraph
    from langgraph.managed import RemainingSteps

    globals().update({"RemainingSteps": RemainingSteps})

    class State(TypedDict, total=False):
        remaining: RemainingSteps
        x: int

    class Input(TypedDict, total=False):
        remaining: RemainingSteps  # intentionally invalid
        x: int

    banner("Managed values: forbidden in input_schema/output_schema")
    try:
        StateGraph(state_schema=State, input_schema=Input)
    except ValueError as e:
        print("Caught:", type(e).__name__)
        print(str(e).splitlines()[0])


def main() -> None:
    bootstrap_langgraph_namespace()
    recipe_managed_values_to_stop_before_recursion()
    recipe_managed_values_forbidden_in_input_output()


if __name__ == "__main__":
    main()
