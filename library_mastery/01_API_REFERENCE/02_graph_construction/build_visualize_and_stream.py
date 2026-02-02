from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from typing import Literal, TypedDict

    from langgraph.graph import END, START, StateGraph

    class State(TypedDict, total=False):
        n: int
        parity: Literal["even", "odd"]
        result: str

    def classify(state: State) -> State:
        n = state["n"]
        return {"parity": "even" if n % 2 == 0 else "odd"}

    def even_node(state: State) -> State:
        return {"result": f"{state['n']} is even"}

    def odd_node(state: State) -> State:
        return {"result": f"{state['n']} is odd"}

    def route(state: State) -> Literal["even", "odd"]:
        return state["parity"]

    graph = (
        StateGraph(State)
        .add_node("classify", classify)
        .add_node("even", even_node)
        .add_node("odd", odd_node)
        .add_edge(START, "classify")
        .add_conditional_edges("classify", route)
        .add_edge("even", END)
        .add_edge("odd", END)
        .compile()
    )

    banner("ASCII Graph")
    print(graph.get_graph().draw_ascii())

    banner("invoke()")
    inp: State = {"n": 7}
    out = graph.invoke(inp)
    show("input", inp)
    show("output", out)

    banner("stream(mode='updates')")
    for chunk in graph.stream({"n": 8}, stream_mode="updates"):
        print(chunk)

    banner("stream(mode='values')")
    for chunk in graph.stream({"n": 9}, stream_mode="values"):
        print(chunk)


if __name__ == "__main__":
    main()

