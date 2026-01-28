# LangGraph (Python) - The Usage Cookbook (Test-Backed)

This cookbook is **mined from this repository’s test suite** (and the test-only example app) rather than relying on potentially stale documentation. Every recipe includes a **source citation** to the exact test file where the pattern appears.

> Note: `examples/` in this repo is explicitly marked as archival and “no longer updated” (`examples/README.md`). Treat tests under `libs/langgraph/tests/` as the source of truth.

## 1. The Production Setup

### 1.1 The “Gold Standard” Initialization Pattern (Fixtures)

The test suite consistently initializes LangGraph in a “clean, production-like” way by composing:
- a compiled graph (`StateGraph(...).compile(...)`),
- an optional **checkpointer** (enables persistence + interrupts),
- an optional **store** (long-term memory),
- an optional **cache** (task/node result caching),
- a **config** that always includes a `thread_id` when persistence is enabled.

**Source Patterns:**
- `libs/langgraph/tests/conftest.py` (fixtures: `sync_checkpointer`, `async_checkpointer`, `sync_store`, `async_store`, `cache`, `durability`, `deterministic_uuids`)
- `libs/langgraph/tests/conftest_checkpointer.py` (factory helpers for Postgres/SQLite/memory checkpointers)
- `libs/langgraph/tests/conftest_store.py` (factory helpers for Postgres/memory stores)

#### Copy-paste ready “real” setup (dev/prod)
```python
from __future__ import annotations

from typing_extensions import TypedDict

from langgraph.graph import END
from langgraph.graph.state import StateGraph

# Optional persistence / memory components:
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.memory import InMemoryStore
from langgraph.cache.memory import InMemoryCache


class State(TypedDict):
    foo: int


def node(state: State) -> dict:
    return {"foo": state["foo"] + 1}


# 1) Choose durability primitives (tests commonly run SQLite in-memory for isolation)
with SqliteSaver.from_conn_string(":memory:") as checkpointer:
    store = InMemoryStore()
    cache = InMemoryCache()

    # 2) Build + compile the graph with the shared runtime dependencies
    graph = (
        StateGraph(State)
        .add_node(node)              # name inferred from function: "node"
        .set_entry_point("node")     # wires START -> node
        .add_edge("node", END)       # wires node -> END
        .compile(checkpointer=checkpointer, store=store, cache=cache)
    )

    # 3) When a checkpointer is enabled, ALWAYS pass a thread_id
    config = {"configurable": {"thread_id": "thread-1"}}

    print(graph.invoke({"foo": 1}, config))  # {'foo': 2}
```

#### Hidden environment knobs surfaced by tests

- `NO_DOCKER=true` disables tests that require Docker (e.g., Postgres/Redis/server integration).
  - **Source:** `libs/langgraph/tests/conftest.py`, `libs/langgraph/tests/test_remote_graph.py`
- `LANGGRAPH_AES_KEY` is read by `EncryptedSerializer.from_pycryptodome_aes()` if you don’t pass a key explicitly.
  - **Source:** serializer implementation used by tests: `libs/checkpoint/langgraph/checkpoint/serde/encrypted.py`

#### Running the same infra the tests expect (optional, for integration-style dev)

The tests assume:
- Postgres on `localhost:5442` (user/password/db: `postgres`)
- Redis on `localhost:6379`

**Source:** `libs/langgraph/tests/compose-postgres.yml`, `libs/langgraph/tests/compose-redis.yml`

```bash
docker compose -f libs/langgraph/tests/compose-postgres.yml up -d
docker compose -f libs/langgraph/tests/compose-redis.yml up -d
```

## 2. Usage Recipes (Basic → Advanced)

### 2.1 The Happy Path (Synchronous & Simple)

#### Recipe: Minimal `StateGraph` → `compile()` → `invoke()`
**Source:** `libs/langgraph/tests/test_utils.py` (fixture `rt_graph`)

```python
from typing_extensions import TypedDict

from langgraph.graph import END
from langgraph.graph.state import StateGraph


class State(TypedDict):
    foo: int


def node(state: State) -> dict:
    return {"foo": state["foo"] + 1}


graph = (
    StateGraph(State)
    .add_node(node)          # inferred name: "node"
    .set_entry_point("node")
    .add_edge("node", END)
    .compile()
)

result = graph.invoke({"foo": 1})
assert result == {"foo": 2}
```

#### Recipe: Message state with `add_messages` reducer
**Source:** `libs/langgraph/tests/test_messages_state.py` (`test_messages_state`)

```python
from typing import Annotated

from langchain_core.messages import HumanMessage, AnyMessage
from typing_extensions import TypedDict

from langgraph.constants import START, END
from langgraph.graph import add_messages
from langgraph.graph.state import StateGraph


class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def foo(state: MessagesState) -> dict:
    return {"messages": [HumanMessage("foo")]}


app = (
    StateGraph(MessagesState)
    .add_node(foo)              # inferred name: "foo"
    .add_edge(START, "foo")
    .add_edge("foo", END)
    .compile()
)

out = app.invoke({"messages": [("user", "meow")]})
# out["messages"] contains the original user message + the appended HumanMessage("foo")
```

### 2.2 The High-Performance Path (Async/Batching/Concurrency)

#### Recipe: Async execution with `ainvoke()`
**Source:** `libs/langgraph/tests/test_pregel_async.py` (ToolNode loop test block around `workflow.compile(...); await app.ainvoke(...)`)

```python
from typing import Annotated

from langchain_core.messages import AnyMessage
from typing_extensions import TypedDict

from langgraph.constants import END
from langgraph.graph import add_messages
from langgraph.graph.state import StateGraph


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


async def agent(state: State) -> dict:
    # do async work here (LLM call, I/O, etc.)
    return {"messages": ["done"]}


graph = (
    StateGraph(State)
    .add_node("agent", agent)
    .set_entry_point("agent")
    .add_edge("agent", END)
    .compile()
)

result = await graph.ainvoke({"messages": []})
```

#### Recipe: Batch multiple runs (`graph.batch`) with per-run configs
This is the “throughput” pattern used in tests: compile once, then execute many runs with different `thread_id`s/configs.

**Source:** `libs/langgraph/tests/test_pregel.py` (`test_store_injected`)

```python
from __future__ import annotations

import operator
import uuid
from typing import Annotated

from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict

from langgraph.graph.state import StateGraph
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore


class State(TypedDict):
    count: Annotated[int, operator.add]


class Node:
    def __call__(self, inputs: State, config: RunnableConfig, store: BaseStore) -> dict:
        # Store is injected when the graph is compiled with store=...
        store.put(("runs",), "latest", {"thread_id": config["configurable"]["thread_id"]})
        return {"count": 1}


store = InMemoryStore()
graph = (
    StateGraph(State)
    .add_node("node", Node())
    .add_edge("__start__", "node")
    .compile(store=store)
)

inputs = [{"count": 0}, {"count": 0}]
configs = [
    {"configurable": {"thread_id": str(uuid.uuid4())}},
    {"configurable": {"thread_id": str(uuid.uuid4())}},
]

results = graph.batch(inputs, configs)
```

#### Recipe: Parallel task fan-out inside `@entrypoint` (Functional API futures)
This is the core “high-perf” pattern for CPU/I/O parallelization: call `@task` functions and collect `.result()` futures.

**Source:** `libs/langgraph/tests/test_pregel.py` (`test_imp_task`)

```python
import time
from typing_extensions import TypedDict

from langgraph.func import entrypoint, task


class Context(TypedDict):
    model: str


@task()
def mapper(x: int) -> str:
    time.sleep(x / 100)
    return str(x) * 2


@entrypoint(context_schema=Context)
def workflow(values: list[int]) -> list[str]:
    futures = [mapper(v) for v in values]
    return [f.result() for f in futures]


out = workflow.invoke([0, 1], context={"model": "test"})
assert out == ["00", "11"]
```

### 2.3 The “Resilient” Path (Timeouts, Retries, Interrupt/Resume)

#### Recipe: Node retries with `RetryPolicy`
**Source:** `libs/langgraph/tests/test_retry.py` (`test_graph_with_single_retry_policy`)

```python
from typing_extensions import TypedDict

from langgraph.graph import START, StateGraph
from langgraph.types import RetryPolicy


class State(TypedDict):
    foo: str


attempts = 0

def flaky(state: State) -> dict:
    global attempts
    attempts += 1
    if attempts < 3:
        raise ValueError("Intentional failure")
    return {"foo": "ok"}


retry_policy = RetryPolicy(
    max_attempts=3,
    initial_interval=0.01,
    backoff_factor=2.0,
    jitter=False,
    retry_on=ValueError,
)

graph = (
    StateGraph(State)
    .add_node("flaky", flaky, retry_policy=retry_policy)
    .add_edge(START, "flaky")
    .compile()
)

graph.invoke({"foo": ""})
```

#### Recipe: Step timeout for “hung” streaming consumers (`graph.step_timeout`)
In tests, the timeout is applied by setting `graph.step_timeout` **after** compile.

**Source:** `libs/langgraph/tests/test_pregel_async.py` (`test_step_timeout_on_stream_hang`)

```python
import asyncio
from typing_extensions import TypedDict

from langgraph.graph.state import StateGraph


class State(TypedDict):
    hello: str


async def slow(_: State) -> None:
    await asyncio.sleep(1.5)


async def fast(_: State) -> dict:
    await asyncio.sleep(0.6)
    return {"hello": "1"}


graph = (
    StateGraph(State)
    .add_node(slow)
    .add_node(fast)
    .set_conditional_entry_point(lambda _: ["slow", "fast"])
    .compile()
)

graph.step_timeout = 1  # seconds

try:
    async for chunk in graph.astream({"hello": "world"}, stream_mode="updates"):
        # simulate a slow consumer that can cause backpressure
        await asyncio.sleep(0.6)
except asyncio.TimeoutError:
    pass
```

#### Recipe: Human-in-the-loop interrupt + resume (StateGraph)
This is the canonical “pause and resume” pattern: you must enable a checkpointer and provide `thread_id`.

**Source:** `libs/langgraph/tests/test_pregel.py` (`test_double_interrupt_subgraph`)

```python
import uuid
from typing_extensions import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.constants import START, END
from langgraph.graph.state import StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict):
    input: str


def node_1(state: State) -> dict:
    return {"input": interrupt("interrupt node 1")}


def node_2(state: State) -> dict:
    return {"input": interrupt("interrupt node 2")}


checkpointer = InMemorySaver()
graph = (
    StateGraph(State)
    .add_node("node_1", node_1)
    .add_node("node_2", node_2)
    .add_edge(START, "node_1")
    .add_edge("node_1", "node_2")
    .add_edge("node_2", END)
    .compile(checkpointer=checkpointer)
)

thread = {"configurable": {"thread_id": str(uuid.uuid4())}}

# First run interrupts on node_1
events = list(graph.stream({"input": "test"}, thread))
assert "__interrupt__" in events[0]

# Resume node_1 → interrupts on node_2
events = list(graph.stream(Command(resume="123"), thread))

# Resume node_2 → completes
events = list(graph.stream(Command(resume="456"), thread))
```

#### Recipe: Durability mode for checkpoint persistence (`durability="sync"|"async"|"exit"`)
**Source:** `libs/langgraph/tests/test_pregel.py` (`test_imp_task`)

```python
import uuid
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.types import Command, interrupt


@task()
def twice(x: int) -> int:
    return 2 * x


@entrypoint(checkpointer=InMemorySaver())
def wf(xs: list[int]) -> list[int]:
    ys = [twice(x).result() for x in xs]
    suffix = interrupt("question")
    return [int(str(y) + suffix) for y in ys]


config = {"configurable": {"thread_id": str(uuid.uuid4())}}
list(wf.stream([1, 2], config, durability="async"))  # emits task updates + interrupt
wf.invoke(Command(resume="0"), config, durability="async")
```

## 3. Meta-Testing Guide (How to Mock It in Your Backend Tests)

### 3.1 Make IDs deterministic (don’t snapshot-randomness)
Tests patch `uuid.uuid4()` to deterministic values for repeatability.

**Source:** `libs/langgraph/tests/conftest.py` (fixture: `deterministic_uuids`)

```python
from uuid import UUID

def test_deterministic_ids(mocker):
    side_effect = (
        UUID(f"00000000-0000-4000-8000-{i:012}", version=4) for i in range(10000)
    )
    mocker.patch("uuid.uuid4", side_effect=side_effect)
    # now uuid.uuid4() is stable in this test
```

### 3.2 Use a fake chat model instead of mocking your graph internals
Rather than mocking `StateGraph`/`Pregel` internals, tests use a deterministic fake LLM.

**Source:** `libs/langgraph/tests/fake_chat.py` (class: `FakeChatModel`)

```python
from langchain_core.messages import AIMessage
from tests.fake_chat import FakeChatModel

model = FakeChatModel(messages=[AIMessage(content="hello"), AIMessage(content="world")])
out = model.invoke([("user", "hi")])
assert out.content in {"hello", "world"}
```

### 3.3 Don’t assert on auto-generated message IDs (normalize them)
Tests either:
- compare messages with “any id” wrappers, or
- set IDs to `None` before equality checks.

**Source:** `libs/langgraph/tests/test_messages_state.py`

### 3.4 Mock RemoteGraph by injecting a fake client (don’t monkeypatch HTTP)
`RemoteGraph` is designed to accept explicit `sync_client` / `client` objects; tests pass `MagicMock`/`AsyncMock` and control return values.

**Source:** `libs/langgraph/tests/test_remote_graph.py` (`test_get_graph`, `test_get_state`, `test_aget_graph`, ...)

```python
from unittest.mock import MagicMock

from langgraph.pregel.remote import RemoteGraph

mock_sync_client = MagicMock()
mock_sync_client.assistants.get_graph.return_value = {"nodes": [], "edges": []}

remote = RemoteGraph("test_graph_id", sync_client=mock_sync_client)
graph = remote.get_graph()
assert graph.nodes == {}
```

### 3.5 Separate unit tests vs integration tests with a `NO_DOCKER` gate
The repo’s integration tests hard-skip when `NO_DOCKER=true` is set.

**Source:** `libs/langgraph/tests/conftest.py`, `libs/langgraph/tests/test_remote_graph.py`

Recommended pattern:
- Unit tests: use `InMemorySaver()` + `InMemoryStore()` + `InMemoryCache()`
- Integration tests: spin Postgres/Redis via docker compose and run the real adapters

