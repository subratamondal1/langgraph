from __future__ import annotations

from pathlib import Path
import sys
from typing import TypedDict

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


class CounterState(TypedDict):
    count: int


def recipe_graph_api_stategraph() -> None:
    """Production-style skeleton: build → compile → invoke."""
    from langgraph.graph import END, START, StateGraph

    def inc(state: CounterState) -> CounterState:
        return {"count": state["count"] + 1}

    graph = (
        StateGraph(CounterState)
        .add_node("inc", inc)
        .add_edge(START, "inc")
        .add_edge("inc", END)
        .compile()
    )

    banner("Graph API (StateGraph): invoke()")
    show("input", {"count": 0})
    show("output", graph.invoke({"count": 0}))


def recipe_functional_api_entrypoint() -> None:
    """Production-style skeleton: tasks + entrypoint (parallel fan-out/fan-in)."""
    from langgraph.func import entrypoint, task

    @task
    def add_one(x: int) -> int:
        return x + 1

    @entrypoint()
    def workflow(values: list[int]) -> list[int]:
        futures = [add_one(v) for v in values]
        return [f.result() for f in futures]

    banner("Functional API (entrypoint + task): invoke()")
    show("input", [1, 2, 3])
    show("output", workflow.invoke([1, 2, 3]))


def recipe_prebuilt_toolnode() -> None:
    """Production-style skeleton: ToolNode + tools_condition (tool loop building block)."""
    from langchain_core.messages import AIMessage, HumanMessage

    from langgraph.graph import END, START, MessagesState, StateGraph
    from langgraph.prebuilt import ToolNode, tools_condition

    def search(query: str) -> str:
        """Toy tool for demonstration."""
        return f"search-result({query})"

    tool_node = ToolNode([search])

    def model(_: MessagesState) -> MessagesState:
        # Normally an LLM creates tool_calls. We hard-code one for clarity.
        tool_calls = [{"name": "search", "args": {"query": "langgraph"}, "id": "t1"}]
        return {"messages": [AIMessage(content="", tool_calls=tool_calls)]}

    graph = (
        StateGraph(MessagesState)
        .add_node("model", model)
        .add_node("tools", tool_node)
        .add_edge(START, "model")
        .add_conditional_edges("model", tools_condition, {"tools": "tools", "__end__": END})
        .add_edge("tools", END)
        .compile()
    )

    banner("Prebuilt (ToolNode): invoke()")
    out = graph.invoke({"messages": [HumanMessage(content="please search")]})
    show("messages", [(m.type, getattr(m, "content", "")) for m in out["messages"]])


def main() -> None:
    bootstrap_langgraph_namespace()
    recipe_graph_api_stategraph()
    recipe_functional_api_entrypoint()
    recipe_prebuilt_toolnode()


if __name__ == "__main__":
    main()

