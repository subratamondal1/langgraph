from __future__ import annotations

from pathlib import Path
import sys
import warnings
from typing import Annotated, TypedDict

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def append_ints(left: list[int], right: list[int] | None) -> list[int]:
    return left + (right or [])


def recipe_recursion_error() -> None:
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

    banner("GraphRecursionError (guarded with recursion_limit)")
    try:
        graph.invoke({"n": 0}, {"recursion_limit": 3})
    except GraphRecursionError as e:
        print("Caught:", type(e).__name__)
        print("First line:", str(e).splitlines()[0])


def recipe_invalid_update_error_and_fix() -> None:
    from langgraph.errors import InvalidUpdateError
    from langgraph.graph import END, START, StateGraph

    class Bad(TypedDict):
        x: int

    def a(_: Bad) -> Bad:
        return {"x": 1}

    def b(_: Bad) -> Bad:
        return {"x": 2}

    bad = (
        StateGraph(Bad)
        .add_node("a", a)
        .add_node("b", b)
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )

    banner("InvalidUpdateError (two writers, no reducer)")
    try:
        bad.invoke({"x": 0})
    except InvalidUpdateError as e:
        print("Caught:", type(e).__name__)
        print("First line:", str(e).splitlines()[0])

    class Good(TypedDict):
        xs: Annotated[list[int], append_ints]

    def a2(_: Good) -> Good:
        return {"xs": [1]}

    def b2(_: Good) -> Good:
        return {"xs": [2]}

    good = (
        StateGraph(Good)
        .add_node("a", a2)
        .add_node("b", b2)
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )

    banner("Fix: reducer key (Annotated) makes concurrent updates safe")
    show("output", good.invoke({"xs": []}))


def recipe_constants_and_deprecation_traps() -> None:
    banner("Constants + deprecation traps")
    from langgraph.constants import END, START, TAG_HIDDEN, TAG_NOSTREAM

    show("START/END", {"START": START, "END": END})
    show("tags", {"TAG_HIDDEN": TAG_HIDDEN, "TAG_NOSTREAM": TAG_NOSTREAM})

    banner("Deprecated proxy import from langgraph.constants")
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        from langgraph.constants import Send  # noqa: F401

    show("warnings", [str(w.message) for w in captured])


def main() -> None:
    bootstrap_langgraph_namespace()
    recipe_recursion_error()
    recipe_invalid_update_error_and_fix()
    recipe_constants_and_deprecation_traps()


if __name__ == "__main__":
    main()
