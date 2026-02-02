from pathlib import Path
import sys
import uuid
from typing import Optional, TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("01 — interrupt() pauses execution and returns an __interrupt__ event")

bootstrap_langgraph_namespace()

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.constants import START
from langgraph.graph import StateGraph
from langgraph.types import interrupt


class State(TypedDict):
    question: str
    answer: Optional[str]


def ask(state: State) -> State:
    # interrupt(...) stops the graph and asks the outside world for input
    user_answer = interrupt({"question": state["question"]})
    return {"answer": str(user_answer)}


graph = (
    StateGraph(State)
    .add_node("ask", ask)
    .add_edge(START, "ask")
    .compile(checkpointer=InMemorySaver())
)

config = {"configurable": {"thread_id": str(uuid.uuid4())}}

step("Run the graph in stream mode (so we can see the interrupt)")
for chunk in graph.stream({"question": "Ship this?", "answer": None}, config):
    print(chunk)

step("Inspect the stored snapshot (interrupt is stored in state)")
snap = graph.get_state(config)
show("interrupts", snap.interrupts)

