from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


@dataclass
class Context:
    user_id: str


def recipe_runtime_injection_and_store() -> None:
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph
    from langgraph.runtime import Runtime
    from langgraph.store.memory import InMemoryStore

    class State(TypedDict, total=False):
        greeting: str

    store = InMemoryStore()
    store.put(("users",), "u1", {"name": "Ada"})

    def greet(_: State, runtime: Runtime[Context]) -> State:
        name = runtime.store.get(("users",), runtime.context.user_id).value["name"]  # type: ignore[union-attr]
        return {"greeting": f"Hello {name}!"}

    graph = (
        StateGraph(state_schema=State, context_schema=Context)
        .add_node("greet", greet)
        .add_edge(START, "greet")
        .add_edge("greet", END)
        .compile(store=store)
    )

    banner("Runtime injection: context + store")
    show("output", graph.invoke({}, context=Context(user_id="u1")))


def recipe_get_store_and_get_stream_writer() -> None:
    from typing import TypedDict

    from langgraph.config import get_config, get_store, get_stream_writer
    from langgraph.graph import END, START, StateGraph
    from langgraph.store.memory import InMemoryStore

    class State(TypedDict):
        x: int
        y: int

    store = InMemoryStore()
    store.put(("values",), "k", {"v": 41})

    def node(state: State) -> State:
        # Escape hatches: access runtime-scoped objects without explicit injection.
        cfg = get_config()
        s = get_store()
        writer = get_stream_writer()

        base = s.get(("values",), "k").value["v"]  # type: ignore[union-attr]
        writer({"event": "debug", "tags": cfg.get("tags"), "base": base})
        return {"y": state["x"] + base}

    graph = (
        StateGraph(State)
        .add_node("node", node)
        .add_edge(START, "node")
        .add_edge("node", END)
        .compile(store=store)
    )

    banner("get_store() + get_stream_writer() (stream_mode='custom')")
    cfg = {"tags": ["prod-demo"]}
    for chunk in graph.stream({"x": 1, "y": 0}, cfg, stream_mode="custom"):
        print(chunk)

    show("invoke output", graph.invoke({"x": 1, "y": 0}, cfg))


def main() -> None:
    bootstrap_langgraph_namespace()
    recipe_runtime_injection_and_store()
    recipe_get_store_and_get_stream_writer()


if __name__ == "__main__":
    main()

