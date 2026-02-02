from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace


def main() -> None:
    bootstrap_langgraph_namespace()

    from langchain_core.messages import AIMessage

    from langgraph.prebuilt import ToolNode
    from langgraph.runtime import Runtime

    def search(query: str) -> str:
        """Call to surf the web (toy example)."""
        if "sf" in query.lower() or "san francisco" in query.lower():
            return "It's 60 degrees and foggy."
        return "It's 90 degrees and sunny."

    tool_node = ToolNode([search])
    tool_calls = [
        {"name": "search", "args": {"query": "what is the weather in sf"}, "id": "1"}
    ]
    ai_message = AIMessage(content="", tool_calls=tool_calls)

    # ToolNode expects a `runtime` (normally injected when ToolNode runs inside a graph).
    out = tool_node.invoke({"messages": [ai_message]}, runtime=Runtime())
    print(out)


if __name__ == "__main__":
    main()
