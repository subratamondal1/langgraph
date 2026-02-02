from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph
    from langgraph.runtime import Runtime
    from langgraph.store.memory import InMemoryStore

    @dataclass
    class Context:
        user_id: str

    class State(TypedDict, total=False):
        counter: int

    store = InMemoryStore()
    store.put(("counters",), "u1", {"n": 0})

    def bump(_: State, runtime: Runtime[Context]) -> State:
        user_id = runtime.context.user_id
        item = runtime.store.get(("counters",), user_id)  # type: ignore[union-attr]
        current = 0 if item is None else item.value["n"]
        runtime.store.put(("counters",), user_id, {"n": current + 1})  # type: ignore[union-attr]
        return {"counter": current + 1}

    graph = (
        StateGraph(state_schema=State, context_schema=Context)
        .add_node("bump", bump)
        .add_edge(START, "bump")
        .add_edge("bump", END)
        .compile(store=store)
    )

    banner("Run 1 (u1)")
    show("output", graph.invoke({}, context=Context(user_id="u1")))

    banner("Run 2 (u1, same store object => persisted)")
    show("output", graph.invoke({}, context=Context(user_id="u1")))

    banner("Stored value")
    show("store.get", store.get(("counters",), "u1").value)  # type: ignore[union-attr]


if __name__ == "__main__":
    main()

