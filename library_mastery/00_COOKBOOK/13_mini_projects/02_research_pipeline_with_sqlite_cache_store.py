from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Annotated, TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("02 — Mini project: research pipeline + SQLite cache + store")

bootstrap_langgraph_namespace()

from langgraph.cache.sqlite import SqliteCache
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.sqlite import SqliteStore


def append(left: list[str], right: list[str] | None) -> list[str]:
    return left + (right or [])


@dataclass
class Context:
    user_id: str


class State(TypedDict, total=False):
    topic: str
    questions: list[str]
    notes: dict[str, str]
    report: str
    log: Annotated[list[str], append]


scratch = COOKBOOK_ROOT / "_scratch"
scratch.mkdir(parents=True, exist_ok=True)
cache = SqliteCache(path=str(scratch / "mini_cache.db"))


def cache_get(namespace: tuple[str, ...], key: str) -> str | None:
    hit = cache.get([(namespace, key)])
    item = hit.get((namespace, key))
    return None if item is None else item["value"]


def cache_set(namespace: tuple[str, ...], key: str, value: str, ttl: int | None = None) -> None:
    cache.set({(namespace, key): ({"value": value}, ttl)})


def plan(state: State) -> State:
    topic = state["topic"]
    questions = [f"What is {topic}?", f"How to use {topic}?", f"Gotchas of {topic}?"]
    return {"questions": questions, "notes": {}, "log": [f"planned {len(questions)} questions"]}


def research(state: State, runtime: Runtime[Context]) -> State:
    notes: dict[str, str] = {}
    for q in state["questions"]:
        cached = cache_get(("search",), q)
        if cached is not None:
            notes[q] = cached
            continue
        # Fake research result
        value = f"[sqlite-cached-note] {q} -> (pretend external research)"
        cache_set(("search",), q, value, ttl=60)
        notes[q] = value

        # Store durable artifact for this user (so you can inspect it later)
        runtime.store.put(("notes", runtime.context.user_id), q, {"note": value})  # type: ignore[union-attr]
    return {"notes": notes, "log": [f"researched {len(notes)} notes (cache+store)"]}


def write_report(state: State) -> State:
    lines = [f"# Report: {state['topic']}", ""]
    for q, note in state["notes"].items():
        lines.append(f"## {q}")
        lines.append(note)
        lines.append("")
    return {"report": "\n".join(lines), "log": ["wrote report"]}


with SqliteStore.from_conn_string(str(scratch / "mini_store.db")) as store:
    graph = (
        StateGraph(state_schema=State, context_schema=Context)
        .add_node("plan", plan)
        .add_node("research", research)
        .add_node("write", write_report)
        .add_edge(START, "plan")
        .add_edge("plan", "research")
        .add_edge("research", "write")
        .add_edge("write", END)
        .compile(store=store)
    )

    input_state = {"topic": "LangGraph", "log": []}
    out = graph.invoke(input_state, context=Context(user_id="u1"))
    show("log", out["log"])
    show("report", out["report"][:250] + "\n...\n")

    step("Inspect stored notes (persisted in SQLite)")
    items = list(store.search(("notes", "u1")))  # type: ignore[call-arg]
    show("stored_count", len(items))
    if items:
        show("one_item", {"key": items[0].key, "value": items[0].value})

