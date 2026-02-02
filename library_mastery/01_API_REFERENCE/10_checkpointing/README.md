# Section 10 — Persistence: Checkpointing (`langgraph.checkpoint.*`)

This folder is a runnable companion to **Section 10** of `library_mastery/01_API_REFERENCE.md`.

Goal: understand checkpointing as “versioned short-term memory”:
- checkpoints are created during execution (and enable pause/resume)
- `thread_id` is the primary key for retrieving state
- you can inspect state via `get_state()` and `get_state_history()`

## Files

- `state_history_introspection.py`
  - runs a 2-step graph with an `InMemorySaver`
  - prints the resulting `StateSnapshot`
  - iterates `get_state_history()` so you can see checkpoint metadata over time

- `interrupt_and_resume_inspect.py`
  - interrupts mid-run (`interrupt(...)`)
  - inspects `StateSnapshot.interrupts` before resuming
  - resumes with `Command(resume=...)`

## Run

```bash
./.venv/bin/python library_mastery/01_API_REFERENCE/10_checkpointing/interrupt_and_resume_inspect.py
```

