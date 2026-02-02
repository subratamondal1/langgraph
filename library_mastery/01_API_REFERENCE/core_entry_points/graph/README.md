# `langgraph.graph` (Graph API)

## What you import from here

`langgraph.graph` is the **Graph API** entry point: the most common “start here” module.

Public exports:
- `START`, `END`: special node IDs used when wiring edges.
- `StateGraph`: the main builder for shared-state graphs.
- `add_messages`, `MessagesState`: helpers for building message-centric graphs.
- `MessageGraph`: deprecated legacy convenience wrapper.

## The core mental model

### 1) Builder vs. executable

`StateGraph(...)` creates a **builder**. You can add nodes/edges/branches, but you can’t run it yet.

Calling `.compile(...)` returns an executable graph (a `Pregel` under the hood) with methods like:
- `.invoke(...)` (run to completion, return final state)
- `.stream(...)` (iterate steps/events)
- async variants: `.ainvoke(...)`, `.astream(...)`

### 2) Nodes are “state → partial state”

A node is typically a function:

```python
def my_node(state: State) -> dict:
    return {"some_key": new_value}
```

It reads from the current state and returns a **partial update** (only the keys it changes).

### 3) Reducers decide how concurrent writes merge

If multiple nodes update the same key in the same step, LangGraph needs to know how to merge them.

- Default behavior for many state keys is “single writer per step”.
- For “append/merge” behaviors you annotate keys with a reducer (e.g. `add_messages` for chat history).

## Examples

- `stategraph_basics.py` shows:
  - wiring `START → node → END`
  - a tiny state update
  - `MessagesState`/`add_messages` message accumulation

