from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Annotated, Optional, TypedDict

# Allow: from _bootstrap import ..., from _utils import ...
COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("Deep Research Agent (SQLite) — single file, top-to-bottom")

bootstrap_langgraph_namespace()

# LangGraph imports (the “car you drive”)
from langgraph.cache.sqlite import SqliteCache
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime
from langgraph.store.sqlite import SqliteStore
from langgraph.types import Command, interrupt


# -----------------------------
# 0) Minimal CLI (keep it simple)
# -----------------------------

topic = "LangGraph"
thread_id = "deep-research-demo"
resume_answer: Optional[str] = None
auto = False

args = sys.argv[1:]
i = 0
while i < len(args):
    if args[i] == "--thread":
        thread_id = args[i + 1]
        i += 2
        continue
    if args[i] == "--resume":
        resume_answer = args[i + 1]
        i += 2
        continue
    if args[i] == "--auto":
        auto = True
        i += 1
        continue
    topic = args[i]
    i += 1

config = {"configurable": {"thread_id": thread_id}}

step("Run config (this is how checkpoints are keyed)")
show("thread_id", thread_id)


# -----------------------------
# 1) SQLite durability setup
# -----------------------------

scratch = COOKBOOK_ROOT / "_scratch"
scratch.mkdir(parents=True, exist_ok=True)

checkpoint_db = scratch / "deep_research_checkpoints.db"
store_db = scratch / "deep_research_store.db"
cache_db = scratch / "deep_research_cache.db"

cache = SqliteCache(path=str(cache_db))


# -----------------------------
# 2) State + Context (TypedDict + dataclass)
# -----------------------------

def append(left: list[str], right: list[str] | None) -> list[str]:
    return left + (right or [])

def merge_notes(left: dict[str, str], right: dict[str, str] | None) -> dict[str, str]:
    merged = dict(left)
    merged.update(right or {})
    return merged


@dataclass
class Context:
    user_id: str


class State(TypedDict, total=False):
    topic: str
    questions: list[str]
    i: int
    current_question: str
    notes: Annotated[dict[str, str], merge_notes]
    report: str
    approved: Optional[bool]
    log: Annotated[list[str], append]


# -----------------------------
# 3) “Tools” (simple functions)
# -----------------------------

FAKE_CORPUS = {
    "LangGraph": [
        "LangGraph helps you build stateful agent workflows as graphs.",
        "StateGraph nodes return partial state updates; reducers merge concurrent updates.",
        "Use SQLite checkpointing to resume runs by thread_id.",
    ]
}


def search_tool(query: str) -> str:
    """
    Fake 'search' tool:
    - checks SQLite cache first
    - otherwise returns deterministic text
    """
    ns = ("search",)
    hit = cache.get([(ns, query)]).get((ns, query))
    if hit is not None:
        return f"[cache hit] {hit['value']}"

    topic_key = "LangGraph" if "langgraph" in query.lower() else "unknown"
    lines = FAKE_CORPUS.get(topic_key, ["(no local docs available)"])
    result = " | ".join(lines)
    cache.set({(ns, query): ({"value": result}, 3600)})
    return f"[cache miss] {result}"


# -----------------------------
# 4) Nodes (plain python functions)
# -----------------------------

def plan(state: State) -> State:
    t = state["topic"]
    questions = [
        f"What is {t}?",
        f"How do I use {t} in production?",
        f"How do I persist + resume a {t} workflow with SQLite?",
    ]
    return {"questions": questions, "i": 0, "notes": {}, "log": [f"planned {len(questions)} questions"]}


def pick_question(state: State) -> State:
    q = state["questions"][state["i"]]
    return {"current_question": q, "log": [f"picked question[{state['i']}]"]}


def research_one(state: State) -> State:
    q = state["current_question"]
    print("\nInside research_one(...)")
    show("question", q)
    note = search_tool(q)
    return {"log": ["researched 1 question"], "notes": {q: note}}


def save_note(state: State, runtime: Runtime[Context]) -> State:
    """
    Persist the latest note to SQLite store.
    Notes are also kept in state (so the report can be generated).
    """
    user_id = runtime.context.user_id
    # We just wrote one note into state["notes"] (for current_question)
    q = state["current_question"]
    note = state["notes"][q]
    runtime.store.put(("research_notes", user_id), q, {"note": note})  # type: ignore[union-attr]
    return {"i": state["i"] + 1, "log": [f"saved note for user={user_id}"]}


def more_or_write(state: State) -> str:
    # Routing function: either loop again or move forward
    return "pick" if state["i"] < len(state["questions"]) else "write"


def write_report(state: State) -> State:
    lines = [f"# Deep Research Report: {state['topic']}", ""]
    for q, note in state["notes"].items():
        lines.append(f"## {q}")
        lines.append(note)
        lines.append("")
    report = "\n".join(lines)
    return {"report": report, "log": ["wrote report"]}


def ask_approval(state: State) -> State:
    answer = interrupt({"question": "Approve this report? (yes/no)", "preview": state["report"][:200]})
    approved = str(answer).strip().lower() in {"y", "yes"}
    return {"approved": approved, "log": [f"approved={approved}"]}


def finish_or_rewrite(state: State) -> str:
    return END if state.get("approved") else "write"


# -----------------------------
# 5) Build graph
# -----------------------------

builder = StateGraph(state_schema=State, context_schema=Context)
builder.add_node("plan", plan)
builder.add_node("pick", pick_question)
builder.add_node("research", research_one)
builder.add_node("save", save_note)
builder.add_node("write", write_report)
builder.add_node("approve", ask_approval)

builder.add_edge(START, "plan")
builder.add_edge("plan", "pick")
builder.add_edge("pick", "research")
builder.add_edge("research", "save")
builder.add_conditional_edges("save", more_or_write, {"pick": "pick", "write": "write"})
builder.add_edge("write", "approve")
builder.add_conditional_edges("approve", finish_or_rewrite, {"write": "write", "__end__": END})


# -----------------------------
# 6) Run / resume
# -----------------------------

with SqliteSaver.from_conn_string(str(checkpoint_db)) as checkpointer:
    with SqliteStore.from_conn_string(str(store_db)) as store:
        graph = builder.compile(checkpointer=checkpointer, store=store)

        if resume_answer is not None:
            step("Resuming from checkpoint")
            for chunk in graph.stream(Command(resume=resume_answer), config, context=Context(user_id="u1")):
                print(chunk)
        else:
            step("Starting a new run (will interrupt for approval)")
            interrupted = False
            for chunk in graph.stream({"topic": topic, "log": []}, config, context=Context(user_id="u1")):
                print(chunk)
                if "__interrupt__" in chunk:
                    interrupted = True
                    break

            if interrupted and auto:
                step("Auto-resume: sending yes")
                for chunk in graph.stream(Command(resume="yes"), config, context=Context(user_id="u1")):
                    print(chunk)
            elif interrupted:
                print("\nPaused on interrupt.")
                print("Resume with:")
                print(
                    "./.venv/bin/python "
                    "library_mastery/00_COOKBOOK/14_final_project/00_deep_research_agent_sqlite.py "
                    "--resume yes"
                )

        step("Inspect durable artifacts in SQLite store")
        items = list(store.search(("research_notes", "u1")))  # type: ignore[call-arg]
        show("stored_notes_count", len(items))
        if items:
            show("example_stored_note", {"key": items[0].key, "value": items[0].value})
