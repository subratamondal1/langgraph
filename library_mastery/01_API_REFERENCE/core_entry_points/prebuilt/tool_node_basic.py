from __future__ import annotations

from pathlib import Path
import sys


def _bootstrap_langgraph_namespace() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    for rel in ("libs/langgraph", "libs/checkpoint", "libs/prebuilt"):
        sys.path.insert(0, str(repo_root / rel))


def main() -> None:
    _bootstrap_langgraph_namespace()

    from langchain_core.messages import AIMessage

    from langgraph.prebuilt import ToolNode

    def search(query: str) -> str:
        if "sf" in query.lower() or "san francisco" in query.lower():
            return "It's 60 degrees and foggy."
        return "It's 90 degrees and sunny."

    tool_node = ToolNode([search])
    tool_calls = [
        {"name": "search", "args": {"query": "what is the weather in sf"}, "id": "1"}
    ]
    ai_message = AIMessage(content="", tool_calls=tool_calls)

    out = tool_node.invoke({"messages": [ai_message]})
    print(out)


if __name__ == "__main__":
    main()

