from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


def _bootstrap_langgraph_namespace() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    for rel in ("libs/langgraph", "libs/checkpoint", "libs/prebuilt"):
        sys.path.insert(0, str(repo_root / rel))


def main() -> None:
    _bootstrap_langgraph_namespace()

    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph
    from langgraph.runtime import Runtime
    from langgraph.store.memory import InMemoryStore

    @dataclass
    class Context:
        user_id: str

    class State(TypedDict, total=False):
        greeting: str

    store = InMemoryStore()
    store.put(("users",), "u1", {"name": "Alice"})

    def hello(_: State, runtime: Runtime[Context]) -> State:
        user_id = runtime.context.user_id
        name = runtime.store.get(("users",), user_id).value["name"] if runtime.store else "unknown"
        return {"greeting": f"Hello, {name}!"}

    graph = (
        StateGraph(state_schema=State, context_schema=Context)
        .add_node("hello", hello)
        .add_edge(START, "hello")
        .add_edge("hello", END)
        .compile(store=store)
    )

    print(graph.invoke({}, context=Context(user_id="u1")))


if __name__ == "__main__":
    main()
