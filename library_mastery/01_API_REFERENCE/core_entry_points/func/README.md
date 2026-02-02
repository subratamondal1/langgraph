# `langgraph.func` (Functional API)

## What you import from here

Public exports:
- `task`: decorator that turns a function into a LangGraph task.
- `entrypoint`: decorator that compiles a function into an executable workflow.

## The core mental model

### 1) `@task` returns futures

Calling a `@task` function inside an entrypoint returns a “future-like” object.

That’s intentional: it makes **parallelism explicit**:

```python
f1 = my_task(x)
f2 = my_task(y)
return f1.result() + f2.result()
```

### 2) `@entrypoint` gives you `.invoke()` / `.stream()`

An entrypoint is compiled into a runnable workflow with:
- `.invoke(...)` / `.ainvoke(...)`
- `.stream(...)` / `.astream(...)`

### 3) Tasks/entrypoints are “graph-safe”

When you enable checkpointing or persistence, inputs/outputs should be serializable.

## Example

- `tasks_and_entrypoint.py` shows fan-out/fan-in parallelism with `@task`.

