# Section 2 — Graph Construction (`langgraph.graph`)

This folder is a runnable companion to **Section 2** of `library_mastery/01_API_REFERENCE.md`.

Goal: understand `StateGraph` like a senior engineer:
- how your schema becomes **channels**
- how nodes/edges/branches compile down to **Pregel**
- how reducers prevent “two writers” failures
- how to inspect the compiled graph and debug execution

## Files

- `00_cookbook.py`
  - production-first patterns for building/compiling/streaming graphs
  - includes the most common failure mode (two writers) + the reducer fix

- `build_visualize_and_stream.py`
  - builds a small graph with conditional routing
  - prints `graph.get_graph().draw_ascii()`
  - runs `invoke()` and several `stream_mode`s to show what the engine emits

- `reducers_and_concurrent_writes.py`
  - demonstrates `InvalidUpdateError` (two writers to the same key in a step)
  - fixes it with an `Annotated[...]` reducer
  - prints the *compiled* channel type for that key (what your schema compiled into)

- `messages_reducer_internals.py`
  - deep dive into `add_messages`: append, overwrite-by-id, delete, delete-all

## Run

From repo root:

```bash
./.venv/bin/python library_mastery/01_API_REFERENCE/02_graph_construction/build_visualize_and_stream.py
```
