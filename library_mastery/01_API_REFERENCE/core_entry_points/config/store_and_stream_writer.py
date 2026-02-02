from __future__ import annotations

from pathlib import Path
import sys


def _bootstrap_langgraph_namespace() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    for rel in ("libs/langgraph", "libs/checkpoint", "libs/prebuilt"):
        sys.path.insert(0, str(repo_root / rel))


def demo_get_store() -> None:
    from typing import TypedDict

    from langgraph.config import get_store
    from langgraph.graph import END, START, StateGraph
    from langgraph.store.memory import InMemoryStore

    class State(TypedDict):
        value: int

    store = InMemoryStore()
    store.put(("values",), "k", {"v": 41})

    def load_from_store(_: State) -> State:
        s = get_store()
        stored = s.get(("values",), "k").value["v"]
        return {"value": stored + 1}

    graph = (
        StateGraph(State)
        .add_node("load", load_from_store)
        .add_edge(START, "load")
        .add_edge("load", END)
        .compile(store=store)
    )

    print("get_store():", graph.invoke({"value": 0}))


def demo_get_stream_writer() -> None:
    from typing import TypedDict

    from langgraph.config import get_stream_writer
    from langgraph.graph import END, START, StateGraph

    class State(TypedDict):
        n: int

    def emit(state: State) -> State:
        writer = get_stream_writer()
        writer({"custom": f"n={state['n']}"})
        return {"n": state["n"] + 1}

    graph = (
        StateGraph(State)
        .add_node("emit", emit)
        .add_edge(START, "emit")
        .add_edge("emit", END)
        .compile()
    )

    print("get_stream_writer() chunks:")
    for chunk in graph.stream({"n": 1}, stream_mode="custom"):
        print("  ", chunk)


def main() -> None:
    _bootstrap_langgraph_namespace()
    demo_get_store()
    demo_get_stream_writer()


if __name__ == "__main__":
    main()
