from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import TypedDict

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


@dataclass
class Context:
    user_id: str


class State(TypedDict, total=False):
    counter: int


def recipe_store_crud() -> None:
    from langgraph.store.memory import InMemoryStore

    store = InMemoryStore()

    banner("Store: put/get/search/list_namespaces")
    store.put(("users",), "u1", {"name": "Ada", "role": "admin"})
    store.put(("users",), "u2", {"name": "Bob", "role": "user"})
    show("get(u1)", store.get(("users",), "u1").value)  # type: ignore[union-attr]
    show("search(role=admin)", [i.value for i in store.search(("users",), filter={"role": "admin"})])
    show("namespaces", list(store.list_namespaces(prefix=("users",))))


def recipe_store_inside_graph() -> None:
    from langgraph.graph import END, START, StateGraph
    from langgraph.runtime import Runtime
    from langgraph.store.memory import InMemoryStore

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

    banner("Store injected into graph: persistence across invocations")
    show("run1", graph.invoke({}, context=Context(user_id="u1")))
    show("run2", graph.invoke({}, context=Context(user_id="u1")))
    show("store value", store.get(("counters",), "u1").value)  # type: ignore[union-attr]


def main() -> None:
    bootstrap_langgraph_namespace()
    recipe_store_crud()
    recipe_store_inside_graph()


if __name__ == "__main__":
    main()

