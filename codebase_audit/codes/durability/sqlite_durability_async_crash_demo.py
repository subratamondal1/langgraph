"""
sqlite_durability_async_crash_demo.py

Purpose
-------
Demonstrate "durability='async'" with SQLite checkpointing:
- checkpoints are persisted *asynchronously* while the next superstep executes

How to use
----------
1) Ensure the repo packages are installed (from repo root):
     make install
     source .venv/bin/activate

2) Reset DB:
     python codebase_audit/codes/durability/sqlite_durability_async_crash_demo.py reset

3) Run (this intentionally hard-crashes the process during step 3):
     python codebase_audit/codes/durability/sqlite_durability_async_crash_demo.py run

4) Inspect what was persisted:
     python codebase_audit/codes/durability/sqlite_durability_async_crash_demo.py inspect

Expected outcome
----------------
Because durability is "async", the checkpoint for step 2 may NOT be persisted
before step 3 begins. Since we hard-crash at the start of step 3, you may observe
that the latest persisted checkpoint is behind (e.g. count==1).

Note: Exact results depend on timing; this script makes persistence slow so the
difference is easy to observe.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

THREAD_ID = "durability-demo-thread"
CRASH_AT_COUNT = 3
STOP_AT_COUNT = 5


def build_app(checkpointer: SqliteSaver):
    def tick(state: dict) -> dict:
        next_count = state["count"] + 1
        print(f"[tick] next_count={next_count}", flush=True)

        # Crash at the start of step 3 (next_count==3).
        # In "async" durability mode, the step 2 checkpoint may still be in-flight.
        if next_count == CRASH_AT_COUNT:
            print("[tick] 💥 hard crash now (os._exit)", flush=True)
            os._exit(137)

        time.sleep(0.05)
        return {"count": next_count}

    def loop_or_end(state: dict) -> str:
        return "tick" if state["count"] < STOP_AT_COUNT else END

    builder = StateGraph(dict)
    builder.add_node("tick", tick)
    builder.add_edge(START, "tick")
    builder.add_conditional_edges("tick", loop_or_end)
    return builder.compile(checkpointer=checkpointer)


def db_path() -> Path:
    db_dir = Path(__file__).resolve().parent / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "durability_async.sqlite"


def command_reset() -> None:
    path = db_path()
    if path.exists():
        path.unlink()
    print("reset_ok db_path=", path)


def command_inspect() -> None:
    path = db_path()
    print("db_path=", path)
    if not path.exists():
        print("no_db_found (run 'reset' then 'run' first)")
        return

    with SqliteSaver.from_conn_string(str(path)) as checkpointer:
        config = {"configurable": {"thread_id": THREAD_ID}}
        tup = checkpointer.get_tuple(config)
        if tup is None:
            print("no_checkpoint_found_for_thread_id=", THREAD_ID)
            return
        print("checkpoint_id=", tup.checkpoint["id"])
        print("channel_values=", tup.checkpoint.get("channel_values", {}))


def command_run() -> None:
    path = db_path()
    print("db_path=", path)

    with SqliteSaver.from_conn_string(str(path)) as checkpointer:
        # Make persistence clearly visible by slowing down each checkpoint write.
        original_put = checkpointer.put

        def slow_put(*args, **kwargs):
            time.sleep(1.5)
            return original_put(*args, **kwargs)

        checkpointer.put = slow_put  # type: ignore[method-assign]

        app = build_app(checkpointer)
        config = {"configurable": {"thread_id": THREAD_ID}}

        print("Starting run: durability='async' (will crash on step 3)")
        app.invoke({"count": 0}, config=config, durability="async")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"run", "inspect", "reset"}:
        print("usage: python sqlite_durability_async_crash_demo.py [run|inspect|reset]")
        raise SystemExit(2)

    cmd = sys.argv[1]
    if cmd == "reset":
        command_reset()
    elif cmd == "inspect":
        command_inspect()
    else:
        command_run()


if __name__ == "__main__":
    main()

