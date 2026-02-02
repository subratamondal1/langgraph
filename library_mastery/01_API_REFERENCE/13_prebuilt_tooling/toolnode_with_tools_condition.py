from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner


def main() -> None:
    bootstrap_langgraph_namespace()

    from langchain_core.messages import AIMessage, HumanMessage

    from langgraph.graph import END, START, MessagesState, StateGraph
    from langgraph.prebuilt import ToolNode, tools_condition

    def search(query: str) -> str:
        """Toy search tool."""
        return f"search-result({query})"

    tool_node = ToolNode([search])

    def model(state: MessagesState) -> MessagesState:
        # Normally an LLM would produce tool_calls. We hard-code one for clarity.
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

    banner("Run")
    out = graph.invoke({"messages": [HumanMessage(content="please search")]})
    for m in out["messages"]:
        print(f"{m.type}: {getattr(m, 'content', '')}")


if __name__ == "__main__":
    main()

