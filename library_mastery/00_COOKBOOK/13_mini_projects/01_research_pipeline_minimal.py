from pathlib import Path
import sys
from typing import Annotated, TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("01 — Mini project: research pipeline (no persistence)")

bootstrap_langgraph_namespace()

from langgraph.graph import END, START, StateGraph


def append(left: list[str], right: list[str] | None) -> list[str]:
    return left + (right or [])


class State(TypedDict, total=False):
    topic: str
    questions: list[str]
    notes: dict[str, str]
    report: str
    log: Annotated[list[str], append]


def plan(state: State) -> State:
    topic = state["topic"]
    questions = [
        f"What is {topic}?",
        f"How do I use {topic} in production?",
        f"What are common mistakes with {topic}?",
    ]
    return {"questions": questions, "notes": {}, "log": [f"planned {len(questions)} questions"]}


def research(state: State) -> State:
    # Fake research: turn each question into a note.
    notes: dict[str, str] = {}
    for q in state["questions"]:
        notes[q] = f"[note] {q} -> (pretend we looked this up)"
    return {"notes": notes, "log": [f"researched {len(notes)} notes"]}


def write_report(state: State) -> State:
    lines = [f"# Report: {state['topic']}", ""]
    for q, note in state["notes"].items():
        lines.append(f"## {q}")
        lines.append(note)
        lines.append("")
    return {"report": "\n".join(lines), "log": ["wrote report"]}


graph = (
    StateGraph(State)
    .add_node("plan", plan)
    .add_node("research", research)
    .add_node("write", write_report)
    .add_edge(START, "plan")
    .add_edge("plan", "research")
    .add_edge("research", "write")
    .add_edge("write", END)
    .compile()
)

input_state = {"topic": "LangGraph", "log": []}
show("input_state", input_state)
out = graph.invoke(input_state)
show("log", out["log"])
show("report", out["report"][:400] + "\n...\n")

