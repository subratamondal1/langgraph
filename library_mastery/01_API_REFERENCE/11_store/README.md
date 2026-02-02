# Section 11 — Persistence: Store (`langgraph.store.*`)

This folder is a runnable companion to **Section 11** of `library_mastery/01_API_REFERENCE.md`.

Goal: treat the store as shared, queryable memory:
- hierarchical namespaces (`("users", "u1")`, etc.)
- `put/get/search/list_namespaces` APIs
- store injection into graphs (`compile(store=...)`) and access via `Runtime.store` / `get_store()`

## Files

- `store_basics.py`
  - demonstrates `put`, `get`, `search(filter=...)`, and `list_namespaces`

- `store_used_from_graph.py`
  - compiles a graph with a store
  - reads/writes per-user counters to show persistence across invocations

## Run

```bash
./.venv/bin/python library_mastery/01_API_REFERENCE/11_store/store_used_from_graph.py
```

