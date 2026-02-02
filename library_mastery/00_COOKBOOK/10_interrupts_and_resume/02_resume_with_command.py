from pathlib import Path
import sys
import uuid
from typing import Optional, TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import step, title


title("02 — resume with Command(resume=...)")

bootstrap_langgraph_namespace()

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.constants import START
from langgraph.graph import StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict):
    question: str
    answer: Optional[str]


def ask(state: State) -> State:
    user_answer = interrupt({"question": state["question"]})
    return {"answer": str(user_answer)}


graph = (
    StateGraph(State)
    .add_node("ask", ask)
    .add_edge(START, "ask")
    .compile(checkpointer=InMemorySaver())
)

config = {"configurable": {"thread_id": str(uuid.uuid4())}}

step("First run: we will hit an interrupt")
for chunk in graph.stream({"question": "Approve deploy?", "answer": None}, config):
    print(chunk)

step("Resume: send the answer back in")
for chunk in graph.stream(Command(resume="yes"), config):
    print(chunk)

