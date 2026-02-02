"""
sqlite_deep_research_durable_demo.py

Goal
----
Show a "real world" durable workflow (deep-research style) using:
- LangGraph Functional API (`@entrypoint` + `@task`)
- SQLite checkpointer (durable state across runs)
- `interrupt(...)` + `Command(resume=...)` for human review

Domain note
-----------
This demo uses a "legal suit drafting checklist" topic as a realistic, structured
document to research + draft + review. It's an educational workflow example and
NOT legal advice.

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
    python codebase_audit/codes/durability/sqlite_deep_research_durable_demo.py start

Or provide a custom topic:
    python codebase_audit/codes/durability/sqlite_deep_research_durable_demo.py start "My topic"

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

DEFAULT_TOPIC = "Drafting a Civil Suit (Partition/Declaration) for Inherited Property"

DEFAULT_OUTLINE: list[tuple[str, list[str]]] = [
    (
        "1. Court and Suit Details",
        [
            "Name of Court",
            "Suit Number (if any)",
            "Title of Suit (Plaintiff vs. Defendant)",
        ],
    ),
    ("2. Parties", ["Plaintiff(s)", "Defendant(s)"]),
    (
        "3. Jurisdiction",
        [
            "Territorial Jurisdiction",
            "Pecuniary Jurisdiction",
            "Subject-matter Jurisdiction",
            "Basis for Jurisdiction",
        ],
    ),
    (
        "4. Facts of the Case",
        [
            "Background of Family / Deceased Ancestor",
            "Description of Inherited Property",
            "Date of Death of Ancestor",
            "Heirs and Their Relationship to Deceased",
        ],
    ),
    (
        "5. Legal Basis of Claim",
        [
            "Applicable inheritance law (as relevant)",
            "Plaintiff’s legal rights / share entitlements (as advised)",
            "Any prior family arrangements or deeds",
        ],
    ),
    (
        "6. Cause of Action",
        [
            "Specific acts/omissions by Defendant",
            "Denial of Plaintiff’s rights / title",
            "Events giving rise to the dispute",
        ],
    ),
    (
        "7. Valuation of Suit",
        [
            "Valuation of inherited property",
            "Court fees / stamp duty calculations (as applicable)",
        ],
    ),
    (
        "8. Relief Sought",
        [
            "Declaration of title / share",
            "Partition of property",
            "Delivery of possession",
            "Injunction (if sought)",
            "Costs of suit",
            "Any other relief",
        ],
    ),
    ("9. Interim Relief (if any)", ["Temporary injunction", "Preservation of status quo"]),
    (
        "10. List of Documents / Schedules",
        [
            "Schedule of property",
            "Death certificate of ancestor",
            "Family tree / heirship chart",
            "Any wills / succession certificates (if relevant)",
            "Other supporting documents",
        ],
    ),
    ("11. Verification", ["Verification statement", "Place and date"]),
]

DEFAULT_QUERIES = [
    "Partition/Declaration suit plaint checklist",
    "Jurisdiction, valuation, reliefs in civil plaint (overview)",
]


def _db_path() -> Path:
    db_dir = Path(__file__).resolve().parent / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "deep_research.sqlite"


# --- Fake "tools" for a no-network demo ------------------------------------
# In production these would call the web, an internal KB, or an LLM.

FAKE_SEARCH_INDEX: dict[str, list[str]] = {
    "Partition/Declaration suit plaint checklist": [
        "doc://court-and-suit-details",
        "doc://parties",
        "doc://jurisdiction",
        "doc://facts",
        "doc://legal-basis",
        "doc://cause-of-action",
        "doc://valuation",
        "doc://relief",
        "doc://interim-relief",
        "doc://documents",
        "doc://verification",
    ],
    "Jurisdiction, valuation, reliefs in civil plaint (overview)": [
        "doc://jurisdiction",
        "doc://valuation",
        "doc://relief",
    ],
}

FAKE_DOCS: dict[str, str] = {
    "doc://court-and-suit-details": (
        "Court and Suit Details: identify the correct court, provide title/caption, "
        "and any suit/case number if already assigned."
    ),
    "doc://parties": (
        "Parties: list all plaintiffs/defendants with complete names, addresses, and "
        "capacity/relationship (if relevant)."
    ),
    "doc://jurisdiction": (
        "Jurisdiction: explain territorial + pecuniary + subject-matter jurisdiction and "
        "the basis for why this court can hear the matter."
    ),
    "doc://facts": (
        "Facts: background of the family/deceased, property description, date of death, "
        "and heir relationships. Keep facts chronological."
    ),
    "doc://legal-basis": (
        "Legal basis: identify the applicable inheritance framework (as relevant) and "
        "state the plaintiff's claimed rights/shares. Reference any prior deeds/arrangements."
    ),
    "doc://cause-of-action": (
        "Cause of action: specify events/acts/omissions that created the dispute, "
        "including denial of rights and when/where it occurred."
    ),
    "doc://valuation": (
        "Valuation: state how the suit is valued for court fee/jurisdiction purposes and "
        "how fees are computed (requires jurisdiction-specific rules)."
    ),
    "doc://relief": (
        "Relief sought: clearly list the remedies requested (declaration, partition, "
        "possession, injunction, costs, other relief)."
    ),
    "doc://interim-relief": (
        "Interim relief: request temporary injunction/status quo/preservation orders if needed, "
        "and explain urgency and balance of convenience."
    ),
    "doc://documents": (
        "Documents/Schedules: include a property schedule and supporting documents "
        "(death certificate, family tree, title docs, etc.)."
    ),
    "doc://verification": (
        "Verification: include a verification statement, place/date, and signature as required by local procedure."
    ),
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
    # Turn the summaries into a structured draft outline.
    notes = "\n".join(f"- {s}" for s in summaries)

    sections = []
    for heading, items in DEFAULT_OUTLINE:
        bullet_items = "\n".join(f"- {i}: [TBD]" for i in items)
        sections.append(f"## {heading}\n{bullet_items}\n")

    return (
        f"# Draft Template (Educational) — {topic}\n\n"
        "This is a structured drafting checklist for learning/demo purposes only; "
        "consult a qualified lawyer for jurisdiction-specific requirements.\n\n"
        "## Research Notes (from sources)\n"
        f"{notes}\n\n"
        + "\n".join(sections)
    )


def build_workflow(checkpointer: SqliteSaver):
    @entrypoint(checkpointer=checkpointer)
    def deep_research(input_data: dict) -> dict:
        topic = input_data.get("topic") or DEFAULT_TOPIC

        # A "deep research" pattern:
        # 1) fan-out searches
        queries = input_data.get(
            "queries",
            DEFAULT_QUERIES,
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
                "question": (
                    "Review the draft template. Suggest improvements and/or provide "
                    "missing details you want filled into the [TBD] fields."
                ),
                "topic": topic,
                "sources": urls,
                "draft": draft,
                "outline": [
                    {"section": heading, "fields": items} for heading, items in DEFAULT_OUTLINE
                ],
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
        _stream_and_pretty_print(
            workflow,
            {"topic": topic, "queries": DEFAULT_QUERIES},
            config,
        )
        print("Next: resume with your feedback, e.g.\n")
        print(
            "  python codebase_audit/codes/durability/sqlite_deep_research_durable_demo.py "
            'resume "Please add placeholders for property schedule and heirship chart."'
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
        # Convenience: default to starting the demo with a realistic topic.
        cmd_start(DEFAULT_TOPIC)
        return

    cmd = sys.argv[1]
    if cmd == "reset":
        cmd_reset()
    elif cmd == "inspect":
        cmd_inspect()
    elif cmd == "start":
        cmd_start(sys.argv[2] if len(sys.argv) >= 3 else DEFAULT_TOPIC)
    elif cmd == "resume":
        if len(sys.argv) < 3:
            raise SystemExit("resume requires feedback string")
        cmd_resume(sys.argv[2])
    else:
        print("usage:")
        print("  python sqlite_deep_research_durable_demo.py reset")
        print('  python sqlite_deep_research_durable_demo.py start ["Topic"]')
        print('  python sqlite_deep_research_durable_demo.py resume "Your feedback"')
        print("  python sqlite_deep_research_durable_demo.py inspect")
        raise SystemExit(f"unknown command: {cmd!r}")


if __name__ == "__main__":
    main()
