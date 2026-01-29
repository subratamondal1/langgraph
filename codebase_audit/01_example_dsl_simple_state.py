"""
01_example_dsl_simple_state.py

Goal: Demonstrate what we mean by an embedded "DSL" (Domain-Specific Language)
for building a graph, and what the input/output look like when you run it.

This is a tiny educational "toy" graph builder, not the real LangGraph runtime.
It intentionally stays small so you can read it end-to-end.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

START = "__start__"
END = "__end__"


State = dict[str, Any]
NodeFn = Callable[[State], State]


@dataclass(frozen=True)
class CompiledGraph:
    nodes: dict[str, NodeFn]
    edges: dict[str, str]

    def _linear_path(self) -> list[str]:
        """Assume a single path START -> ... -> END."""
        path: list[str] = []
        cur = START
        seen: set[str] = set()
        while True:
            if cur in seen:
                raise ValueError(f"Cycle detected at {cur!r}")
            seen.add(cur)
            nxt = self.edges.get(cur)
            if nxt is None:
                raise ValueError(f"No outgoing edge from {cur!r}")
            if nxt == END:
                return path
            if nxt not in self.nodes:
                raise ValueError(f"Edge points to unknown node {nxt!r}")
            path.append(nxt)
            cur = nxt

    def invoke(self, state: State) -> State:
        state = dict(state)
        for step, node_name in enumerate(self._linear_path(), start=1):
            before = dict(state)
            updates = self.nodes[node_name](before)
            state.update(updates)
            print(f"[step {step}] {node_name}: input={before} updates={updates} output={state}")
        return state

    def stream(self, state: State):
        state = dict(state)
        for step, node_name in enumerate(self._linear_path(), start=1):
            before = dict(state)
            updates = self.nodes[node_name](before)
            state.update(updates)
            yield {"step": step, "node": node_name, "input": before, "updates": updates, "state": dict(state)}


class GraphDSL:
    """A minimal embedded DSL: add_node / add_edge / compile."""

    def __init__(self) -> None:
        self._nodes: dict[str, NodeFn] = {}
        self._edges: dict[str, str] = {}

    def add_node(self, name: str, fn: NodeFn) -> "GraphDSL":
        self._nodes[name] = fn
        return self

    def add_edge(self, src: str, dst: str) -> "GraphDSL":
        self._edges[src] = dst
        return self

    def compile(self) -> CompiledGraph:
        return CompiledGraph(nodes=dict(self._nodes), edges=dict(self._edges))


def main() -> None:
    # "DSL": declare nodes + edges (not the runtime details).
    def double(state: State) -> State:
        return {"x": state["x"] * 2}

    def add1(state: State) -> State:
        return {"x": state["x"] + 1}

    graph = (
        GraphDSL()
        .add_node("double", double)
        .add_node("add1", add1)
        .add_edge(START, "double")
        .add_edge("double", "add1")
        .add_edge("add1", END)
        .compile()
    )

    print("\n=== DSL demo: linear pipeline double -> add1 ===")
    input_state = {"x": 2}
    print(f"Input:  {input_state}")
    output_state = graph.invoke(input_state)
    print(f"Output: {output_state}")

    print("\n=== Streaming demo (events) ===")
    for event in graph.stream({"x": 3}):
        print(event)


if __name__ == "__main__":
    main()

