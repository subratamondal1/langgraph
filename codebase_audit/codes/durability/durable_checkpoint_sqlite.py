from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph


def inc(state: dict) -> dict:
    return {"count": state["count"] + 1}


builder = StateGraph(dict)
builder.add_node("inc", inc)
builder.add_edge(START, "inc")
builder.add_edge("inc", END)

# Create the SQLite DB file under codebase_audit/codes/db/ (next to this script).
db_dir = Path(__file__).resolve().parent / "db"
db_dir.mkdir(parents=True, exist_ok=True)
db_path = db_dir / "checkpoints.sqlite"
print("sqlite_db_path:", db_path)

with SqliteSaver.from_conn_string(str(db_path)) as checkpointer:
    # setup() exists but is called automatically when needed for SQLite
    app = builder.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "demo-thread"}}

    out = app.invoke({"count": 0}, config=config, durability="sync")
    print("output:", out)

    ckpt_tuple = checkpointer.get_tuple(config)
    print("checkpoint_id:", ckpt_tuple.checkpoint["id"])
