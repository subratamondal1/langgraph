# 02 — THE ANATOMY (The Map)

This is a map of the repo organized by **intent** (what each area *does*), not by folder names alone.

## Top-Level Layout (Intent-Based)

### A) Product libraries (publishable)

All production code lives under `libs/` (monorepo).

- **Core orchestration engine:** `libs/langgraph/`
- **Checkpointing base interfaces + in-memory/redis adapters:** `libs/checkpoint/`
- **Checkpointing + store backends:**
  - `libs/checkpoint-postgres/` (Postgres + pgvector)
  - `libs/checkpoint-sqlite/` (SQLite + sqlite-vec)
- **High-level “recipes” / building blocks:** `libs/prebuilt/`
- **External interaction surfaces:**
  - `libs/sdk-py/` (Python SDK for LangGraph Server API)
  - `libs/cli/` (CLI for interacting with / running LangGraph API server)
  - `libs/sdk-js/` (present, but appears as a placeholder in this snapshot)

### B) Learning & demonstrations

- `examples/`: notebooks and small scripts demonstrating use-cases (RAG, multi-agent, HITL, etc.)

### C) Repo operations / governance

- `.github/`: CI workflows, release automation, tooling scripts.
- Root `Makefile`: fan-out runner for per-library `make lint/format/test/lock`.

## The “Big Bang” Entry Points (Where Execution Begins)

Because this is a framework repo, there are multiple “entry points” depending on how the system is used.

### 1) CLI entry point (user runs a command)

- Console script: `langgraph`
- Defined in `libs/cli/pyproject.toml` (`[project.scripts]`)
- Dispatches into: `libs/cli/langgraph_cli/cli.py:cli`
- Module runner: `python -m langgraph_cli` via `libs/cli/langgraph_cli/__main__.py`

Intent: translate CLI commands + config into Docker/runtime actions, and optionally use the SDK to talk to a running API server.

### 2) Core library entry points (developer imports and runs graphs)

Primary import surface (graph authoring):

- `from langgraph.graph import StateGraph, START, END`
- Exported from `libs/langgraph/langgraph/graph/__init__.py`

Execution engine surface:

- `from langgraph.pregel import Pregel`
- Exported from `libs/langgraph/langgraph/pregel/__init__.py`

### 3) Python SDK entry points (developer talks to LangGraph Server API)

- `from langgraph_sdk import get_client, get_sync_client`
- Exported from `libs/sdk-py/langgraph_sdk/__init__.py`
- Core client implementation lives in `libs/sdk-py/langgraph_sdk/client.py`

### 4) Benchmark harness (performance investigation)

- `python -m bench` runs `libs/langgraph/bench/__main__.py`

## Intent-Based Subsystem Map

### 1) Core orchestration (“Business logic” of the framework)

Location: `libs/langgraph/langgraph/`

By intent:

- **Graph authoring DSL:** `langgraph/graph/` (state/message graphs, node/edge composition, compile step)
- **Execution engine:** `langgraph/pregel/` (step scheduling, checkpoint integration, streaming, retries)
- **State transport primitives:** `langgraph/channels/` (how values flow and merge between nodes)
- **Run-scoped utilities:** `langgraph/runtime.py`, `langgraph/config.py` (context/store/stream-writer access patterns)
- **Internal helpers:** `langgraph/_internal/` (private utilities, typing, config packing)

### 2) Persistence (“Durable execution”)

Locations:

- Interfaces + core types: `libs/checkpoint/langgraph/checkpoint/`
- Implementations:
  - `libs/checkpoint/langgraph/checkpoint/memory/` (in-memory saver)
  - `libs/checkpoint-sqlite/langgraph/checkpoint/sqlite/` (SQLite saver)
  - `libs/checkpoint-postgres/langgraph/checkpoint/postgres/` (Postgres saver)

Intent boundaries:

- **Base protocol** defines what the engine needs (get/list/put checkpoints; store pending writes).
- **Backend adapters** translate those primitives into DB operations and migrations.

### 3) Long-term memory store (“Documents + retrieval”)

Locations:

- Interfaces + core ops/types: `libs/checkpoint/langgraph/store/base/`
- Implementations:
  - `libs/checkpoint-sqlite/langgraph/store/sqlite/`
  - `libs/checkpoint-postgres/langgraph/store/postgres/`

Key capabilities (architectural intent):

- Namespaced KV store with metadata (created_at/updated_at)
- TTL support
- Optional vector index + embedding hooks (pluggable embeddings, ANN configs)

### 4) Prebuilt components (“Batteries included”)

Location: `libs/prebuilt/langgraph/prebuilt/`

Intent:

- Provide higher-level graph patterns (agent executors, tool nodes, interrupts, validators) built on top of the core DSL + engine.

### 5) External I/O layers (interfaces to the outside world)

- **CLI:** `libs/cli/langgraph_cli/` (config parsing, docker orchestration, templates, schema)
- **SDK:** `libs/sdk-py/langgraph_sdk/` (HTTP transport, auth, streaming/SSE, typed schema objects)

## Cross-Library Dependency Shape (High-Level)

- `checkpoint` is a foundational dependency for:
  - `checkpoint-postgres`, `checkpoint-sqlite`, `prebuilt`, `langgraph`
- `prebuilt` feeds into:
  - `langgraph`
- `sdk-py` is used by:
  - `cli` (and is also a standalone library)

The core concept: **execution + durability** lives in the `langgraph` namespace, while **distribution boundaries** are split across independent packages.

