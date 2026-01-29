"""
postgres_deep_research_durable_demo.py

Goal
----
Same "deep research" durable workflow as the SQLite demo, but using Postgres.
This is closer to production because Postgres can be shared across processes/hosts.

What it demonstrates
--------------------
- LangGraph Functional API (`@entrypoint` + `@task`)
- Postgres checkpointer (durable checkpoints stored in Postgres tables)
- `interrupt(...)` + `Command(resume=...)` for human review
- On resume, expensive `@task` work should NOT re-run (it is cached via the checkpointer)

Setup (from repo root)
----------------------
1) Install local packages:
     make install
     source .venv/bin/activate

2) Start a local Postgres (the repo includes a compose file used by tests):
     docker compose -f libs/langgraph/tests/compose-postgres.yml up -d

Connection string
-----------------
Set `LANGGRAPH_POSTGRES_URI` (or rely on the default below):
  export LANGGRAPH_POSTGRES_URI="postgres://postgres:postgres@localhost:5442/postgres"

Usage
-----
Reset rows for this demo thread_id:
  python codebase_audit/codes/durability/postgres_deep_research_durable_demo.py reset

Start a run (will interrupt for review):
  python codebase_audit/codes/durability/postgres_deep_research_durable_demo.py start "LangGraph durability"

Resume:
  python codebase_audit/codes/durability/postgres_deep_research_durable_demo.py resume "Looks good. Add more about retries."

Inspect latest checkpoint:
  python codebase_audit/codes/durability/postgres_deep_research_durable_demo.py inspect
"""

from __future__ import annotations

import os
import sys
import time

try:
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.func import entrypoint, task
    from langgraph.types import Command
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing 'langgraph' (or postgres checkpointer) in your environment.\n"
        "From the repo root, run:\n"
        "  make install\n"
        "  source .venv/bin/activate\n"
        "Also ensure you installed Postgres deps (psycopg).\n"
    ) from exc


POSTGRES_URI = os.environ.get(
    "LANGGRAPH_POSTGRES_URI",
    "postgres://postgres:postgres@localhost:5442/postgres",
)
THREAD_ID = os.environ.get("LANGGRAPH_THREAD_ID", "deep-research-demo-thread")


# --- Fake "tools" for a no-network demo ------------------------------------

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
    return text.strip()


@task(name="synthesize_report")
def synthesize_report(topic: str, summaries: list[str]) -> str:
    print("[task synthesize_report] ...", flush=True)
    time.sleep(0.2)
    bullets = "\n".join(f"- {s}" for s in summaries)
    return f"# Deep Research Report: {topic}\n\n## Key Findings\n{bullets}\n"


def build_workflow(checkpointer: PostgresSaver):
    @entrypoint(checkpointer=checkpointer)
    def deep_research(input_data: dict) -> dict:
        topic = input_data["topic"]
        queries = input_data.get("queries", [topic, f"{topic} pitfalls"])

        # Fan-out searches
        search_futures = [web_search(q) for q in queries]
        urls = sorted({u for fut in search_futures for u in fut.result()})

        # Fan-out fetch + summarize
        fetch_futures = [fetch_doc(u) for u in urls]
        docs = [f.result() for f in fetch_futures]

        summarize_futures = [summarize(doc) for doc in docs]
        summaries = [f.result() for f in summarize_futures]

        draft = synthesize_report(topic, summaries).result()

        from langgraph.types import interrupt

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
            try:
                payload = interrupt_tuple[0].value
            except Exception:
                payload = interrupt_tuple
            print("\n--- INTERRUPT PAYLOAD (what you need to answer) ---")
            print(payload)
            print("--- END INTERRUPT PAYLOAD ---\n")


def cmd_reset() -> None:
    print("POSTGRES_URI:", POSTGRES_URI)
    print("THREAD_ID:", THREAD_ID)
    with PostgresSaver.from_conn_string(POSTGRES_URI) as checkpointer:
        checkpointer.setup()
        # Delete only this demo's rows. Keeps migrations table intact.
        checkpointer.conn.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", (THREAD_ID,))
        checkpointer.conn.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s", (THREAD_ID,))
        checkpointer.conn.execute("DELETE FROM checkpoints WHERE thread_id = %s", (THREAD_ID,))
    print("reset_ok")


def cmd_inspect() -> None:
    print("POSTGRES_URI:", POSTGRES_URI)
    print("THREAD_ID:", THREAD_ID)
    with PostgresSaver.from_conn_string(POSTGRES_URI) as checkpointer:
        checkpointer.setup()
        config = {"configurable": {"thread_id": THREAD_ID}}
        tup = checkpointer.get_tuple(config)
        if tup is None:
            print("no_checkpoint_found_for_thread_id")
            return
        print("checkpoint_id=", tup.checkpoint["id"])
        print("channel_values keys=", sorted(tup.checkpoint.get("channel_values", {}).keys()))


def cmd_start(topic: str) -> None:
    print("POSTGRES_URI:", POSTGRES_URI)
    print("THREAD_ID:", THREAD_ID)
    with PostgresSaver.from_conn_string(POSTGRES_URI) as checkpointer:
        checkpointer.setup()
        workflow = build_workflow(checkpointer)
        config = {"configurable": {"thread_id": THREAD_ID}}
        print("Starting deep research. This run will INTERRUPT for review.\n")
        _stream_and_pretty_print(workflow, {"topic": topic}, config)
        print("Next: resume with your feedback, e.g.\n")
        print(
            "  python codebase_audit/codes/durability/postgres_deep_research_durable_demo.py "
            'resume "Looks good. Add more about retries."'
        )


def cmd_resume(feedback: str) -> None:
    print("POSTGRES_URI:", POSTGRES_URI)
    print("THREAD_ID:", THREAD_ID)
    with PostgresSaver.from_conn_string(POSTGRES_URI) as checkpointer:
        checkpointer.setup()
        workflow = build_workflow(checkpointer)
        config = {"configurable": {"thread_id": THREAD_ID}}
        print("Resuming from interrupt. Tasks should NOT re-run.\n")
        _stream_and_pretty_print(workflow, Command(resume=feedback), config)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage:")
        print("  python postgres_deep_research_durable_demo.py reset")
        print('  python postgres_deep_research_durable_demo.py start "Topic"')
        print('  python postgres_deep_research_durable_demo.py resume "Your feedback"')
        print("  python postgres_deep_research_durable_demo.py inspect")
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

