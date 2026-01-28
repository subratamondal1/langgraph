# LangGraph (Python) - The Error & Resilience Guide

This is a **Failure Mode Analysis (FMA)** for the Python `langgraph` namespace as implemented in this repo. It is written for SRE/production use: how it fails, how to detect it, and how to recover without waking someone up at 3 AM.

## 0. Method (“Grepping Expedition”)

I scanned the implementation for:
- `raise` (explicit failure paths)
- `assert` (invariant checks that can crash)
- `status_code` (HTTP error classification / retry semantics)

Primary hot paths analyzed:
- Graph runtime: `libs/langgraph/langgraph/pregel/main.py`, `libs/langgraph/langgraph/pregel/_runner.py`, `libs/langgraph/langgraph/pregel/_loop.py`
- Graph builder/validation: `libs/langgraph/langgraph/graph/state.py`
- Tool execution: `libs/prebuilt/langgraph/prebuilt/tool_node.py`
- Remote execution: `libs/langgraph/langgraph/pregel/remote.py`
- Persistence contracts/adapters: `libs/checkpoint/langgraph/*`, `libs/checkpoint-postgres/langgraph/*`, `libs/checkpoint-sqlite/langgraph/*`

## 1. Exception Hierarchy

### 1.1 “Root Exception” reality check

There is **no single `LangGraphError` / `LibraryError` base class**. The codebase uses a mix of:
- standard Python exceptions (`ValueError`, `TypeError`, `RuntimeError`, `TimeoutError`, etc.)
- a small set of LangGraph-specific exceptions
- third-party exceptions (e.g., `psycopg`, `sqlite3`, `httpx`, `requests`, `langgraph_sdk`, `langchain_core`)

The closest thing to a “framework-owned base” is **`GraphBubbleUp`**, but it represents **control-flow** more than failure.

### 1.2 Practical hierarchy (what you can catch)

```python
# Control-flow exceptions (not "errors" in the usual sense)
GraphBubbleUp (Exception)                              # libs/langgraph/langgraph/errors.py
├── GraphInterrupt (GraphBubbleUp)                     # raised internally for interrupts
│   └── NodeInterrupt (deprecated)                     # legacy
└── ParentCommand (GraphBubbleUp)                      # bubble Command to parent graph

# Runtime/graph failures
GraphRecursionError (RecursionError)                   # recursion_limit exceeded
InvalidUpdateError (Exception)                         # invalid node returns / invalid concurrent updates
EmptyInputError (Exception)                            # empty input
TaskNotFound (Exception)                               # distributed mode

# Remote execution wrapper
RemoteException (Exception)                            # libs/langgraph/langgraph/pregel/remote.py

# Checkpoint/channel plumbing
EmptyChannelError (Exception)                          # libs/checkpoint/langgraph/checkpoint/base/__init__.py

# Store / indexing validation
InvalidNamespaceError (ValueError)                     # libs/checkpoint/langgraph/store/base/__init__.py

# Tool execution (prebuilt)
ToolException (langchain_core.tools.base.ToolException)  # external dependency
└── ToolInvocationError (ToolException)                # libs/prebuilt/langgraph/prebuilt/tool_node.py

# Serialization / deserialization
InvalidModuleError (Exception)                         # libs/checkpoint/langgraph/checkpoint/serde/jsonplus.py
```

### 1.3 SRE takeaway (catch strategy)

Because there is no shared base, production callers should generally catch:
- **LangGraph semantics:** `GraphRecursionError`, `InvalidUpdateError`, `EmptyInputError`
- **Timeouts:** `TimeoutError` and `asyncio.TimeoutError`
- **Remote:** `RemoteException` (and whatever the SDK raises underneath)
- **Tool layer:** `ToolException` / `ToolInvocationError` if you’re using `ToolNode`
- **Vendor infra:** `psycopg.Error`, `sqlite3.Error`, `redis.exceptions.*`, `httpx.*`, `requests.*`

## 2. Hidden Failure Modes (Landmines)

These are the failure modes most likely to surprise a production service because they are either:
- raised as generic exceptions with message-only semantics, or
- arise only under concurrency/streaming, or
- are silently swallowed (masking a real incident).

### 2.1 Misconfiguration: checkpointer requires `thread_id` / configurable keys

**Symptom:** graph crashes early with a `ValueError` about missing configurable keys.

**Trigger:** enabling a checkpointer but calling `.invoke()` / `.stream()` without a `config` that contains `configurable.thread_id` (and optionally checkpoint ns/id).

**Source:** `libs/langgraph/langgraph/pregel/main.py` (`Pregel._defaults`)

What happens:
- `checkpointer` is present
- `config.get("configurable")` is missing → `ValueError("Checkpointer requires one or more ...")`

**SRE action:**
- Treat as **permanent / code bug** (fail fast).
- Add an application-layer guard: reject requests without `thread_id` when persistence is enabled.

---

### 2.2 Misconfiguration: `checkpointer=True` cannot be used for a root graph

**Symptom:** `RuntimeError("checkpointer=True cannot be used for root graphs.")`

**Trigger:** constructing a root `Pregel` (or `CompiledStateGraph`) with `checkpointer=True` instead of an actual saver.

**Source:** `libs/langgraph/langgraph/pregel/main.py` (`Pregel._defaults`)

**SRE action:** permanent; fix wiring. In production, always pass an actual saver instance (or `None`).

---

### 2.3 Infinite loop / no stop condition → `GraphRecursionError`

**Symptom:** `GraphRecursionError` with troubleshooting link and message about `recursion_limit`.

**Trigger:** graph runs out of steps without reaching a stop condition.

**Source:** `libs/langgraph/langgraph/pregel/main.py` (`Pregel.stream` / `Pregel.astream`)

**SRE action:**
- Treat as **permanent for that request** (logic bug or bad input); do not retry blindly.
- Add observability:
  - `recursion_limit` configured per request or per graph class
  - alarm on spikes
- Chaos drill: force a stop-condition regression and validate the service fails with a clear, user-facing error.

---

### 2.4 Streaming consumer backpressure → `TimeoutError` / `asyncio.TimeoutError`

**Symptom:** a stream/astream raises a timeout with message `"Timed out"`.

**Trigger:** when steps cannot complete within `graph.step_timeout`, including cases where:
- parallel tasks hang, or
- the consumer blocks long enough that backpressure prevents progress.

**Sources:**
- Timeout is raised by `_panic_or_proceed(...)`: `libs/langgraph/langgraph/pregel/_runner.py`
  - sync uses `TimeoutError`
  - async uses `asyncio.TimeoutError`
- `step_timeout` is passed into runner ticks from `Pregel.stream/astream`: `libs/langgraph/langgraph/pregel/main.py`

**SRE action:**
- Treat as **transient** if caused by downstream I/O; but also consider it as **resource exhaustion** if it’s caused by internal deadlocks/backpressure.
- Use a “timeout budget” per request and set `graph.step_timeout` defensively.
- Always catch both timeout classes:
  - `TimeoutError` (sync)
  - `asyncio.TimeoutError` (async)
- Ensure cancellations are handled (tasks are cancelled on timeout).

---

### 2.5 Control flow that looks like failure: interrupts are exceptions internally

**Symptom:** you might see `GraphInterrupt` (exception) when you expected an `"__interrupt__"` event/value.

**Why:** interrupts are implemented via raising `GraphInterrupt`, but the Pregel loop **suppresses** it only for top-level graphs.

**Source:** `libs/langgraph/langgraph/pregel/_loop.py` (`PregelLoop.__exit__`)
- Root graph (`not self.is_nested`) suppresses `GraphInterrupt` and emits interrupt data.
- Nested graphs do **not** suppress; the parent graph must handle it.

**SRE action:**
- Do not treat `GraphInterrupt` as a crash; treat it as **workflow state**:
  - surface interrupt payload to caller
  - require caller to resume with `Command(resume=...)`
- If you embed graphs as nodes/tools/subgraphs, ensure the parent executor expects interrupts.

---

### 2.6 “Invalid update” errors (often accidental complexity)

These show up when node returns don’t match the framework’s update contract or when multiple concurrent writes violate the channel semantics.

**Primary exception:** `InvalidUpdateError`

Common triggers (all are effectively “fatal for the request”):
- Node returns an unexpected type (not dict / not compatible with schema)
  - Source: `libs/langgraph/langgraph/graph/state.py` (`CompiledStateGraph.attach_node._get_updates`)
- `LastValue` receives multiple values in a single super-step
  - Source: `libs/langgraph/langgraph/channels/last_value.py`
- Multiple “overwrite” updates to a `BinaryOperatorAggregate` in one super-step
  - Source: `libs/langgraph/langgraph/channels/binop.py`
- Attempting to `Send` to `END` (invalid routing)
  - Source: `libs/langgraph/langgraph/graph/_branch.py`

**SRE action:**
- Treat as **permanent / code bug** (don’t retry).
- Convert to a structured, searchable error response (include node name and channel key).
- Add canary tests for “node return contract” before deployment.

---

### 2.7 Runtime dependency injection failures (store/config/runtime)

If your node signature requests injected args, LangGraph enforces them **at runtime** based on type hints.

**Symptom:** `ValueError("Missing required config key 'store' for '<name>'.")`

**Trigger:** a node/task requests a required dependency but graph is compiled without it.

**Source:** `libs/langgraph/langgraph/_internal/_runnable.py` (`RunnableCallable.invoke/ainvoke`)
- `store: BaseStore` is treated as required.
- `store: BaseStore | None` is treated as optional.

**SRE action:**
- Permanent (misconfiguration).
- Enforce a build-time policy:
  - if nodes require `store`, your graph factory must always compile with a store
  - or annotate store as optional.

---

### 2.8 Async/sync mismatch landmines

#### 2.8.1 Calling async tasks in a sync context
**Symptom:** `RuntimeError("In an sync context async tasks cannot be called")`

**Source:** `libs/langgraph/langgraph/pregel/_runner.py` (`_call`)

**SRE action:** permanent; ensure you use async entrypoints/graphs (`ainvoke/astream`) for async tasks.

#### 2.8.2 AsyncSqliteSaver sync calls from main loop
**Symptom:** `asyncio.InvalidStateError(...)` when calling sync methods on `AsyncSqliteSaver` from the main event loop.

**Source:** `libs/checkpoint-sqlite/langgraph/checkpoint/sqlite/aio.py`

**SRE action:** permanent; use async methods in async contexts.

#### 2.8.3 SqliteSaver doesn’t support async API
**Symptom:** `NotImplementedError` with an error message that instructs to use `AsyncSqliteSaver`.

**Source:** `libs/checkpoint-sqlite/langgraph/checkpoint/sqlite/__init__.py`

**SRE action:** permanent; choose the correct adapter for your execution model.

---

### 2.9 Serialization failures (checkpointing/caching) → “state not serializable”

When a checkpointer or cache is enabled, **inputs/outputs must be serializable** using the configured `SerializerProtocol`.

Common symptoms:
- `ormsgpack.MsgpackEncodeError` (default serializer cannot encode your object)
- `NotImplementedError("Unknown serialization type: ...")` (corrupt/unexpected persisted data)

**Sources:**
- `JsonPlusSerializer.dumps_typed/loads_typed`: `libs/checkpoint/langgraph/checkpoint/serde/jsonplus.py`
- Cache/store/checkpointer all transit through serializer:
  - `libs/checkpoint/langgraph/checkpoint/base/__init__.py`
  - `libs/checkpoint/langgraph/cache/*`

**SRE action:**
- Treat as **permanent** for that request (bad state contract).
- Fail fast with a clear error and surface a “serialization contract violated” metric.
- If you must support complex objects:
  - prefer converting to plain JSON types at the boundaries
  - avoid enabling `pickle_fallback` unless you fully trust your checkpoint store (security risk).

---

### 2.10 Store failures: invalid namespaces, TTL support, and embedding configuration

#### 2.10.1 Invalid namespace labels
**Symptom:** `InvalidNamespaceError` (a `ValueError`) with a precise message.

**Source:** `libs/checkpoint/langgraph/store/base/__init__.py` (`_validate_namespace`)

Constraints that can bite you:
- namespace cannot be empty
- labels must be strings
- labels cannot contain `.`
- root label cannot be `"langgraph"`

**SRE action:** permanent (input validation). Enforce namespaces at compile-time or via a single helper.

#### 2.10.2 TTL requested on adapters that don’t support TTL
**Symptom:** `NotImplementedError("TTL is not supported by ...")`

**Source:** `libs/checkpoint/langgraph/store/base/__init__.py` (`BaseStore.put`)

**SRE action:** permanent (configuration). Validate store capabilities at startup.

#### 2.10.3 Embedding provider string requires extra dependencies
**Symptom:** `ValueError` explaining that `langchain>=0.3.9` and provider packages are required.

**Source:** `libs/checkpoint/langgraph/store/base/embed.py` (`ensure_embeddings`)

**SRE action:** permanent; validate environment at service start (dependency + model/provider availability).

---

### 2.11 Tool execution failures (`ToolNode`) – the #1 crash source in agent stacks

If you run tool-calling workflows, most production incidents originate here.

Key failure modes:

#### 2.11.1 Missing/invalid message state
**Symptoms:**
- `ValueError("No message found in input")`
- `ValueError("No AIMessage found in input")`
- `ValueError("No messages found in input state to tool_edge: ...")`

**Sources:**
- `ToolNode._parse_input`: `libs/prebuilt/langgraph/prebuilt/tool_node.py`
- `tools_condition`: `libs/prebuilt/langgraph/prebuilt/tool_node.py`

**SRE action:** permanent (input contract). Validate state schema before invoking ToolNode.

#### 2.11.2 Tool returns the wrong type
**Symptom:** `TypeError("Tool <name> returned unexpected type: ...")`

**Source:** `ToolNode._execute_tool_sync/_execute_tool_async`

**SRE action:** permanent (tool contract). Unit-test tools in isolation and enforce return types.

#### 2.11.3 Tool argument validation errors (pydantic)
**Symptom:** `ToolInvocationError(...)` wrapping a `pydantic.ValidationError`

**Source:** `ToolNode._execute_tool_sync/_execute_tool_async` wraps validation failures.

**SRE action:** permanent for that request (LLM asked for invalid args). Return error ToolMessage and continue, rather than crashing.

#### 2.11.4 Missing store when tool expects `InjectedStore`
**Symptom:** `ValueError("Cannot inject store into tools with InjectedStore annotations - please compile your graph with a store.")`

**Source:** `ToolNode._inject_tool_args`

**SRE action:** permanent; enforce “store required” at graph factory time.

#### 2.11.5 Tool returns `Command(update=...)` without matching `ToolMessage`
**Symptom:** `ValueError(...)` explaining that every tool call must have a corresponding `ToolMessage`.

**Source:** `ToolNode._validate_tool_command`

**SRE action:** permanent; treat as tool implementation bug.

#### 2.11.6 “Handle tool errors” can either swallow or crash

`ToolNode(handle_tool_errors=...)` defines whether tool exceptions become:
- an error `ToolMessage(status="error")` (graph continues), or
- a raised exception (graph fails).

**Source:** `ToolNode._execute_tool_sync/_execute_tool_async`

**SRE action:** for production, explicitly choose a policy:
- If you want the workflow to keep running, set `handle_tool_errors` to:
  - `True` (catch-all) or
  - an exception type/tuple or
  - a typed handler function that returns a safe string.
- If you want strict failure, set `handle_tool_errors=False` and catch exceptions at the service boundary.

---

### 2.12 Remote execution failure semantics (`RemoteGraph`)

`RemoteGraph` is a client-side proxy. It can fail in 3 distinct ways:

1) **Local configuration error**
- `ValueError` if async/sync client isn’t initialized.
- Source: `_validate_client/_validate_sync_client` in `libs/langgraph/langgraph/pregel/remote.py`

2) **Remote “error” stream events**
- `RemoteException(chunk.data)` on `error` stream events.
- Source: `RemoteGraph.stream/astream` in `libs/langgraph/langgraph/pregel/remote.py`

3) **Interrupt/control-flow bubbling**
- Raises `ParentCommand(...)` or `GraphInterrupt(...)` when those stream events occur (typically when used as a subgraph).
- Source: `RemoteGraph.stream/astream`

**SRE action:**
- Treat `RemoteException` as **transient or permanent based on payload** (you own the policy).
- Add a circuit breaker + exponential backoff around remote runs.
- Log full payload (it is the only structured clue you may get).

---

### 2.13 “Silent degradation” is a failure mode too (Redis cache)

`RedisCache` catches broad exceptions and returns empty results / no-ops writes if Redis is down.

**Source:** `libs/checkpoint/langgraph/cache/redis/__init__.py`

Impact:
- Your system may “work” but recompute everything.
- Incidents can hide until latency/cost spikes.

**SRE action:**
- Add explicit Redis health checks + alerts.
- Track cache hit rate and “cache backend error count”.
- Consider wrapping `RedisCache` with logging on exception paths.

---

### 2.14 Assertions (hard crashes) – treat as “should never happen”

There are `assert` statements in production code that enforce internal invariants. If they fire, you likely have:
- state corruption
- a concurrency bug
- a mismatch between resume state and interrupt ordering

Notable locations:
- Interrupt resume invariants: `libs/langgraph/langgraph/types.py` (inside `interrupt()`)
- Task id checksum invariants: `libs/langgraph/langgraph/pregel/_algo.py`
- Encryption ciphername invariant: `libs/checkpoint/langgraph/checkpoint/serde/encrypted.py`

**SRE action:**
- Treat as **fatal** (page someone).
- Capture full context (thread_id, checkpoint_ns/id, graph name, last events).

## 3. HTTP Status Code Handling & Retries

### 3.1 Default retry classification (what’s automatic vs not)

LangGraph’s default retry predicate is `default_retry_on(exc)`.

**Source:** `libs/langgraph/langgraph/_internal/_retry.py`

Behavior:
- Retries:
  - `ConnectionError`
  - `httpx.HTTPStatusError` with **5xx**
  - `requests.HTTPError` with **5xx**, or with no response
- Does **not** retry:
  - common programming errors (`ValueError`, `TypeError`, etc.)
- Crucially: **429 is not retried by default** (it is not 5xx).

### 3.2 SRE guidance for rate limiting (429)

If you use an HTTP client that raises `httpx.HTTPStatusError` for 429, you must implement a custom `RetryPolicy.retry_on` that treats 429 as retryable and adds backoff/jitter.

Example pattern:
```python
import httpx
from langgraph.types import RetryPolicy

def retry_on_http(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, ConnectionError)

policy = RetryPolicy(
    max_attempts=5,
    initial_interval=0.5,
    backoff_factor=2.0,
    jitter=True,
    retry_on=retry_on_http,
)
```

## 4. Recovery Playbook (Actionable Defense)

This section maps error categories to concrete actions you can implement at the service boundary.

### 4.1 Transient failures (Retryable)

**Typical exceptions**
- `TimeoutError` / `asyncio.TimeoutError` (step timeout)
- `ConnectionError` (network)
- `RemoteException` (remote server transient)
- vendor connection errors (e.g., psycopg connection drop)

**SRE action**
- Wrap outer invocation in a retry loop (tenacity / exponential backoff + jitter).
- Add a circuit breaker for `RemoteGraph` and DB-backed checkpointers/stores.
- Enforce time budgets:
  - set `graph.step_timeout`
  - set client-level timeouts for HTTP/DB

### 4.2 Permanent failures (Do not retry)

**Typical exceptions**
- `InvalidUpdateError` (node return contract / channel semantics violated)
- `GraphRecursionError` (no stop condition)
- `ValueError`/`TypeError` from:
  - `StateGraph.validate` / compilation
  - `ToolNode` contract mismatches (missing AIMessage, wrong Command.update shape)
  - invalid namespaces / TTL unsupported
  - serialization failures (`MsgpackEncodeError`)

**SRE action**
- Fail fast and return a 4xx/5xx depending on blame:
  - caller input invalid → 4xx
  - developer wiring bug → 5xx + alert
- Add guardrails:
  - validate state schema and tool return types in CI
  - enforce `thread_id` presence when checkpointer is enabled

### 4.3 Resource / load shedding failures

**Typical signals**
- repeated timeouts
- recursion-limit spikes (graphs stuck in loops)
- cache backend silently failing (latency/cost spike)
- rate limiting (429) if you add it to retry set

**SRE action**
- Apply backpressure:
  - queue requests
  - cap concurrency
  - add per-tenant rate limits
- If 429:
  - respect `Retry-After` if available
  - add jittered exponential backoff
- Use DLQ / “workflow failed” persistence if the request can be resumed later.

### 4.4 Control-flow events (Handle, don’t crash)

**Events**
- `GraphInterrupt` / interrupt payloads (`"__interrupt__"`)
- `ParentCommand` (command bubbled to parent)

**SRE action**
- Treat as workflow state:
  - persist it
  - return it to caller
  - resume with `Command(resume=...)`
- Ensure subgraph/tool embedding paths don’t accidentally treat these as fatal exceptions.

## 5. Chaos Experiments (Suggested)

Run these in staging to ensure your service degrades predictably:

1) **Kill Redis** (if using `RedisCache`) and confirm:
   - requests still succeed
   - cache hit rate drops to ~0
   - latency/cost alarms fire (because the library won’t throw)

2) **Cut Postgres connections** (if using Postgres saver/store) and confirm:
   - errors bubble as vendor exceptions (you catch and retry/circuit-break)
   - you don’t lose “thread_id” correlation in logs

3) **Introduce a tool that raises** (e.g., `ValueError`) and verify:
   - with `handle_tool_errors=True`, graph continues and emits an error ToolMessage
   - with `handle_tool_errors=False`, your service boundary catches and reports a clean failure

4) **Force an infinite loop regression** and validate:
   - `GraphRecursionError` is raised
   - the request fails fast within your SLO budget

