# `langgraph.runtime` (Runtime Context)

## What you import from here

Public exports:
- `Runtime`: a small dataclass bundling run-scoped utilities.
- `get_runtime`: access the current run’s `Runtime` (only valid inside a runnable context).

## The core mental model

`Runtime` is a convenient “bag” of things you often need inside nodes/tasks:
- `context`: immutable per-run context (user_id, tenant_id, db handle, etc.)
- `store`: persistence/memory store (optional)
- `stream_writer`: custom stream emitter (no-op unless `stream_mode="custom"`)
- `previous`: previous return value (functional API + checkpointer)

Prefer **dependency injection**:

```python
def node(state: State, runtime: Runtime[Context]) -> dict:
    ...
```

Use `get_runtime()` when you can’t (or don’t want to) change the function signature.

## Example

- `runtime_in_graph_node.py` shows reading `runtime.context` and `runtime.store`.

