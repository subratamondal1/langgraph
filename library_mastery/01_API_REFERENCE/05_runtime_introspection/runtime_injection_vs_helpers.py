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

    from langgraph.config import get_store
    from langgraph.graph import END, START, StateGraph
    from langgraph.runtime import Runtime
    from langgraph.store.memory import InMemoryStore

    @dataclass
    class Context:
        user_id: str

    class State(TypedDict, total=False):
        via_runtime: str
        via_helper: str

    store = InMemoryStore()
    store.put(("users",), "u1", {"name": "Ada"})

    def read_with_runtime(_: State, runtime: Runtime[Context]) -> State:
        name = runtime.store.get(("users",), runtime.context.user_id).value["name"]  # type: ignore[union-attr]
        return {"via_runtime": f"hello {name} (runtime)"}

    def read_with_helper(_: State) -> State:
        s = get_store()
        name = s.get(("users",), "u1").value["name"]
        return {"via_helper": f"hello {name} (get_store)"}

    graph = (
        StateGraph(state_schema=State, context_schema=Context)
        .add_node("runtime", read_with_runtime)
        .add_node("helper", read_with_helper)
        .add_edge(START, "runtime")
        .add_edge("runtime", "helper")
        .add_edge("helper", END)
        .compile(store=store)
    )

    banner("invoke() with Context + Store")
    out = graph.invoke({}, context=Context(user_id="u1"))
    show("output", out)


if __name__ == "__main__":
    main()

