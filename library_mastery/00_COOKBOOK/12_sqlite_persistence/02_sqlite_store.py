from dataclasses import dataclass
from pathlib import Path
import sys

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("02 — SQLite store (general persistence)")

bootstrap_langgraph_namespace()

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.sqlite import SqliteStore
from typing import TypedDict


@dataclass
class Context:
    user_id: str


class State(TypedDict, total=False):
    counter: int


scratch = COOKBOOK_ROOT / "_scratch"
scratch.mkdir(parents=True, exist_ok=True)
db_path = scratch / "store.db"


with SqliteStore.from_conn_string(str(db_path)) as store:
    step("Part A) Direct CRUD")
    store.put(("users",), "u1", {"name": "Ada", "role": "admin"})
    store.put(("users",), "u2", {"name": "Bob", "role": "user"})
    show("get(u1)", store.get(("users",), "u1").value)  # type: ignore[union-attr]
    show("search(role=admin)", [i.value for i in store.search(("users",), filter={"role": "admin"})])

    step("Part B) Inject store into a graph via runtime.store")
    store.put(("counters",), "u1", {"n": 0})

    def bump(_: State, runtime: Runtime[Context]) -> State:
        user_id = runtime.context.user_id
        item = runtime.store.get(("counters",), user_id)  # type: ignore[union-attr]
        current = 0 if item is None else item.value["n"]
        runtime.store.put(("counters",), user_id, {"n": current + 1})  # type: ignore[union-attr]
        return {"counter": current + 1}

    graph = (
        StateGraph(state_schema=State, context_schema=Context)
        .add_node("bump", bump)
        .add_edge(START, "bump")
        .add_edge("bump", END)
        .compile(store=store)
    )

    out1 = graph.invoke({}, context=Context(user_id="u1"))
    out2 = graph.invoke({}, context=Context(user_id="u1"))
    show("out1", out1)
    show("out2", out2)
    show("store.get(counters/u1)", store.get(("counters",), "u1").value)  # type: ignore[union-attr]

