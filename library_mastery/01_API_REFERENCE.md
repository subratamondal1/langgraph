# LangGraph (Python) - The Unabridged API Reference

This document is a **source-derived** reference for the **Python `langgraph` namespace** as implemented in this repository (a monorepo). It is intended to expose the **real public surface area** (and the “public-by-import” surface) that developers actually touch, including optional adapters and semi-public utilities that are easy to miss.

> Scope note: this file focuses on the **Python library surface** (`langgraph.*`). The CLI (`langgraph-cli`) and the server SDK (`langgraph-sdk`) are companion projects and are only referenced when the core library depends on them (e.g., `RemoteGraph`).

Hands-on companion: runnable examples live in `library_mastery/01_API_REFERENCE/` (start with `01_core_entry_points/00_cookbook.py`, then follow the numbered folders).

## 0. Package Topology (Namespace Packaging)

`langgraph` is a **PEP 420 namespace package** in this repo: there is no `langgraph/__init__.py`. The namespace is composed from multiple distributions under `libs/`:

- Core framework: `libs/langgraph/langgraph/*` (distributed as `langgraph`)
- Checkpoint + store + cache base interfaces and in-memory impls: `libs/checkpoint/langgraph/*` (distributed as `langgraph-checkpoint`)
- Postgres checkpoint/store impls: `libs/checkpoint-postgres/langgraph/*` (distributed as `langgraph-checkpoint-postgres`)
- SQLite checkpoint/store/cache impls: `libs/checkpoint-sqlite/langgraph/*` (distributed as `langgraph-checkpoint-sqlite`)
- Prebuilt agent/tool helpers: `libs/prebuilt/langgraph/*` (distributed as `langgraph-prebuilt`)

Practical implication:
- “Entry points” are submodules like `langgraph.graph`, `langgraph.pregel`, `langgraph.func`, etc.
- Many important public APIs are reachable via `langgraph.<domain>.<adapter>` where `<domain>` has **no** `__init__.py` (e.g. `langgraph.checkpoint.sqlite`, `langgraph.store.postgres`).

## 1. Core Entry Points (Public Exports)

These are the main “you should start here” modules. Each lists its `__all__` exports (where present).

### `langgraph.graph`
**Source File:** `libs/langgraph/langgraph/graph/__init__.py`

Exports:
- `START`, `END` (from `langgraph.constants`)
- `StateGraph` (builder)
- Message helpers: `add_messages`, `MessagesState`, `MessageGraph` (**deprecated**)

### `langgraph.pregel`
**Source File:** `libs/langgraph/langgraph/pregel/__init__.py`

Exports:
- `Pregel` (runtime/execution engine)
- `NodeBuilder` (builder for `PregelNode`)

### `langgraph.func`
**Source File:** `libs/langgraph/langgraph/func/__init__.py`

Exports:
- `task` (decorator)
- `entrypoint` (decorator class that returns a compiled `Pregel`)

### `langgraph.channels`
**Source File:** `libs/langgraph/langgraph/channels/__init__.py`

Exports (channel primitives):
- Base: `BaseChannel`
- Value channels: `AnyValue`, `LastValue`, `LastValueAfterFinish`, `UntrackedValue`, `EphemeralValue`
- Reducer channel: `BinaryOperatorAggregate`
- Barrier channels: `NamedBarrierValue`, `NamedBarrierValueAfterFinish`
- Topic channel: `Topic`

### `langgraph.runtime`
**Source File:** `libs/langgraph/langgraph/runtime.py`

Exports:
- `Runtime`
- `get_runtime`

### `langgraph.config`
**Source File:** `libs/langgraph/langgraph/config.py`

Exports:
- `get_config`
- `get_store`
- `get_stream_writer`

### `langgraph.types`
**Source File:** `libs/langgraph/langgraph/types.py`

Exports (control-plane + contracts):
- Literals: `All`, `Durability`, `StreamMode`
- Helpers: `ensure_valid_checkpointer`
- Retry/cache config: `RetryPolicy`, `CachePolicy`
- Interrupts/control: `Interrupt`, `interrupt`, `Send`, `Command`, `Overwrite`
- Execution/state objects: `StateUpdate`, `PregelTask`, `PregelExecutableTask`, `StateSnapshot`
- Stream plumbing: `StreamWriter`

### `langgraph.errors`
**Source File:** `libs/langgraph/langgraph/errors.py`

Exports:
- `ErrorCode` (enum for troubleshooting links)
- `GraphRecursionError`, `InvalidUpdateError`
- `GraphInterrupt` (raised internally for interrupts), `NodeInterrupt` (**deprecated**)
- `ParentCommand` (bubble a `Command` to the parent graph)
- `EmptyInputError`, `TaskNotFound`
- `EmptyChannelError` (re-exported from `langgraph.checkpoint.base`)

### `langgraph.constants`
**Source File:** `libs/langgraph/langgraph/constants.py`

Exports:
- Public constants: `START`, `END`, `TAG_NOSTREAM`, `TAG_HIDDEN`
- Back-compat (deprecated / “please don’t use”): `CONF`, `TASKS`, `CONFIG_KEY_CHECKPOINTER`
- A `__getattr__` that **warns** and proxies deprecated constants/types.

### `langgraph.managed`
**Source File:** `libs/langgraph/langgraph/managed/__init__.py`

Exports:
- `IsLastStep`
- `RemainingSteps`

### `langgraph.prebuilt` (optional, shipped as dependency of `langgraph`)
**Source File:** `libs/prebuilt/langgraph/prebuilt/__init__.py`

Exports:
- `ToolNode`, `tools_condition`
- `ToolRuntime`, `InjectedState`, `InjectedStore`
- `create_react_agent` (**deprecated**)
- `ValidationNode` (**deprecated**)

## 2. Graph Construction (`langgraph.graph`)

### `StateGraph`
**Source File:** `libs/langgraph/langgraph/graph/state.py`
**Description:** Builder for a shared-state graph where nodes read `State` and return partial updates that are merged via per-field reducers; compiles to a `CompiledStateGraph` (a `Pregel`).

#### Constructor / Configuration
| Param | Type | Default | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `state_schema` | `type[StateT]` | **Required** | The schema defining state keys and optional reducers (`Annotated[field_type, reducer]`). |
| `context_schema` | `type[ContextT] \| None` | `None` | Schema for immutable run-scoped context injected via `Runtime[ContextT]`. |
| `input_schema` | `type[InputT] \| None` | `None` | Optional separate input schema; defaults to `state_schema`. |
| `output_schema` | `type[OutputT] \| None` | `None` | Optional separate output schema; defaults to `state_schema`. |
| `**kwargs` | `DeprecatedKwargs` | — | Deprecated keys supported: `config_schema` → `context_schema`; `input` → `input_schema`; `output` → `output_schema`. |

#### Critical Methods (Builder DSL)
- `add_node(...)`: Add a node (callable or Runnable). Supports naming, per-node `retry_policy`, `cache_policy`, `metadata`, `defer`, and optional `input_schema`.
- `add_edge(start_key: str | list[str], end_key: str)`: Add directed edge; list means “wait for all starts”.
- `add_conditional_edges(source: str, path: Callable|Runnable, path_map: dict|list|None = None)`: Route dynamically based on `path` return value(s) (node names, `END`, or via `path_map`).
- `add_sequence(...)`: Convenience to wire nodes sequentially.
- `set_entry_point(key: str)`: Equivalent to `add_edge(START, key)`.
- `set_conditional_entry_point(path, path_map=None)`: Conditional routing from `START`.
- `set_finish_point(key: str)`: Equivalent to `add_edge(key, END)`.
- `validate(interrupt: Sequence[str] | None = None)`: Structural validation and interrupt target validation.
- `compile(checkpointer=None, *, cache=None, store=None, interrupt_before=None, interrupt_after=None, debug=False, name=None) -> CompiledStateGraph`: Produce an executable graph.

#### Hidden Config / Edge Cases
- Reserved nodes: `START` cannot be an end node; `END` cannot be a start node.
- Managed values in schema:
  - Allowed in `state_schema`
  - **Forbidden** in `input_schema` / `output_schema` (raises `ValueError`).

---

### `CompiledStateGraph`
**Source File:** `libs/langgraph/langgraph/graph/state.py`
**Description:** Executable graph produced by `StateGraph.compile()`. It is a `Pregel` specialized for shared-state graphs.

#### Constructor / Configuration
This class is constructed by `StateGraph.compile()`; its effective runtime config is the underlying `Pregel` configuration (see `Pregel` below).

#### Public Methods (Adds to `Pregel`)
- `get_input_jsonschema(config=None) -> dict`: JSON schema for `input_schema`.
- `get_output_jsonschema(config=None) -> dict`: JSON schema for `output_schema`.

#### Internal-but-useful Hooks (for advanced/extenders)
- `attach_node(...)`, `attach_edge(...)`, `attach_branch(...)`: Used by compilation/graph wiring.
- `_migrate_checkpoint(...)`: Handles checkpoint format migrations during execution.

---

### Message State Helpers

#### `add_messages(left, right, *, format=None)`
**Source File:** `libs/langgraph/langgraph/graph/message.py`
**Description:** Reducer for append-only-ish message lists with ID-based replacement and deletions.

Key behaviors:
- Accepts single message or list on each side.
- Ensures messages have IDs (assigns UUIDs where missing).
- Supports deleting by sending a `RemoveMessage` with a matching `id`.
- Supports “delete all” via `RemoveMessage(id="__remove_all__")`.
- Optional `format="langchain-openai"` converts to OpenAI-style `BaseMessage` formatting (requires newer `langchain-core`).

#### `MessagesState`
**Source File:** `libs/langgraph/langgraph/graph/message.py`
**Description:** `TypedDict` schema: `{"messages": Annotated[list[AnyMessage], add_messages]}`.

#### `MessageGraph` (**deprecated**)
**Source File:** `libs/langgraph/langgraph/graph/message.py`
**Description:** Deprecated convenience graph where the entire state is a message list; internally a `StateGraph` over `Annotated[list[AnyMessage], add_messages]`.

---

### UI Streaming Helpers (`langgraph.graph.ui`)
These are not re-exported from `langgraph.graph`, but are public in their module.

#### `UIMessage`, `RemoveUIMessage`, `AnyUIMessage`
**Source File:** `libs/langgraph/langgraph/graph/ui.py`
**Description:** TypedDict contracts for UI events emitted via `stream_mode="custom"` and optionally stored in state.

#### `push_ui_message(name, props, *, id=None, metadata=None, message=None, state_key="ui", merge=False) -> UIMessage`
**Source File:** `libs/langgraph/langgraph/graph/ui.py`
**Description:** Emits a UI event to the stream writer and optionally appends to state under `state_key`.

Hidden behaviors:
- Adds run metadata (`run_id`, tags, run_name) automatically from `RunnableConfig`.
- If `merge=True`, consumers are expected to merge props with existing UI message state (also supported by reducer).

#### `delete_ui_message(id, *, state_key="ui") -> RemoveUIMessage`
**Source File:** `libs/langgraph/langgraph/graph/ui.py`

#### `ui_message_reducer(left, right) -> list[AnyUIMessage]`
**Source File:** `libs/langgraph/langgraph/graph/ui.py`
**Description:** Reducer supporting “remove-ui” messages and optional prop-merging.

## 3. Execution Engine (`langgraph.pregel`)

### `NodeBuilder`
**Source File:** `libs/langgraph/langgraph/pregel/main.py`
**Description:** Fluent builder for `PregelNode` specs (subscribe → do → write), used when constructing a `Pregel` directly.

#### Constructor / Configuration
| Param | Type | Default | Description & Constraints |
| :--- | :--- | :--- | :--- |
| *(no args)* | — | — | Initializes an empty node definition. |

#### Critical Methods (Fluent API)
- `subscribe_only(channel: str)`: Subscribe to a single input channel; mutually exclusive with multi-subscribe.
- `subscribe_to(*channels: str, read: bool = True)`: Subscribe to multiple channels; optionally do not include their values in input.
- `read_from(*channels: str)`: Read extra channels without subscribing/triggers.
- `do(node: RunnableLike)`: Append a runnable step (composes into a `RunnableSeq`).
- `write_to(*channels: str | ChannelWriteEntry, **kwargs)`: Add writes to channels (static values or mapper callables).
- `meta(*tags: str, **metadata)`: Add tags/metadata.
- `add_retry_policies(*policies: RetryPolicy)`: Per-node retry policies.
- `add_cache_policy(policy: CachePolicy)`: Per-node cache policy.
- `build() -> PregelNode`: Materialize the spec.

---

### `Pregel`
**Source File:** `libs/langgraph/langgraph/pregel/main.py`
**Description:** Core runtime implementing a bulk-synchronous parallel (Pregel-like) execution model over channels and actor nodes; also serves as the executable surface for compiled graphs.

#### Constructor / Configuration
| Param | Type | Default | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `nodes` | `dict[str, PregelNode \| NodeBuilder]` | **Required** | Node definitions keyed by node id/name. |
| `channels` | `dict[str, BaseChannel \| ManagedValueSpec] \| None` | **Required** | Channel specs and managed value specs. `None` becomes `{}`. |
| `auto_validate` | `bool` | `True` | Validate graph/channel wiring immediately. |
| `stream_mode` | `StreamMode` | `"values"` | Default stream mode for `.stream()`/`.astream()`. |
| `stream_eager` | `bool` | `False` | If `True`, stream output “eagerly” (used by functional API). |
| `output_channels` | `str \| Sequence[str]` | **Required** | Channel(s) returned by `.invoke()` and emitted under `"values"` streaming. |
| `stream_channels` | `str \| Sequence[str] \| None` | `None` | Channel(s) to stream by default (falls back to `output_channels` / internal defaults). |
| `interrupt_after_nodes` | `All \| Sequence[str]` | `()` | Nodes to interrupt after. |
| `interrupt_before_nodes` | `All \| Sequence[str]` | `()` | Nodes to interrupt before. |
| `input_channels` | `str \| Sequence[str]` | **Required** | Channel(s) that accept user input. |
| `step_timeout` | `float \| None` | `None` | Per-step timeout in seconds. |
| `debug` | `bool \| None` | `None` | Enable debug mode (defaults to env/config via `get_debug()`). |
| `checkpointer` | `Checkpointer` | `None` | Checkpointer config: `None` inherit, `False` disable, saver instance, or `True` for “subgraph uses parent saver” (not allowed on root). |
| `store` | `BaseStore \| None` | `None` | Optional persistent store shared via runtime. |
| `cache` | `BaseCache \| None` | `None` | Optional cache for node/task results. |
| `retry_policy` | `RetryPolicy \| Sequence[RetryPolicy]` | `()` | Graph-wide retry policies (nodes can override). |
| `cache_policy` | `CachePolicy \| None` | `None` | Graph-wide cache policy (nodes can override). |
| `context_schema` | `type[ContextT] \| None` | `None` | Schema for runtime context injected into nodes via `Runtime[ContextT]`. |
| `config` | `RunnableConfig \| None` | `None` | Base config merged into invocation config. |
| `trigger_to_nodes` | `Mapping[str, Sequence[str]] \| None` | `None` | Advanced: explicit trigger routing map (defaults to `{}`). |
| `name` | `str` | `"LangGraph"` | Display name. |
| `**deprecated_kwargs` | `DeprecatedKwargs` | — | Deprecated key supported: `config_type` → `context_schema`. |

#### Critical Methods (Execution Surface)
- Graph structure:
  - `get_graph(config=None, *, xray: int|bool = False)`
  - `aget_graph(config=None, *, xray: int|bool = False)`
  - `get_subgraphs()` / `aget_subgraphs()`
- Runtime configuration:
  - `copy(update: dict)` (returns modified copy)
  - `with_config(config=None, **kwargs)` (merges configs)
  - `validate()`
- Schemas (some deprecated):
  - `get_input_schema()` / `get_output_schema()` and JSON schema variants
  - `get_context_jsonschema()`
- State inspection:
  - `get_state(config, *, subgraphs=False)` / `aget_state(...)`
  - `get_state_history(config, *, filter=None, before=None, limit=None)` / async variant
- State updates:
  - `update_state(config, values, as_node=None, task_id=None)` / `aupdate_state(...)`
  - `bulk_update_state(config, updates)` / `abulk_update_state(...)`
- Execution:
  - `invoke(input, config=None, *, context=None, interrupt_before=None, interrupt_after=None)`
  - `ainvoke(...)`
  - `stream(input, config=None, *, context=None, stream_mode=None, interrupt_before=None, interrupt_after=None, durability=None, debug=None, output_keys=None, subgraphs=False, **deprecated)` *(exact kwargs vary; see below)*
  - `astream(...)`
- Cache management:
  - `clear_cache(namespaces=None)` / `aclear_cache(...)`

#### Hidden Config / “Gotchas”
- Reserved channel name: `__pregel_tasks` is reserved; `Pregel` enforces it and injects a `Topic(Send, accumulate=False)` under that key.
- Checkpointer rules:
  - `checkpointer=True` is **not allowed** for a root graph (it means “inherit from parent graph”).
  - If a checkpointer is present, `RunnableConfig` must include configurable keys like `thread_id` (and optionally `checkpoint_ns`, `checkpoint_id`).
- Deprecated streaming flag:
  - `checkpoint_during` (bool) is deprecated in favor of `durability: Literal["sync","async","exit"]`.

---

### Remote Execution (`langgraph.pregel.remote`)

#### `RemoteGraph`
**Source File:** `libs/langgraph/langgraph/pregel/remote.py`
**Description:** A `PregelProtocol` implementation that proxies execution and state operations to a **LangGraph Server API** (e.g., LangSmith Deployments).

#### Constructor / Configuration
| Param | Type | Default | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `assistant_id` | `str` | **Required** | Remote graph identifier (assistant id / graph name). |
| `url` | `str \| None` | `None` | Base URL for the server API; required if you don’t pass clients. |
| `api_key` | `str \| None` | `None` | Auth token; if unset, client may read env (`LANGGRAPH_API_KEY`, `LANGSMITH_API_KEY`, `LANGCHAIN_API_KEY`). |
| `headers` | `dict[str,str] \| None` | `None` | Extra HTTP headers. |
| `client` | `LangGraphClient \| None` | `None` | Async client override. |
| `sync_client` | `SyncLangGraphClient \| None` | `None` | Sync client override. |
| `config` | `RunnableConfig \| None` | `None` | Base config merged into calls. |
| `name` | `str \| None` | `None` | Display name; defaults to `assistant_id`. |
| `distributed_tracing` | `bool` | `False` | Include LangSmith distributed tracing headers when making calls. |

#### Critical Methods
- `with_config(...)` / `copy(...)`: local-only config copy/merge.
- `get_graph(...)` / `aget_graph(...)`: fetch drawable graph structure from server.
- `invoke(...)` / `ainvoke(...)`, `stream(...)` / `astream(...)`: execute remotely.
- `get_state(...)`, `get_state_history(...)`, `update_state(...)`: remote state APIs.

#### Data/Config Constraints (often missed)
- Config is **sanitized** before sending: only primitives / UUIDs / nested dicts/lists of primitives are allowed.
- Some pregel-specific configurable keys are dropped when calling remote (checkpoint routing is owned by the server).

#### `RemoteException`
**Source File:** `libs/langgraph/langgraph/pregel/remote.py`
**Description:** Raised for remote execution failures.

---

### Protocols (`langgraph.pregel.protocol`)

#### `PregelProtocol[StateT, ContextT, InputT, OutputT]`
**Source File:** `libs/langgraph/langgraph/pregel/protocol.py`
**Description:** Abstract protocol for executable graphs (sync+async), used by `Pregel`, `CompiledStateGraph`, and `RemoteGraph`.

#### `StreamProtocol`
**Source File:** `libs/langgraph/langgraph/pregel/protocol.py`
**Description:** Wrapper that carries enabled stream modes and a callable to receive stream chunks.

---

### Debug Payload Contracts (`langgraph.pregel.debug`)
**Source File:** `libs/langgraph/langgraph/pregel/debug.py`

Exports:
- `TaskPayload`, `TaskResultPayload`, `CheckpointTask`, `CheckpointPayload` (TypedDicts)

Use-case:
- Interpret `stream_mode="debug"` events (tasks + checkpoints) programmatically.

---

### Deprecated: `langgraph.pregel.types`
**Source File:** `libs/langgraph/langgraph/pregel/types.py`
Re-exports moved types from `langgraph.types` and emits a deprecation warning on import.

## 4. Functional API (`langgraph.func`)

### `task` (decorator)
**Source File:** `libs/langgraph/langgraph/func/__init__.py`
**Description:** Wrap a function as a graph-aware task that returns a future-like handle; intended to be called *inside* `entrypoint` workflows or `StateGraph` nodes.

#### Decorator Parameters
| Param | Type | Default | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `name` | `str \| None` | `None` | Override the task name (mutates `__name__` or wraps bound method). |
| `retry_policy` | `RetryPolicy \| Sequence[RetryPolicy] \| None` | `None` | Per-task retry policies. |
| `cache_policy` | `CachePolicy[Callable[..., str\|bytes]] \| None` | `None` | Per-task caching policy and cache key function. |
| `**kwargs` | `DeprecatedKwargs` | — | Deprecated key supported: `retry` → `retry_policy`. |

#### Return Type
Returns a `_TaskFunction` wrapper. Calling it yields a `SyncAsyncFuture[T]`:
- `.result()` blocks (sync)
- `await`able (async)

#### Hidden Behaviors
- Async tasks require Python ≥ 3.11 (per docstring and contextvar propagation constraints).
- Cache clearing helpers exist on the wrapper:
  - `_TaskFunction.clear_cache(cache)`
  - `_TaskFunction.aclear_cache(cache)`

---

### `_TaskFunction` (callable wrapper)
**Source File:** `libs/langgraph/langgraph/func/__init__.py`
**Description:** The object produced by `@task`, responsible for invoking via Pregel’s internal call mechanism and optionally clearing cache namespaces.

#### Constructor / Configuration
| Param | Type | Default | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `func` | `Callable[..., Awaitable[T]] \| Callable[..., T]` | **Required** | Underlying task callable. |
| `retry_policy` | `Sequence[RetryPolicy]` | **Required** | Normalized retry policies sequence. |
| `cache_policy` | `CachePolicy[...] \| None` | `None` | Task-level cache policy. |
| `name` | `str \| None` | `None` | Optional override of function name. |

---

### `entrypoint` (decorator class)
**Source File:** `libs/langgraph/langgraph/func/__init__.py`
**Description:** Convert a plain Python function into a compiled workflow (a `Pregel`), with optional checkpointing for “previous” state and interrupts.

#### Constructor / Configuration
| Param | Type | Default | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `checkpointer` | `BaseCheckpointSaver \| None` | `None` | Enables persistence, interrupts, and `previous` injection. |
| `store` | `BaseStore \| None` | `None` | Store injected into runtime. |
| `cache` | `BaseCache \| None` | `None` | Cache for task results. |
| `context_schema` | `type[ContextT] \| None` | `None` | Schema for run-scoped context injection. |
| `cache_policy` | `CachePolicy \| None` | `None` | Workflow-level cache policy. |
| `retry_policy` | `RetryPolicy \| Sequence[RetryPolicy] \| None` | `None` | Workflow-level retry policies. |
| `**kwargs` | `DeprecatedKwargs` | — | Deprecated keys supported: `config_schema` → `context_schema`; `retry` → `retry_policy`. |

#### Result of Decorating
`@entrypoint(...)` returns a **`Pregel` instance**, not a function. The resulting object supports:
- `.invoke(...)`, `.ainvoke(...)`
- `.stream(...)`, `.astream(...)`
- `.get_state(...)`, `.update_state(...)` (when checkpointer present)

#### `entrypoint.final[value, save]`
**Source File:** `libs/langgraph/langgraph/func/__init__.py`
**Description:** Return wrapper that decouples “returned value” from “saved previous value”.

Constructor fields:
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `value` | `R` | **Required** | Value returned to the caller. |
| `save` | `S` | **Required** | Value persisted to checkpoints as the next `previous`. |

## 5. Runtime & In-Graph Introspection (`langgraph.runtime`, `langgraph.config`)

### `Runtime[ContextT]`
**Source File:** `libs/langgraph/langgraph/runtime.py`
**Description:** Bundles run-scoped context plus store/stream utilities; injected into nodes and middleware when requested as a parameter.

#### Constructor / Configuration
`Runtime` is a dataclass; typical users do not instantiate it manually (it’s created per run).

Fields (constructor-equivalent):
| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `context` | `ContextT` | `None` | Immutable run context/dependencies. |
| `store` | `BaseStore \| None` | `None` | Store for persistence/memory. |
| `stream_writer` | `StreamWriter` | *(no-op)* | Writer for `stream_mode="custom"`. |
| `previous` | `Any` | `None` | Prior entrypoint return value for thread (functional API + checkpointer). |

Methods:
- `merge(other: Runtime) -> Runtime`: Merge two runtimes (other overrides when set).
- `override(**overrides) -> Runtime`: Dataclass replace helper.

### `get_runtime(context_schema=None) -> Runtime`
**Source File:** `libs/langgraph/langgraph/runtime.py`
**Description:** Fetch the current run’s `Runtime` from the active `RunnableConfig` context.

### `get_config() -> RunnableConfig`
**Source File:** `libs/langgraph/langgraph/config.py`
**Description:** Access the active run config from inside nodes/tasks.

Gotcha:
- On Python < 3.11, using `get_config()` in async contexts may raise because contextvar propagation differs.

### `get_store() -> BaseStore`
**Source File:** `libs/langgraph/langgraph/config.py`
**Description:** Convenience accessor: `get_config()["configurable"][__pregel_runtime].store`.

### `get_stream_writer() -> StreamWriter`
**Source File:** `libs/langgraph/langgraph/config.py`
**Description:** Convenience accessor for streaming custom events from within nodes/tasks.

## 6. Channels (`langgraph.channels`)

Channels define:
- **ValueType**: what you can read from the channel
- **UpdateType**: what nodes can write to the channel
- **checkpoint() / from_checkpoint()**: persistence behavior (or `MISSING`)
- **update(values)**: aggregation/validation for a super-step

### `BaseChannel[Value, Update, Checkpoint]`
**Source File:** `libs/langgraph/langgraph/channels/base.py`
**Description:** Abstract base for channels. Pregel calls `.update()` at the end of each step and `.consume()` when a subscribed task ran.

#### Constructor / Configuration
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `typ` | `Any` | **Required** | Type hint for the value/update. |
| `key` | `str` | `""` | Channel name (set by graph compilation/wiring). |

Core methods:
- `get() -> Value` (raises `EmptyChannelError` if unset)
- `update(values: Sequence[Update]) -> bool` (may raise `InvalidUpdateError`)
- `checkpoint() -> Checkpoint|Any` (returns `MISSING` when unsupported/empty by default)
- `from_checkpoint(checkpoint) -> Self`
- `consume() -> bool` (default no-op)
- `finish() -> bool` (default no-op)

---

### `LastValue`
**Source File:** `libs/langgraph/langgraph/channels/last_value.py`
**Description:** Stores the last value received; **can receive at most one value per step**.

Constructor:
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `typ` | `Any` | **Required** | Value type. |
| `key` | `str` | `""` | Channel name. |

---

### `LastValueAfterFinish`
**Source File:** `libs/langgraph/langgraph/channels/last_value.py`
**Description:** Like `LastValue`, but the value becomes readable only after `.finish()` is called; then it is consumed/cleared on `.consume()`.

---

### `AnyValue`
**Source File:** `libs/langgraph/langgraph/channels/any_value.py`
**Description:** Stores last value; if multiple values are received, it assumes they are equivalent (no “single write” guard).

---

### `EphemeralValue`
**Source File:** `libs/langgraph/langgraph/channels/ephemeral_value.py`
**Description:** Stores the most recent step’s value; clears when no updates occur.

Constructor:
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `typ` | `Any` | **Required** | Value type. |
| `guard` | `bool` | `True` | If `True`, enforces ≤1 update per step. |

---

### `UntrackedValue`
**Source File:** `libs/langgraph/langgraph/channels/untracked_value.py`
**Description:** Stores last value but **never checkpoints** (`checkpoint()` returns `MISSING`).

Constructor:
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `typ` | `type[Value]` | **Required** | Value type. |
| `guard` | `bool` | `True` | If `True`, enforces ≤1 update per step. |

---

### `BinaryOperatorAggregate`
**Source File:** `libs/langgraph/langgraph/channels/binop.py`
**Description:** Aggregates values using a binary reducer (`operator(value, update)`), and supports **overwrite** semantics.

Constructor:
| Param | Type | Default | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `typ` | `type[Value]` | **Required** | Type of stored value. Attempted to instantiate to get an initial empty value; if not instantiable, starts as `MISSING`. |
| `operator` | `Callable[[Value, Value], Value]` | **Required** | Reducer function. |

Overwrite behavior:
- If a node writes `Overwrite(value=...)` or a dict `{"__overwrite__": ...}` to this channel, it bypasses the reducer.
- Receiving multiple overwrites in one super-step raises `InvalidUpdateError`.

---

### `Topic`
**Source File:** `libs/langgraph/langgraph/channels/topic.py`
**Description:** Pub/sub channel that stores a list of values. With `accumulate=False`, values reset each step.

Constructor:
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `typ` | `type[Value]` | **Required** | Type of each published value. |
| `accumulate` | `bool` | `False` | If `False`, clears values each step. |

---

### `NamedBarrierValue` / `NamedBarrierValueAfterFinish`
**Source File:** `libs/langgraph/langgraph/channels/named_barrier_value.py`
**Description:** Barrier channels that only become “available” when a set of named values has been seen; AfterFinish variant gates availability on `.finish()`.

Constructor:
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `typ` | `type[Value]` | **Required** | Update type (names). |
| `names` | `set[Value]` | **Required** | Names that must be received. |

## 7. Control Plane & Data Contracts (`langgraph.types`)

### Literals / Enums
**Source File:** `libs/langgraph/langgraph/types.py`

- `Durability = Literal["sync", "async", "exit"]`
- `StreamMode = Literal["values","updates","checkpoints","tasks","debug","messages","custom"]`
- `All = Literal["*"]` (“interrupt on all nodes” sentinel)
- `Checkpointer = None | bool | BaseCheckpointSaver`

---

### `RetryPolicy`
**Source File:** `libs/langgraph/langgraph/types.py`
**Description:** Per-node/task retry configuration (NamedTuple).

Fields:
| Field | Type | Default | Meaning |
| :--- | :--- | :--- | :--- |
| `initial_interval` | `float` | `0.5` | Delay before first retry (seconds). |
| `backoff_factor` | `float` | `2.0` | Multiplier for exponential backoff. |
| `max_interval` | `float` | `128.0` | Maximum delay between retries. |
| `max_attempts` | `int` | `3` | Attempts including the first try. |
| `jitter` | `bool` | `True` | Add random jitter. |
| `retry_on` | `type[Exception] \| Sequence[type[Exception]] \| Callable[[Exception], bool]` | `default_retry_on` | Which errors trigger a retry. |

---

### `CachePolicy[key_func]`
**Source File:** `libs/langgraph/langgraph/types.py`
**Description:** Cache configuration (dataclass).

Fields:
| Field | Type | Default | Meaning |
| :--- | :--- | :--- | :--- |
| `key_func` | `Callable[..., str|bytes]` | `default_cache_key` | How to compute a cache key from node/task input. |
| `ttl` | `int \| None` | `None` | TTL seconds (None = never expire). |

---

### `Interrupt`
**Source File:** `libs/langgraph/langgraph/types.py`
**Description:** Interrupt payload emitted when a node calls `interrupt(...)` and no resume value is available.

#### Constructor / Configuration
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `value` | `Any` | **Required** | Value surfaced to client. |
| `id` | `str` | `"placeholder-id"` | Interrupt id used for resuming. |
| `**deprecated_kwargs` | `DeprecatedKwargs` | — | If `ns` is provided and `id` is default, id is derived by hashing namespace. |

Other API:
- `Interrupt.from_ns(value, ns: str) -> Interrupt` (stable id derived from ns)
- `interrupt_id` property (**deprecated**, use `.id`)

---

### `Send`
**Source File:** `libs/langgraph/langgraph/types.py`
**Description:** Envelope used in conditional edges to schedule a node with custom input at the next step (“push”).

#### Constructor / Configuration
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `node` | `str` | **Required** | Target node name. |
| `arg` | `Any` | **Required** | Input/state to send to the node. |

---

### `Command`
**Source File:** `libs/langgraph/langgraph/types.py`
**Description:** Multi-purpose control primitive to (a) update state, (b) resume interrupts, (c) navigate/goto nodes (including `Send`).

#### Constructor / Configuration
| Param | Type | Default | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `graph` | `str \| None` | `None` | Target graph: `None` = current; `Command.PARENT` = closest parent graph. |
| `update` | `Any \| None` | `None` | State update. Supported shapes: `dict`, sequence of `(str, Any)` tuples, dataclass/Pydantic with annotated keys, or root value. |
| `resume` | `dict[str, Any] \| Any \| None` | `None` | Resume value(s) for interrupts. |
| `goto` | `Send \| Hashable \| Sequence[Send \| Hashable]` | `()` | Navigation: node name(s) or `Send` packets. |

Constants / helpers:
- `Command.PARENT = "__parent__"`
- Internal helper `_update_as_tuples()` is used by `StateGraph` compilation to extract channel updates.

---

### `interrupt(value) -> Any`
**Source File:** `libs/langgraph/langgraph/types.py`
**Description:** Human-in-the-loop primitive. On first call in a node/task it raises an internal `GraphInterrupt` carrying an `Interrupt`. On re-execution with resume data, returns the resumed value.

Hard requirement:
- Requires a checkpointer, because resume values are tracked via persisted scratchpad state.

Resume matching:
- Multiple interrupts in a node are ordered; resume values are consumed in order per-task.

---

### `Overwrite`
**Source File:** `libs/langgraph/langgraph/types.py`
**Description:** Wrap a value to bypass reducers (notably `BinaryOperatorAggregate`).

#### Constructor / Configuration
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `value` | `Any` | **Required** | Value written directly. |

Also supported (equivalent) wire representation:
- `{"__overwrite__": <value>}` (dict form recognized by `BinaryOperatorAggregate`)

---

### Execution/State Records

#### `StateUpdate`
**Source File:** `libs/langgraph/langgraph/types.py`
**Description:** NamedTuple used by `.update_state()` and `.bulk_update_state()`.

Fields:
- `values: dict[str, Any] | Any | None`
- `as_node: str | None = None`
- `task_id: str | None = None`

#### `PregelTask`
**Source File:** `libs/langgraph/langgraph/types.py`
**Description:** Task status record returned in `StateSnapshot.tasks`.

Fields:
- `id`, `name`, `path`
- `error: Exception | None`
- `interrupts: tuple[Interrupt, ...]`
- `state: None | RunnableConfig | StateSnapshot`
- `result: Any | None`

#### `PregelExecutableTask`
**Source File:** `libs/langgraph/langgraph/types.py`
**Description:** Internal execution object representing a runnable task in a step; appears in debug plumbing.

#### `StateSnapshot`
**Source File:** `libs/langgraph/langgraph/types.py`
**Description:** Snapshot returned by `.get_state()` and state-history APIs.

Fields:
- `values`: channel values
- `next`: tuple of node names scheduled
- `config`: runnable config for the snapshot
- `metadata`: checkpoint metadata (if any)
- `created_at`, `parent_config`
- `tasks`, `interrupts`

## 8. Errors & Constants (`langgraph.errors`, `langgraph.constants`)

### `ErrorCode` (Enum)
**Source File:** `libs/langgraph/langgraph/errors.py`
Values include:
- `GRAPH_RECURSION_LIMIT`
- `INVALID_CONCURRENT_GRAPH_UPDATE`
- `INVALID_GRAPH_NODE_RETURN_VALUE`
- `MULTIPLE_SUBGRAPHS`
- `INVALID_CHAT_HISTORY`

### Common Exceptions
- `GraphRecursionError(RecursionError)`: recursion limit exceeded.
- `InvalidUpdateError(Exception)`: invalid node return / invalid concurrent updates.
- `EmptyChannelError(Exception)`: reading a never-written channel.
- `GraphInterrupt(GraphBubbleUp)`: internal interrupt carrier.
- `ParentCommand(GraphBubbleUp)`: bubble a `Command` to parent.
- `EmptyInputError`, `TaskNotFound`.

### Constants
**Source File:** `libs/langgraph/langgraph/constants.py`
- `START = "__start__"`
- `END = "__end__"`
- `TAG_NOSTREAM = "nostream"`
- `TAG_HIDDEN = "langsmith:hidden"`

Deprecation traps:
- `langgraph.constants.Send` / `.Interrupt` are deprecated proxies to `langgraph.types`.
- Many internal constants can still be imported from `langgraph.constants` but emit warnings; they are defined in `langgraph._internal._constants`.

## 9. Managed Values (`langgraph.managed`)

### `IsLastStep`, `RemainingSteps`
**Source Files:** `libs/langgraph/langgraph/managed/is_last_step.py`, `libs/langgraph/langgraph/managed/__init__.py`
**Description:** `Annotated[...]` types backed by `ManagedValue` providers. These allow state keys whose values are computed from the runtime scratchpad (e.g., remaining recursion steps).

## 10. Persistence: Checkpointing (`langgraph.checkpoint.*`)

### Base Contracts (`langgraph.checkpoint.base`)
**Source File:** `libs/checkpoint/langgraph/checkpoint/base/__init__.py`

#### `BaseCheckpointSaver[V]`
**Description:** Interface for persisting and retrieving checkpoints (sync+async).

Constructor:
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `serde` | `SerializerProtocol \| None` | `None` | Serializer used for checkpoint payloads; default is `JsonPlusSerializer()`. |

Key methods:
- `get(config) -> Checkpoint | None`
- `get_tuple(config) -> CheckpointTuple | None` *(implement in subclasses)*
- `list(config|None, *, filter=None, before=None, limit=None) -> Iterator[CheckpointTuple]` *(implement)*
- `put(config, checkpoint, metadata, new_versions) -> RunnableConfig` *(implement)*
- `put_writes(config, writes, task_id, task_path="") -> None` *(implement)*
- `delete_thread(thread_id) -> None` *(implement)*
- Async variants: `aget`, `aget_tuple`, `alist`, `aput`, `aput_writes`, `adelete_thread`
- `get_next_version(current, channel=None) -> V`: default integer increment (override for custom versioning; `str` requires implementation).

#### Data Types
- `CheckpointMetadata` (TypedDict, total=False):
  - `source: Literal["input","loop","update","fork"]`
  - `step: int`
  - `parents: dict[str,str]` (checkpoint lineage by namespace)
- `Checkpoint` (TypedDict):
  - `v: int`, `id: str`, `ts: str`
  - `channel_values: dict[str, Any]`
  - `channel_versions: dict[str, str|int|float]`
  - `versions_seen: dict[str, dict[str, str|int|float]]`
  - `updated_channels: list[str] | None`
- `CheckpointTuple(NamedTuple)`:
  - `config`, `checkpoint`, `metadata`, plus `parent_config`, `pending_writes`
- `PendingWrite = tuple[str, str, Any]`
- `WRITES_IDX_MAP`: maps special write keys (`__error__`, `__interrupt__`, etc.) to negative indices to avoid collisions.

Deprecated utilities still present:
- `empty_checkpoint()`
- `create_checkpoint(...)`

---

### In-Memory Checkpointer (`langgraph.checkpoint.memory`)

#### `InMemorySaver`
**Source File:** `libs/checkpoint/langgraph/checkpoint/memory/__init__.py`
**Description:** In-memory checkpoint saver; useful for tests/demos; not durable across process restarts.

Constructor:
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `serde` | `SerializerProtocol \| None` | `None` | Serializer. |
| `factory` | `type[defaultdict]` | `defaultdict` | Inject alternate mapping factory (advanced). |

Notable behaviors:
- Implements both sync and async context manager interfaces (`with` and `async with`).
- Stores channel blobs separately to reduce duplication (`self.blobs`).

---

### SQLite Checkpointer (`langgraph.checkpoint.sqlite`)

#### `SqliteSaver`
**Source File:** `libs/checkpoint-sqlite/langgraph/checkpoint/sqlite/__init__.py`
**Description:** Synchronous SQLite-backed saver (lightweight; not recommended for high concurrency).

Constructor:
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `conn` | `sqlite3.Connection` | **Required** | Connection; recommended `check_same_thread=False` (class uses a lock). |
| `serde` | `SerializerProtocol \| None` | `None` | Serializer (default uses JsonPlus). |

Convenience:
- `SqliteSaver.from_conn_string(conn_string) -> contextmanager[SqliteSaver]`

Async note:
- Sync `SqliteSaver` explicitly does **not** support async methods; the error message points to `AsyncSqliteSaver`.

#### `AsyncSqliteSaver`
**Source File:** `libs/checkpoint-sqlite/langgraph/checkpoint/sqlite/aio.py`
**Description:** Async SQLite saver using `aiosqlite`.

Constructor:
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `conn` | `aiosqlite.Connection` | **Required** | Async connection. |
| `serde` | `SerializerProtocol \| None` | `None` | Serializer. |

Convenience:
- `AsyncSqliteSaver.from_conn_string(conn_string) -> asynccontextmanager[AsyncSqliteSaver]`

Sync-call trap:
- Calling sync methods on `AsyncSqliteSaver` from the main event loop raises; allowed only from a different thread (it uses `run_coroutine_threadsafe`).

---

### Postgres Checkpointer (`langgraph.checkpoint.postgres`)

#### `PostgresSaver`
**Source File:** `libs/checkpoint-postgres/langgraph/checkpoint/postgres/__init__.py`
**Description:** Synchronous Postgres saver using psycopg3; supports optional pipeline mode.

Constructor:
| Param | Type | Default | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `conn` | `psycopg.Connection \| psycopg_pool.ConnectionPool \| ...` | **Required** | Connection or pool (internal `Conn` alias). |
| `pipe` | `Pipeline \| None` | `None` | Only valid with a single Connection (not with pool). |
| `serde` | `SerializerProtocol \| None` | `None` | Serializer. |

Convenience:
- `PostgresSaver.from_conn_string(conn_string, *, pipeline=False) -> contextmanager[PostgresSaver]`

Operational requirement:
- `setup()` **must be called** by the user the first time to run migrations.

#### `AsyncPostgresSaver`
**Source File:** `libs/checkpoint-postgres/langgraph/checkpoint/postgres/aio.py`
**Description:** Async Postgres saver (psycopg3 async).

Constructor mirrors `PostgresSaver` with `AsyncConnection` / `AsyncConnectionPool` and `AsyncPipeline`.
Includes `from_conn_string(..., serde=None)` async context manager and `setup()` async migration runner.

#### Shallow variants
**Source File:** `libs/checkpoint-postgres/langgraph/checkpoint/postgres/shallow.py`
Exports:
- `ShallowPostgresSaver`
- `AsyncShallowPostgresSaver`

Use-case:
- Store fewer blob details / reduce storage footprint (implementation-specific).

## 11. Persistence: Store (`langgraph.store.*`)

### Base Contracts (`langgraph.store.base`)
**Source File:** `libs/checkpoint/langgraph/store/base/__init__.py`
**Description:** Persistent key-value store with hierarchical namespaces, optional vector search, and optional TTL.

#### Core Types / Ops
- `Item`: stored value + timestamps + namespace/key
- `SearchItem(Item)`: adds `score: float|None`
- Ops (for `BaseStore.batch/abatch`):
  - `GetOp(namespace, key, refresh_ttl=True)`
  - `SearchOp(namespace_prefix, filter=None, limit=10, offset=0, query=None, refresh_ttl=True)`
  - `PutOp(namespace, key, value, index=None|False|list[str], ttl=None)`
  - `ListNamespacesOp(match_conditions=None, max_depth=None, limit=100, offset=0)`
- `Op = GetOp | SearchOp | PutOp | ListNamespacesOp`
- `Result = Item | list[Item] | list[SearchItem] | list[tuple[str, ...]] | None`

Namespace constraints:
- Namespace is a `tuple[str, ...]` that:
  - cannot be empty
  - cannot contain `.` in labels
  - cannot have empty labels
  - cannot start with `"langgraph"` as root label

Filters (SearchOp.filter):
- Supports direct equality and operators:
  - `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`

TTL:
- `TTLConfig` supports defaults like `refresh_on_read`, `default_ttl`, `sweep_interval_minutes`
- If TTL is used, adapter must set `supports_ttl = True` (otherwise `put(..., ttl=...)` raises).

Indexing / vector search:
- `IndexConfig`:
  - `dims: int`
  - `embed: Embeddings | EmbeddingsFunc | AEmbeddingsFunc | str`
  - `fields: list[str] | None` (JSON-path-like field selection; defaults to `["$"]`)

#### `BaseStore`
**Description:** Abstract adapter surface; implement `batch()` and `abatch()`.

Key methods (provided as wrappers around batch ops):
- `get(...)`, `search(...)`, `put(...)`, `delete(...)`, `list_namespaces(...)`
- Async variants: `aget`, `asearch`, `aput`, `adelete`, `alist_namespaces`

---

### In-Memory Store (`langgraph.store.memory`)

#### `InMemoryStore`
**Source File:** `libs/checkpoint/langgraph/store/memory/__init__.py`
**Description:** Dict-backed store with optional in-process vector search. Not durable across restarts.

Constructor:
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `index` | `IndexConfig \| None` | `None` | Enables embeddings + similarity search. |

---

### SQLite Store (`langgraph.store.sqlite`)

#### `SqliteStore`
**Source File:** `libs/checkpoint-sqlite/langgraph/store/sqlite/base.py`
**Description:** SQLite-backed store with optional vector search and TTL support.

Constructor:
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `conn` | `sqlite3.Connection` | **Required** | SQLite connection. |
| `deserializer` | `Callable[[bytes|str|orjson.Fragment], dict] \| None` | `None` | Custom JSON deserializer for stored values (advanced). |
| `index` | `SqliteIndexConfig \| None` | `None` | Enable vector search (requires sqlite-vec). |
| `ttl` | `TTLConfig \| None` | `None` | TTL config; supports sweeper thread. |

Operational requirement:
- `setup()` must be called before first use (migrations).

#### `AsyncSqliteStore`
**Source File:** `libs/checkpoint-sqlite/langgraph/store/sqlite/aio.py`
**Description:** Async variant.

---

### Postgres Store (`langgraph.store.postgres`)

#### `PoolConfig`
**Source File:** `libs/checkpoint-postgres/langgraph/store/postgres/base.py`
**Description:** TypedDict for pool sizing/kwargs.

#### `PostgresStore`
**Source File:** `libs/checkpoint-postgres/langgraph/store/postgres/base.py`
**Description:** Postgres-backed store with pgvector-based semantic search and TTL support.

Constructor:
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `conn` | `Connection \| ConnectionPool \| ...` | **Required** | psycopg3 connection or pool. |
| `pipe` | `Pipeline \| None` | `None` | Pipeline mode (single connection only). |
| `deserializer` | `Callable[[bytes|orjson.Fragment], dict] \| None` | `None` | Custom JSON deserializer. |
| `index` | `PostgresIndexConfig \| None` | `None` | Enable semantic search (pgvector required). |
| `ttl` | `TTLConfig \| None` | `None` | TTL config; requires calling `start_ttl_sweeper()` to actually sweep in background. |

Convenience:
- `PostgresStore.from_conn_string(conn_string, *, pipeline=False, pool_config=None, index=None, ttl=None)`

#### `AsyncPostgresStore`
**Source File:** `libs/checkpoint-postgres/langgraph/store/postgres/aio.py`
**Description:** Async Postgres store with optional async pool and async TTL sweeper task.

## 12. Persistence: Cache (`langgraph.cache.*`)

### `BaseCache[ValueT]`
**Source File:** `libs/checkpoint/langgraph/cache/base/__init__.py`
**Description:** Cache interface for task/node results; uses `SerializerProtocol` to store typed values.

Constructor:
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `serde` | `SerializerProtocol \| None` | `None` | Default uses `JsonPlusSerializer(pickle_fallback=False)`. |

Key methods:
- `get(keys: Sequence[FullKey]) -> dict[FullKey, ValueT]`
- `aget(...)`
- `set(pairs: Mapping[FullKey, tuple[ValueT, int|None]])`
- `aset(...)`
- `clear(namespaces=None)` / `aclear(...)`

Types:
- `Namespace = tuple[str, ...]`
- `FullKey = tuple[Namespace, str]`

---

### `InMemoryCache`
**Source File:** `libs/checkpoint/langgraph/cache/memory/__init__.py`
**Description:** Thread-safe in-memory cache with TTL.

Constructor:
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `serde` | `SerializerProtocol \| None` | `None` | Serializer. |

---

### `RedisCache`
**Source File:** `libs/checkpoint/langgraph/cache/redis/__init__.py`
**Description:** Redis-backed cache with TTL support.

Constructor:
| Param | Type | Default | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `redis` | `Any` | **Required** | Redis client (expects `mget`, `pipeline`, `keys`, `delete`, etc.). |
| `serde` | `SerializerProtocol \| None` | `None` | Serializer. |
| `prefix` | `str` | `"langgraph:cache:"` | Key prefix. |

Reliability note (important):
- Operations catch broad exceptions and may **silently degrade** to empty reads / no-op writes if Redis is unavailable.

---

### `SqliteCache`
**Source File:** `libs/checkpoint-sqlite/langgraph/cache/sqlite/__init__.py`
**Description:** File-backed SQLite cache with TTL.

Constructor:
| Param | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `path` | `str` | **Required** | SQLite DB file path. |
| `serde` | `SerializerProtocol \| None` | `None` | Serializer. |

## 13. Prebuilt Tooling (`langgraph.prebuilt`)

### `ToolNode`
**Source File:** `libs/prebuilt/langgraph/prebuilt/tool_node.py`
**Description:** A runnable node that executes model-emitted tool calls in parallel and returns tool outputs or `Command` objects.

#### Constructor / Configuration
| Param | Type | Default | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `tools` | `Sequence[BaseTool \| Callable]` | **Required** | Tools available for execution; callables are wrapped via `langchain_core.tools.tool`. |
| `name` | `str` | `"tools"` | Node name. |
| `tags` | `list[str] \| None` | `None` | Runnable tags. |
| `handle_tool_errors` | `bool \| str \| Callable[..., str] \| type[Exception] \| tuple[type[Exception], ...]` | `_default_handle_tool_errors` | How to convert exceptions into tool error messages. |
| `messages_key` | `str` | `"messages"` | Where to find messages in state input. |
| `wrap_tool_call` | `ToolCallWrapper \| None` | `None` | Sync interceptor wrapper around tool execution (can return `ToolMessage` or `Command`). |
| `awrap_tool_call` | `AsyncToolCallWrapper \| None` | `None` | Async interceptor; if unset, may fall back to `wrap_tool_call`. |

#### Public Properties / Methods
- `tools_by_name -> dict[str, BaseTool]`: registered tools.
- Invocation is via Runnable interface: `invoke(...)`, `ainvoke(...)`, etc (inherited).

#### Error Handling Semantics (high value detail)
`handle_tool_errors` supports:
- `True` / exception type / tuple of types: generate default error template with `repr(e)`
- `str`: use as error content verbatim
- `callable(e) -> str`: compute error message
- Default `_default_handle_tool_errors` returns message for `ToolInvocationError`, otherwise re-raises

---

### `tools_condition(state_or_messages) -> Literal["tools","__end__"]`
**Source File:** `libs/prebuilt/langgraph/prebuilt/tool_node.py`
**Description:** Helper for `StateGraph.add_conditional_edges(...)` to route to `"tools"` when the last AI message contains tool calls.

---

### `ToolCallRequest`
**Source File:** `libs/prebuilt/langgraph/prebuilt/tool_node.py`
**Description:** Dataclass passed into tool-call interceptors (`wrap_tool_call`/`awrap_tool_call`) to enable safe request modification.

Constructor fields:
| Field | Type | Default | Meaning |
| :--- | :--- | :--- | :--- |
| `tool_call` | `ToolCall` | **Required** | Name/args/id from model output. |
| `tool` | `BaseTool \| None` | **Required** | Resolved tool (None if unregistered). |
| `state` | `Any` | **Required** | Input state/messages/base model. |
| `runtime` | `ToolRuntime` | **Required** | Tool runtime context. |

Helper:
- `override(**overrides) -> ToolCallRequest` (immutable-style replacement; direct attribute assignment warns).

---

### `ToolRuntime`
**Source File:** `libs/prebuilt/langgraph/prebuilt/tool_node.py`
**Description:** Dataclass runtime injected into tool functions when they declare a `runtime: ToolRuntime` parameter.

Fields:
| Field | Type | Default | Meaning |
| :--- | :--- | :--- | :--- |
| `state` | `StateT` | **Required** | Current graph state. |
| `context` | `ContextT` | **Required** | Run context (shared with `Runtime`). |
| `config` | `RunnableConfig` | **Required** | Config for this tool call. |
| `stream_writer` | `StreamWriter` | **Required** | For custom streaming. |
| `tool_call_id` | `str \| None` | **Required** | Tool call id from message. |
| `store` | `BaseStore \| None` | **Required** | Persistent store (shared). |

---

### `InjectedState`, `InjectedStore`
**Source File:** `libs/prebuilt/langgraph/prebuilt/tool_node.py`
**Description:** `InjectedToolArg` annotations used to hide system-supplied args from model schemas while still injecting state/store into tool call execution.

`InjectedState(field: str|None = None)`:
- If `field` is None, inject entire state; else inject `state[field]`.

`InjectedStore()`:
- Injects the `BaseStore` instance (requires compatible langchain-core).

---

### Deprecated: `create_react_agent`, `ValidationNode`
**Source File:** `libs/prebuilt/langgraph/prebuilt/__init__.py`
Both are retained for back-compat; implementations live in `chat_agent_executor.py` and `tool_validator.py` and emit deprecation warnings in favor of LangChain equivalents.

## 14. Serialization & Encryption (`langgraph.checkpoint.serde.*`)

### `JsonPlusSerializer`
**Source File:** `libs/checkpoint/langgraph/checkpoint/serde/jsonplus.py`
**Description:** Default serializer for checkpoints/caches; uses `ormsgpack` and includes optional fallbacks.

Constructor:
| Param | Type | Default | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `pickle_fallback` | `bool` | `False` | If `True`, falls back to pickle when msgpack encoding fails (**dangerous if untrusted**). |
| `allowed_json_modules` | `Sequence[tuple[str,...]] \| Literal[True] \| None` | `None` | Allowlist for JSON “constructor” reviving. `True` disables allowlist checks (dangerous). |
| `__unpack_ext_hook__` | `Callable[[int, bytes], Any] \| None` | `None` | Override msgpack extension hook. |

Security note (real-world):
- If attackers can write to your checkpoint DB and you deserialize with permissive settings, you may be exposed to code execution via object revival or pickle fallback.

### `EncryptedSerializer`
**Source File:** `libs/checkpoint/langgraph/checkpoint/serde/encrypted.py`
**Description:** Wraps another serializer and encrypts its bytes using a `CipherProtocol`.

Factory:
- `EncryptedSerializer.from_pycryptodome_aes(...)`:
  - If `key` not provided, reads `LANGGRAPH_AES_KEY` from environment.
  - Key must be 16/24/32 bytes.
  - Requires `pycryptodome`.

## 15. Legacy Compatibility Modules

### `langgraph.utils.*` (**legacy; to be removed in v1**)
**Source Files:** `libs/langgraph/langgraph/utils/config.py`, `libs/langgraph/langgraph/utils/runnable.py`
**Description:** Back-compat reexports of internal helpers (`ensure_config`, `patch_configurable`, `RunnableCallable`, etc.).
