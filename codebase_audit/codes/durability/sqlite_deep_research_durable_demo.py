"""
sqlite_deep_research_durable_demo.py

Goal
----
Show a "real world" durable workflow (deep-research style) using:
- LangGraph Functional API (`@entrypoint` + `@task`)
- SQLite checkpointer (durable state across runs)
- `interrupt(...)` + `Command(resume=...)` for human review

Why this demonstrates "durable functions"
----------------------------------------
When the workflow hits an interrupt, it stops and asks for input.
On resume, the workflow re-executes from the start, BUT expensive operations are
wrapped as `@task`. Task results are persisted by the checkpointer, so those tasks
do NOT re-run on resume (you'll see no "[task]" prints the second time).

Setup (from repo root)
----------------------
    make install
    source .venv/bin/activate

Usage
-----
Reset the DB:
    python codebase_audit/codes/durability/sqlite_deep_research_durable_demo.py reset

Start a run (will interrupt for review):
    python codebase_audit/codes/durability/sqlite_deep_research_durable_demo.py start "LangGraph durability"

Resume after you see the interrupt payload:
    python codebase_audit/codes/durability/sqlite_deep_research_durable_demo.py resume "Looks good. Add more about retries."

Inspect latest checkpoint:
    python codebase_audit/codes/durability/sqlite_deep_research_durable_demo.py inspect
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.func import entrypoint, task
    from langgraph.types import Command
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing 'langgraph' in your environment.\n"
        "From the repo root, run:\n"
        "  make install\n"
        "  source .venv/bin/activate\n"
        "Then re-run this script with 'python ...'."
    ) from exc


THREAD_ID = "deep-research-demo-thread"


def _db_path() -> Path:
    db_dir = Path(__file__).resolve().parent / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "deep_research.sqlite"


# --- Fake "tools" for a no-network demo ------------------------------------
# In production these would call the web, an internal KB, or an LLM.

FAKE_SEARCH_INDEX: dict[str, list[str]] = {
    "LangGraph durability": [
        "doc://durability-modes",
        "doc://checkpointers",
        "doc://interrupt-resume",
    ],
    "LangGraph durability pitfalls": [
        "doc://async-durability-risk",
        "doc://nondeterminism",
    ],
}

FAKE_DOCS: dict[str, str] = {
    "doc://durability-modes": "Durability modes: sync, async, exit. Sync is safest.",
    "doc://checkpointers": "Checkpointers persist checkpoints. SQLite for local dev; Postgres for production.",
    "doc://interrupt-resume": "Interrupt pauses execution. Resume uses Command(resume=...). Tasks can be cached.",
    "doc://async-durability-risk": "Async durability overlaps compute with I/O but can lose the last step on crash.",
    "doc://nondeterminism": "Parallel writes need deterministic merge order to avoid flaky state differences.",
}


@task(name="web_search")
def web_search(query: str) -> list[str]:
    print(f"[task web_search] query={query!r}", flush=True)
    time.sleep(0.4)
    return FAKE_SEARCH_INDEX.get(query, [])


@task(name="fetch_doc")
def fetch_doc(url: str) -> str:
    print(f"[task fetch_doc] url={url}", flush=True)
    time.sleep(0.4)
    return FAKE_DOCS.get(url, f"(missing doc for {url})")


@task(name="summarize")
def summarize(text: str) -> str:
    print("[task summarize] ...", flush=True)
    time.sleep(0.2)
    # Extremely simple "summary" (placeholder for an LLM).
    return text.strip()


@task(name="synthesize_report")
def synthesize_report(topic: str, summaries: list[str]) -> str:
    print("[task synthesize_report] ...", flush=True)
    time.sleep(0.2)
    bullets = "\n".join(f"- {s}" for s in summaries)
    return f"# Deep Research Report: {topic}\n\n## Key Findings\n{bullets}\n"


def build_workflow(checkpointer: SqliteSaver):
    @entrypoint(checkpointer=checkpointer)
    def deep_research(input_data: dict) -> dict:
        topic = input_data["topic"]

        # A "deep research" pattern:
        # 1) fan-out searches
        queries = input_data.get(
            "queries",
            [topic, f"{topic} pitfalls"],
        )

        search_futures = [web_search(q) for q in queries]
        urls = sorted({u for fut in search_futures for u in fut.result()})

        # 2) fan-out fetch + summarize (parallelizable)
        fetch_futures = [fetch_doc(u) for u in urls]
        docs = [f.result() for f in fetch_futures]

        summarize_futures = [summarize(doc) for doc in docs]
        summaries = [f.result() for f in summarize_futures]

        # 3) synthesize draft
        draft = synthesize_report(topic, summaries).result()

        # 4) human-in-the-loop review (interrupt)
        # On resume, the function re-executes from the top, but tasks will not re-run.
        from langgraph.types import interrupt  # import inside to keep top-level minimal

        review = interrupt(
            {
                "question": "Review the draft and provide feedback to finalize.",
                "topic": topic,
                "sources": urls,
                "draft": draft,
            }
        )

        final = draft + "\n## Reviewer Feedback\n" + str(review).strip() + "\n"
        return {"topic": topic, "sources": urls, "draft": draft, "final": final}

    return deep_research


def _stream_and_pretty_print(workflow, input_or_command, config: dict) -> None:
    for chunk in workflow.stream(input_or_command, config, stream_mode="debug"):
        print(chunk)
        if "__interrupt__" in chunk:
            interrupt_tuple = chunk["__interrupt__"]
            # Usually a tuple of Interrupt objects. Show the 'value' payload.
            try:
                payload = interrupt_tuple[0].value
            except Exception:
                payload = interrupt_tuple
            print("\n--- INTERRUPT PAYLOAD (what you need to answer) ---")
            print(payload)
            print("--- END INTERRUPT PAYLOAD ---\n")


def cmd_reset() -> None:
    path = _db_path()
    if path.exists():
        path.unlink()
    print("reset_ok db_path=", path)


def cmd_inspect() -> None:
    path = _db_path()
    print("db_path=", path)
    if not path.exists():
        print("no_db_found (run 'reset' then 'start' first)")
        return
    with SqliteSaver.from_conn_string(str(path)) as checkpointer:
        config = {"configurable": {"thread_id": THREAD_ID}}
        tup = checkpointer.get_tuple(config)
        if tup is None:
            print("no_checkpoint_found_for_thread_id=", THREAD_ID)
            return
        print("checkpoint_id=", tup.checkpoint["id"])
        print("channel_values keys=", sorted(tup.checkpoint.get("channel_values", {}).keys()))


def cmd_start(topic: str) -> None:
    path = _db_path()
    print("sqlite_db_path:", path)
    with SqliteSaver.from_conn_string(str(path)) as checkpointer:
        workflow = build_workflow(checkpointer)
        config = {"configurable": {"thread_id": THREAD_ID}}
        print("THREAD_ID:", THREAD_ID)
        print("Starting deep research. This run will INTERRUPT for review.\n")
        _stream_and_pretty_print(workflow, {"topic": topic}, config)
        print("Next: resume with your feedback, e.g.\n")
        print(
            "  python codebase_audit/codes/durability/sqlite_deep_research_durable_demo.py "
            'resume "Looks good. Add more about retries."'
        )


def cmd_resume(feedback: str) -> None:
    path = _db_path()
    print("sqlite_db_path:", path)
    with SqliteSaver.from_conn_string(str(path)) as checkpointer:
        workflow = build_workflow(checkpointer)
        config = {"configurable": {"thread_id": THREAD_ID}}
        print("THREAD_ID:", THREAD_ID)
        print("Resuming from interrupt. Tasks should NOT re-run.\n")
        _stream_and_pretty_print(workflow, Command(resume=feedback), config)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage:")
        print("  python sqlite_deep_research_durable_demo.py reset")
        print('  python sqlite_deep_research_durable_demo.py start "Topic"')
        print('  python sqlite_deep_research_durable_demo.py resume "Your feedback"')
        print("  python sqlite_deep_research_durable_demo.py inspect")
        raise SystemExit(2)

    cmd = sys.argv[1]
    if cmd == "reset":
        cmd_reset()
    elif cmd == "inspect":
        cmd_inspect()
    elif cmd == "start":
        if len(sys.argv) < 3:
            raise SystemExit("start requires a topic string")
        cmd_start(sys.argv[2])
    elif cmd == "resume":
        if len(sys.argv) < 3:
            raise SystemExit("resume requires feedback string")
        cmd_resume(sys.argv[2])
    else:
        raise SystemExit(f"unknown command: {cmd!r}")


if __name__ == "__main__":
    main()

