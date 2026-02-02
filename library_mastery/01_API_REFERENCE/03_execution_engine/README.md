# Section 3 — Execution Engine (`langgraph.pregel`)

This folder is a runnable companion to **Section 3** of `library_mastery/01_API_REFERENCE.md`.

Goal: understand how the runtime actually executes work:
- nodes are **actors** (PregelNodes)
- channels are the **state + merge rules**
- execution happens in **super-steps** (plan → execute → update)
- streaming modes expose what’s happening internally

## Files

- `pregel_debug_stream.py`
  - builds a small Pregel app with multiple nodes/channels
  - prints the drawable graph (`get_graph().draw_ascii()`)
  - runs with `stream_mode="tasks"` and `stream_mode="debug"` so you can see scheduling/output

- `pregel_cycle_until_none.py`
  - demonstrates a self-loop: a node writes back into the channel it subscribes to
  - uses `ChannelWriteEntry(skip_none=True)` to stop when the node returns `None`

## Run

```bash
./.venv/bin/python library_mastery/01_API_REFERENCE/03_execution_engine/pregel_debug_stream.py
```

