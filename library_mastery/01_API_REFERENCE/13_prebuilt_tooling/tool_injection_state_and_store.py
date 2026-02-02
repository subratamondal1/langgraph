from __future__ import annotations

from pathlib import Path
import sys
from typing import Annotated

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from langchain_core.messages import AIMessage, HumanMessage

    from langgraph.graph import END, START, MessagesState, StateGraph
    from langgraph.prebuilt import InjectedState, InjectedStore, ToolNode, tools_condition
    from langgraph.store.base import BaseStore
    from langgraph.store.memory import InMemoryStore

    store = InMemoryStore()

    def memory_tool(
        query: str,
        state: Annotated[dict, InjectedState],
        store: Annotated[BaseStore, InjectedStore],
    ) -> str:
        """Tool that reads graph state and writes to store (to demonstrate injection)."""
        store.put(("tool_runs",), "last", {"query": query, "messages": len(state["messages"])})
        return f"query={query}, messages={len(state['messages'])}"

    tool_node = ToolNode([memory_tool])

    def model(_: MessagesState) -> MessagesState:
        tool_calls = [{"name": "memory_tool", "args": {"query": "debug"}, "id": "t1"}]
        return {"messages": [AIMessage(content="", tool_calls=tool_calls)]}

    graph = (
        StateGraph(MessagesState)
        .add_node("model", model)
        .add_node("tools", tool_node)
        .add_edge(START, "model")
        .add_conditional_edges("model", tools_condition, {"tools": "tools", "__end__": END})
        .add_edge("tools", END)
        .compile(store=store)
    )

    banner("Run")
    out = graph.invoke({"messages": [HumanMessage(content="run tool")]})
    show("last message", out["messages"][-1].content)

    banner("Store value written by tool")
    show("store.get", store.get(("tool_runs",), "last").value)  # type: ignore[union-attr]


if __name__ == "__main__":
    main()

