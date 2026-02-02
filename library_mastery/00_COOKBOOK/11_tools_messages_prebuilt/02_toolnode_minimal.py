from pathlib import Path
import sys

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("02 — ToolNode minimal: model -> tools -> END")

bootstrap_langgraph_namespace()

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition


step("1) Define a simple tool (normal python function)")
def search(query: str) -> str:
    # In real life: call a search API. Here: deterministic output.
    return f"[fake-search] results for: {query}"


step("2) Create a ToolNode with that tool")
tools = ToolNode([search])


step("3) Create a 'model' node that produces a tool_call")
def model(_: MessagesState) -> MessagesState:
    # Normally an LLM creates these tool calls.
    tool_calls = [{"name": "search", "args": {"query": "langgraph"}, "id": "t1"}]
    return {"messages": [AIMessage(content="", tool_calls=tool_calls)]}


step("4) Build a graph that routes model -> tools when tool calls exist")
builder = StateGraph(MessagesState)
builder.add_node("model", model)
builder.add_node("tools", tools)
builder.add_edge(START, "model")
builder.add_conditional_edges("model", tools_condition, {"tools": "tools", "__end__": END})
builder.add_edge("tools", END)
graph = builder.compile()

step("5) Run it")
out = graph.invoke({"messages": [HumanMessage(content="search please")]})
show("messages (output)", [(m.type, getattr(m, "content", "")) for m in out["messages"]])

