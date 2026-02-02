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

    # Tool conversion resolves annotations from module globals (with future annotations).
    globals().update(
        {
            "InjectedState": InjectedState,
            "InjectedStore": InjectedStore,
            "BaseStore": BaseStore,
            "Annotated": Annotated,
        }
    )

    store = InMemoryStore()

    def memory_tool(
        query: str,
        state: Annotated[dict, InjectedState],
        store: Annotated[BaseStore, InjectedStore],
    ) -> str:
        """Tool that reads state and writes to the store."""
        store.put(("tool_runs",), "last", {"query": query, "messages": len(state["messages"])})
        return f"ok(query={query}, messages={len(state['messages'])})"

    def risky_tool(x: int) -> str:
        """Tool that may fail to demonstrate error handling."""
        if x < 0:
            raise RuntimeError("negative not allowed")
        return f"x={x}"

    tool_node = ToolNode([memory_tool, risky_tool], handle_tool_errors=True)

    def model(_: MessagesState) -> MessagesState:
        tool_calls = [
            {"name": "memory_tool", "args": {"query": "prod"}, "id": "t1"},
            {"name": "risky_tool", "args": {"x": -1}, "id": "t2"},
        ]
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

    banner("Prebuilt: ToolNode + tools_condition")
    out = graph.invoke({"messages": [HumanMessage(content="run tools")]})
    show("messages", [(m.type, getattr(m, "content", "")) for m in out["messages"]])

    banner("Store value written by tool")
    show("store.get", store.get(("tool_runs",), "last").value)  # type: ignore[union-attr]


if __name__ == "__main__":
    main()

