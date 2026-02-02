from pathlib import Path
import sys

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("01 — MessagesState is just a dict with a `messages` list")

bootstrap_langgraph_namespace()

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


step("1) Input messages")
messages = [
    HumanMessage(content="Find me info about LangGraph"),
    AIMessage(content="Sure, I'll search."),
    ToolMessage(content="search result: ...", tool_call_id="t1"),
]

show("messages", [(m.type, m.content) for m in messages])

step("2) In LangGraph, your state often looks like:")
state = {"messages": messages}
show("state", state)

