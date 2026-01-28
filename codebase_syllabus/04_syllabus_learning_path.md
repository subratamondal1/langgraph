# 04 — THE SYLLABUS (The Output)

This is a learning path that answers “How does this system work?” from first principles, moving from constraints → core mechanics → integrations.

## I. Foundations (Constraints and Packaging)

1. Monorepo shape and build orchestration
   - Root `Makefile` (fan-out across `libs/*`)
   - Per-library `Makefile` targets (`lint/format/test`, `uv sync`, etc.)
2. Packaging + dependency locking
   - Each `libs/*/pyproject.toml` (what each library *is*)
   - Each `libs/*/uv.lock` (pinned dependency graph)
3. CI expectations
   - `.github/workflows/*` (python version matrix; “no dirty working tree after tests”)

## II. The Core Model (What LangGraph *is*)

1. The import surface a user sees
   - `langgraph.graph` exports: `StateGraph`, `START`, `END`
   - `langgraph.pregel` exports: `Pregel`
2. The fundamental abstraction
   - Graph = nodes + edges + branching + state schema
   - Compile = convert declarative graph into an executable runnable
3. The runtime “context” concept
   - Run-scoped context, store, and streaming hooks (runtime/config patterns)

## III. Execution Engine (How Work Actually Runs)

1. Scheduling model
   - Pregel-style iteration: determine which nodes run based on channel versions / updates
2. State propagation
   - Channels define how values flow/merge between steps
3. Streaming + observability hooks
   - Stream modes, event emission, and custom stream writer patterns

## IV. Durability (How State Survives Time)

1. Checkpointing (short-term, versioned state)
   - Why `thread_id` exists and what it keys
   - What gets persisted (channel values/versions, metadata, pending writes)
2. Checkpointer backends (adapters)
   - In-memory: debugging/testing
   - SQLite: local durability
   - Postgres: production durability (pooling, migrations, optional vector extension)
3. Serialization layer
   - JSON+/msgpack-style typed payloads, optional encryption hooks

## V. Long-Term Memory Store (How Knowledge Persists)

1. Store semantics
   - Namespaces, keys, values, metadata, TTL
2. Retrieval semantics
   - Optional vector embeddings + ANN configuration
3. Backend behavior
   - SQLite vs Postgres migration/index differences

## VI. Prebuilt Components (Common Recipes)

1. “Agent-like” building blocks
   - Executors, tool nodes, interrupt/validation patterns
2. How prebuilt composes with the core
   - Prebuilt should feel like “opinionated graph templates” built atop the same compile/execute primitives

## VII. Interfaces (How Humans and Systems Touch It)

1. Python SDK (remote control)
   - Typed client, auth, errors, SSE streaming
2. CLI (operator workflow)
   - Config schema → docker orchestration → optional SDK calls
   - Template generation and schema validation

## VIII. Practice (Examples, Benchmarks, Tests)

1. Examples (`examples/`)
   - Use-case notebooks: agentic RAG, multi-agent, HITL, etc.
2. Benchmarks (`libs/langgraph/bench/`)
   - Performance probes for execution patterns
3. Tests (per-library)
   - Treat tests as executable documentation of the intended behavior and supported backends

