from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace


def demo_stategraph_counter() -> None:
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph

    class State(TypedDict):
        count: int

    def inc(state: State) -> State:
        return {"count": state["count"] + 1}

    graph = (
        StateGraph(State)
        .add_node("inc", inc)
        .add_edge(START, "inc")
        .add_edge("inc", END)
        .compile()
    )

    print("StateGraph counter:", graph.invoke({"count": 0}))


def demo_messages_state() -> None:
    from langchain_core.messages import AIMessage, HumanMessage

    from langgraph.graph import END, START, MessagesState, StateGraph

    def respond(state: MessagesState) -> MessagesState:
        last = state["messages"][-1]
        return {"messages": [AIMessage(content=f"You said: {last.content}")]}

    graph = (
        StateGraph(MessagesState)
        .add_node("respond", respond)
        .add_edge(START, "respond")
        .add_edge("respond", END)
        .compile()
    )

    out = graph.invoke({"messages": [HumanMessage(content="Hello")]})
    print("MessagesState last message:", out["messages"][-1].content)


def main() -> None:
    bootstrap_langgraph_namespace()
    demo_stategraph_counter()
    demo_messages_state()


if __name__ == "__main__":
    main()
