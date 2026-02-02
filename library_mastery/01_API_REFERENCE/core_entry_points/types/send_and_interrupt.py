from __future__ import annotations

from pathlib import Path
import uuid
import sys


def _bootstrap_langgraph_namespace() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    for rel in ("libs/langgraph", "libs/checkpoint", "libs/prebuilt"):
        sys.path.insert(0, str(repo_root / rel))


def demo_send_fan_out() -> None:
    from typing import Annotated, TypedDict

    from langgraph.constants import END, START
    from langgraph.graph import StateGraph
    from langgraph.types import Send

    class OverallState(TypedDict):
        subjects: list[str]
        jokes: Annotated[list[str], lambda a, b: a + b]  # simple list-append reducer

    def continue_to_jokes(state: OverallState) -> list[Send]:
        return [Send("generate_joke", {"subject": s}) for s in state["subjects"]]

    def generate_joke(state: dict) -> dict:
        return {"jokes": [f"Joke about {state['subject']}"]}

    graph = (
        StateGraph(OverallState)
        .add_node("generate_joke", generate_joke)
        .add_conditional_edges(START, continue_to_jokes)
        .add_edge("generate_joke", END)
        .compile()
    )

    print("Send fan-out:", graph.invoke({"subjects": ["cats", "dogs"], "jokes": []})["jokes"])


def demo_interrupt_resume() -> None:
    from typing import Optional
    from typing import TypedDict

    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.constants import START
    from langgraph.graph import StateGraph
    from langgraph.types import Command, interrupt

    class State(TypedDict):
        question: str
        answer: Optional[str]

    def ask_human(state: State) -> State:
        answer = interrupt(state["question"])
        return {"answer": answer}

    graph = (
        StateGraph(State)
        .add_node("ask", ask_human)
        .add_edge(START, "ask")
        .compile(checkpointer=InMemorySaver())
    )

    config = {"configurable": {"thread_id": uuid.uuid4()}}

    # First run interrupts (you'll see an __interrupt__ event)
    for chunk in graph.stream({"question": "What is your favorite color?", "answer": None}, config):
        print("interrupt stream chunk:", chunk)

    # Resume the same thread with a Command
    for chunk in graph.stream(Command(resume="blue"), config):
        print("resume stream chunk:", chunk)


def main() -> None:
    _bootstrap_langgraph_namespace()
    demo_send_fan_out()
    demo_interrupt_resume()


if __name__ == "__main__":
    main()
