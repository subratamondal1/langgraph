from __future__ import annotations

from pathlib import Path
import operator
import sys
from typing import Annotated, TypedDict

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def append(left: list[str], right: list[str] | None) -> list[str]:
    return left + (right or [])


class State(TypedDict):
    x: int
    events: Annotated[list[str], append]


def recipe_channel_primitives() -> None:
    from langgraph.channels import (
        BinaryOperatorAggregate,
        EphemeralValue,
        LastValue,
        LastValueAfterFinish,
        NamedBarrierValue,
        Topic,
    )

    banner("Channel primitives (direct)")

    lv = LastValue(int, key="x")
    lv.update([1])
    show("LastValue.get()", lv.get())

    topic = Topic(str, accumulate=True)
    topic.update(["a", "b"])
    topic.update(["c"])
    show("Topic(accumulate=True).get()", topic.get())

    total = BinaryOperatorAggregate(int, operator.add)
    total.update([1, 2, 3])
    show("BinaryOperatorAggregate(add).get()", total.get())

    eph = EphemeralValue(str)
    eph.update(["hello"])
    show("EphemeralValue.get()", eph.get())
    eph.update([])
    show("EphemeralValue.is_available()", eph.is_available())

    barrier = NamedBarrierValue(str, names={"A", "B"})
    barrier.update(["A"])
    show("NamedBarrierValue available after A?", barrier.is_available())
    barrier.update(["B"])
    show("NamedBarrierValue available after A+B?", barrier.is_available())

    after = LastValueAfterFinish(int, key="y")
    after.update([7])
    show("LastValueAfterFinish available after update?", after.is_available())
    after.finish()
    show("LastValueAfterFinish.get() after finish()", after.get())


def recipe_schema_compiles_to_channels() -> None:
    from langgraph.graph import END, START, StateGraph

    def node(state: State) -> State:
        return {"x": state["x"] + 1, "events": [f"saw x={state['x']}"]}

    graph = (
        StateGraph(State)
        .add_node("node", node)
        .add_edge(START, "node")
        .add_edge("node", END)
        .compile()
    )

    banner("State schema -> compiled channels")
    for key, ch in graph.channels.items():
        print(f"{key}: {type(ch).__name__}")

    show("invoke output", graph.invoke({"x": 1, "events": []}))


def main() -> None:
    bootstrap_langgraph_namespace()
    recipe_channel_primitives()
    recipe_schema_compiles_to_channels()


if __name__ == "__main__":
    main()

