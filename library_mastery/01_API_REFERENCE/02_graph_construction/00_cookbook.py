from __future__ import annotations

from pathlib import Path
import sys
from typing import Annotated, Literal, TypedDict

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, print_graph, show


def append(left: list[str], right: list[str] | None) -> list[str]:
    return left + (right or [])


class RoutingState(TypedDict, total=False):
    n: int
    parity: Literal["even", "odd"]
    result: str
    log: Annotated[list[str], append]


def classify(state: RoutingState) -> RoutingState:
    n = state["n"]
    parity: Literal["even", "odd"] = "even" if n % 2 == 0 else "odd"
    return {"parity": parity, "log": [f"classify(n={n}) -> {parity}"]}


def route(state: RoutingState) -> Literal["even", "odd"]:
    return state["parity"]


def even_node(state: RoutingState) -> RoutingState:
    return {"result": f"{state['n']} is even", "log": ["even_node()"]}


def odd_node(state: RoutingState) -> RoutingState:
    return {"result": f"{state['n']} is odd", "log": ["odd_node()"]}


class BadConcurrentState(TypedDict):
    x: int


def recipe_build_compile_invoke_and_stream() -> None:
    from langgraph.graph import END, START, StateGraph

    graph = (
        StateGraph(RoutingState)
        .add_node("classify", classify)
        .add_node("even", even_node)
        .add_node("odd", odd_node)
        .add_edge(START, "classify")
        .add_conditional_edges("classify", route)
        .add_edge("even", END)
        .add_edge("odd", END)
        .compile()
    )

    banner("Graph Construction: visualize")
    print_graph(graph.get_graph())

    banner("Graph Construction: invoke()")
    inp: RoutingState = {"n": 7, "log": []}
    out = graph.invoke(inp)
    show("input", inp)
    show("output", out)

    banner("Graph Construction: stream(mode='updates')")
    for chunk in graph.stream({"n": 8, "log": []}, stream_mode="updates"):
        print(chunk)


def recipe_concurrent_writes_failure_and_fix() -> None:
    from langgraph.errors import InvalidUpdateError
    from langgraph.graph import END, START, StateGraph

    def a(_: BadConcurrentState) -> BadConcurrentState:
        return {"x": 1}

    def b(_: BadConcurrentState) -> BadConcurrentState:
        return {"x": 2}

    bad = (
        StateGraph(BadConcurrentState)
        .add_node("a", a)
        .add_node("b", b)
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", END)
        .add_edge("b", END)
        .compile()
    )

    banner("Two writers -> InvalidUpdateError (what it looks like in prod)")
    try:
        bad.invoke({"x": 0})
    except InvalidUpdateError as e:
        print("Caught:", type(e).__name__)
        print(str(e).splitlines()[0])

    banner("Fix: use a reducible key (Annotated reducer)")

    class Good(TypedDict):
        xs: Annotated[list[int], lambda l, r: l + (r or [])]

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
    show("output", good.invoke({"xs": []}))


def main() -> None:
    bootstrap_langgraph_namespace()
    recipe_build_compile_invoke_and_stream()
    recipe_concurrent_writes_failure_and_fix()


if __name__ == "__main__":
    main()

