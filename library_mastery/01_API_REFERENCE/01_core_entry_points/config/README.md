# `langgraph.config` (Runtime Accessors)

## What you import from here

Public exports:
- `get_config`: access the current `RunnableConfig` (only valid inside a runnable context).
- `get_store`: access the configured store from inside nodes/tasks.
- `get_stream_writer`: access the custom stream writer from inside nodes/tasks.

## The core mental model

When LangGraph runs, it stores run-scoped data in a context variable.

These helpers are an escape hatch when you don’t want to inject parameters:
- Instead of adding `config: RunnableConfig` to every node, use `get_config()`.
- Instead of injecting a `Runtime`, use `get_store()` / `get_stream_writer()`.

Prefer injection (it’s clearer and easier to type-check), but these helpers are useful for quick demos and glue code.

## Example

- `store_and_stream_writer.py` shows:
  - reading from a `store` inside a node via `get_store()`
  - emitting custom stream chunks via `get_stream_writer()`

