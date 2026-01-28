# 03 — THE FLOW (The Dynamics)

This document hypothesizes the “happy paths” and key data/control flows—without attempting to describe every file.

LangGraph is best understood as two planes:

- **Data plane:** runs graphs (state, messages, channels, steps).
- **Control plane:** configures, persists, and orchestrates runs locally or via an external server (checkpointers/stores, CLI, SDK).

## Happy Path A: Build and Run a Graph (Local, In-Process)

**Core user intent:** “Given some input state/messages, execute a multi-step graph and produce output, possibly streaming intermediate events.”

High-level flow:

1. **Author** nodes (Python callables) and a state schema.
2. **Assemble** a `StateGraph` (nodes + edges + branching).
3. **Compile** into a runnable graph.
4. **Execute** via `.invoke()` / `.stream()` / `.ainvoke()` / `.astream()`.

Conceptual file-path (by subsystem):

```
User code
  -> langgraph.graph.StateGraph (graph authoring DSL)
  -> StateGraph.compile() => CompiledStateGraph
  -> CompiledStateGraph (inherits Pregel engine)
  -> langgraph.pregel.* (step loop + scheduling + streaming)
  -> outputs (final state + optional streamed events)
```

Key first-principles idea:

- **Compilation turns a declarative graph into an executable engine** (a runnable that knows how to schedule nodes and manage state transitions).

## Happy Path B: Durable Execution via Checkpointing (Short-Term, Versioned)

**Core user intent:** “Pause/resume/replay a run and preserve progress between invocations.”

What changes:

- You compile with a **checkpointer** (or inherit one from a parent/subgraph).
- You invoke with a **`thread_id`** (identity of the run/thread).

Conceptual flow:

```
invoke(inputs, config={"configurable": {"thread_id": ...}})
  -> Pregel loop computes step N
  -> checkpointer.put(...checkpoint snapshot...)
  -> later: checkpointer.get(...thread_id...) to resume/replay
```

System invariants:

- `thread_id` is the primary key for persistence; without it, “durable execution” is structurally impossible.
- Checkpoints carry **channel values + channel versions + metadata**; versions enable correct scheduling/resumption.

Backend variability:

- In-memory saver: for debug/test.
- SQLite saver: lightweight local durability.
- Postgres saver: production-grade durability (pooling, migrations, optional pgvector).

## Happy Path C: Long-Term “Memory” via Store (Documents + Retrieval)

**Core user intent:** “Persist information across threads/conversations, with optional retrieval by similarity.”

Two complementary mechanisms:

- **Checkpointing** remembers *run state* (short-term, per thread).
- **Store** remembers *artifacts/documents* (long-term, cross-thread).

Conceptual flow inside a node:

```
node(state, runtime):
  -> runtime.store.get/put/search(...)
  -> optional embeddings => vector index
  -> return state updates
```

Key constraints:

- The store API is **namespaced**, so callers must provide a logical namespace tuple (collection) + key.
- Vector search implies:
  - stable embedding dimensionality (`dims`)
  - a pluggable embeddings provider (LangChain `Embeddings` or a function)
  - backend-specific index/migration behavior (pgvector vs sqlite-vec)

## Happy Path D: “Run a Server” and Interact via CLI + SDK (Control Plane)

**Core user intent:** “Package graphs + deps, run them behind an API, and control runs remotely.”

In this repo, the server runtime is treated as **external** (a dependency), but the wiring is here.

Conceptual flow:

```
User terminal
  -> `langgraph ...` (click CLI)
  -> reads langgraph.json (graphs + deps + env + python version)
  -> orchestrates Docker images/containers
  -> (optionally) uses langgraph_sdk (httpx) to call the API:
       - create assistants/threads
       - start runs
       - stream events (SSE)
```

This yields an important architectural split:

- **Graph authoring/execution primitives** live in-process (core library).
- **Deployment + remote orchestration** is mediated through a *configuration schema* + *SDK* + *container boundary*.

## Where to Expect the “Interesting” Flow Logic

If you want to understand system behavior with minimal reading, prioritize these intent hotspots:

- **Graph compilation boundary:** graph DSL → executable engine.
- **Pregel loop boundary:** step scheduling + channel versioning + stream emission.
- **Persistence boundary:** checkpointer/store interfaces → backend adapters (SQLite/Postgres) + migrations.
- **Control plane boundary:** CLI config → Docker/runtime wiring → HTTP API via SDK.

