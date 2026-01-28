# 01 — THE PHYSICS (The Constraints)

This repo is a **Python monorepo** for LangGraph: a framework for building **stateful, long-running agent/workflow graphs** with optional durability (checkpoints + memory stores) and optional deployment via an external API server.

The goal of this document is to enumerate the “immutable truths” that constrain architecture and dictate how the system *must* behave.

## Immutable Truths

### 1) Languages & Runtime Model

- **Primary language:** Python.
- **Supported Python:** packages declare `requires-python >= 3.10`; CI tests across **3.10 → 3.14**.
- **Execution style:** a mix of **sync + asyncio**. Many interfaces offer both sync and async variants; tests use `pytest-asyncio`.
- **Important runtime constraint:** some “run context” utilities are powered by `contextvars` propagation and warn that **Python < 3.11** has limitations in async contexts (because task context propagation differs).
- **JavaScript/TypeScript:** present as **examples** under `libs/cli/**` (not a core runtime package here).

### 2) Packaging Topology: One Namespace, Many Distributions

The repo is split into multiple publishable libraries under `libs/`, but many of them contribute to the same **implicit namespace package**: `langgraph/*` (notice the absence of `langgraph/__init__.py`).

Implications / constraints:

- **Modular backends:** optional functionality (e.g., `langgraph.checkpoint.postgres`, `langgraph.store.sqlite`) can ship in separate wheels without bloating the core.
- **Tight coordination:** multiple distributions must agree on shared types/protocols and avoid import/name collisions under the same namespace.
- **Versioning coupling:** release versions across packages are intentionally aligned (e.g., `langgraph` and `langgraph-prebuilt` share versioning cadence).

### 3) Build / Toolchain Choices

- **Build system:** PEP 517 via `hatchling` (per-library `pyproject.toml`).
- **Dependency management:** `uv` with a per-library `uv.lock` (reproducible, pinned dependency graphs).
- **Dev workflow:** `Makefile` targets per library; root `Makefile` fans out across `libs/*`.
- **Quality gates:** `ruff` (format + lint), `mypy` (typing), `pytest` (tests); CI enforces clean git status after tests.

Architectural implications:

- **Per-library isolation** is expected (each library can be tested/linted independently).
- **Cross-library development** is supported via editable path sources (`tool.uv.sources` in some libraries), making the monorepo behave like a single coherent workspace.

### 4) Hard Dependencies (Architectural Building Blocks)

These are the “gravity wells” around which the design orbits:

- **`langchain-core`**: provides the `Runnable` model / `RunnableConfig` patterns that LangGraph compiles into and executes within.
- **`pydantic>=2`**: strongly suggests structured state/config schemas and validation.
- **Performance-focused serialization:** `orjson`, `ormsgpack` (fast JSON + msgpack-style payloads).
- **CLI framework:** `click` for the `langgraph` CLI entrypoint.
- **HTTP client:** `httpx` (used by the Python SDK to talk to an external LangGraph API).

### 5) Persistence & “Memory” Are First-Class

Durability exists in two distinct layers (both optional, but architecturally central):

1) **Checkpointing (“short-term, versioned state”)**
   - A checkpointer saves **graph execution snapshots** keyed by `thread_id`.
   - Multiple implementations exist:
     - In-memory (debug/test)
     - SQLite (async via `aiosqlite`, vector via `sqlite-vec`)
     - Postgres (via `psycopg`, pooling via `psycopg-pool`, vector via `pgvector`)

2) **Store (“long-term memory / documents”)**
   - A persistent, namespaced key-value store that supports:
     - TTL
     - Optional vector search over embedded fields
   - Implementations exist for SQLite and Postgres.

Architectural implications:

- The “core engine” must be written such that **storage is pluggable** (protocols/interfaces in the base packages, concrete adapters in backend packages).
- A **thread/run identity** (`thread_id`, and often checkpoint namespaces) is foundational to correctness.

### 6) External Systems Are Expected in the Full Experience

- **Docker is a first-class dev/test dependency** for some libraries (tests start Postgres and Redis via `docker compose`).
- The CLI’s “dev/up” workflow references an **external** LangGraph API server runtime (`langgraph-api`, `langgraph-runtime-inmem`) that is *not implemented* in this repo, but integrated via dependencies.

Architectural implications:

- This repo is primarily a **framework + adapters + client tooling**, not “the server”.
- The system boundary includes:
  - local execution (pure Python)
  - optional local infra (Postgres/Redis)
  - optional remote execution (LangGraph API server), accessed via SDK/CLI

## Architectural Limits (By First Principles)

### What this repo is *not*

- Not a single deployable application with one `main()` entrypoint.
- Not a JS frontend (JS/TS present here is example scaffolding).
- Not the LangGraph API server implementation (that appears as external dependencies used by the CLI).

### What it must optimize for

- **Composable orchestration primitives** (graph building + execution engine).
- **Determinism + resumability** (checkpoint identities, channel versions, metadata).
- **Pluggable persistence** (SQLite/Postgres backends, serialization layers).
- **Multi-surface UX** (Python import surface + CLI + SDK).

