# `langgraph.pregel` (Execution Engine)

## What you import from here

Public exports:
- `Pregel`: the runtime/execution engine (Bulk Synchronous Parallel model).
- `NodeBuilder`: a fluent builder for `PregelNode` specs.

## When you should (and shouldn’t) use it

Most users should prefer:
- `langgraph.graph.StateGraph` (Graph API), or
- `langgraph.func.entrypoint` (Functional API)

Both compile down to `Pregel` internally.

Use `Pregel` directly when you need **full control** over:
- channels (value semantics, barriers, topics, aggregation),
- low-level wiring (input/output channels),
- actor-style execution patterns.

## The core mental model

Pregel runs in **steps**:
1. **Plan**: select which nodes (“actors”) should run based on what channels changed.
2. **Execute**: run selected nodes in parallel.
3. **Update**: apply channel updates atomically.

Channels are the state; nodes read from channels and write to channels.

## Example

- `pregel_basics.py` builds a tiny `Pregel` app with `NodeBuilder` and a few channels.

