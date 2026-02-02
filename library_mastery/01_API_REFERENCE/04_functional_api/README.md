# Section 4 — Functional API (`langgraph.func`)

This folder is a runnable companion to **Section 4** of `library_mastery/01_API_REFERENCE.md`.

Goal: treat the functional API like a serious workflow runtime:
- tasks return **futures** (explicit fan-out/fan-in)
- `entrypoint(...)` compiles a workflow into a runnable with `.invoke()` / `.stream()`
- retries and caching are first-class (policies + injected cache)
- checkpointing enables `previous` and interrupts/resume

## Files

- `fanout_fanin_tasks.py`
  - shows how tasks return futures and how you join results

- `previous_across_invocations.py`
  - shows how `previous` works when you provide a checkpointer and reuse `thread_id`

- `retry_and_cache_policies.py`
  - demonstrates per-task retries (`RetryPolicy`)
  - demonstrates per-task caching (`CachePolicy`) using `InMemoryCache`

## Run

```bash
./.venv/bin/python library_mastery/01_API_REFERENCE/04_functional_api/retry_and_cache_policies.py
```

