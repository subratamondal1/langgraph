# Section 5 — Runtime & In-Graph Introspection (`langgraph.runtime`, `langgraph.config`)

This folder is a runnable companion to **Section 5** of `library_mastery/01_API_REFERENCE.md`.

Goal: understand what gets injected at runtime and how to debug a run:
- `Runtime` injection (context, store, stream writer, previous)
- `get_config()` / `get_store()` / `get_stream_writer()` helpers (contextvar access)
- custom stream events (`stream_mode="custom"`)

## Files

- `runtime_injection_vs_helpers.py`
  - shows two ways to access run-scoped resources: `Runtime[...]` injection vs `get_store()`

- `custom_stream_events.py`
  - emits structured debug events from inside a node using `get_stream_writer()`
  - consumes them via `graph.stream(..., stream_mode="custom")`

## Run

```bash
./.venv/bin/python library_mastery/01_API_REFERENCE/05_runtime_introspection/custom_stream_events.py
```

