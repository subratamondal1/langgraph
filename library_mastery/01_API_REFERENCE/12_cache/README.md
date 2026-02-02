# Section 12 — Persistence: Cache (`langgraph.cache.*`)

This folder is a runnable companion to **Section 12** of `library_mastery/01_API_REFERENCE.md`.

Goal: understand caching as a first-class runtime capability:
- caches store results keyed by a namespace + deterministic “args key”
- `CachePolicy` controls keying + TTL
- you can attach caching at the node/task level and inject a cache instance at runtime

## Files

- `00_cookbook.py`
  - production-first caching: direct cache usage + node caching via `CachePolicy`

- `cache_basics.py`
  - demonstrates `InMemoryCache.get/set/clear` directly
  - shows namespaces and TTL behavior (no graph involved)

- `graph_node_caching.py`
  - compiles a `StateGraph` with `cache=InMemoryCache()`
  - adds a node with `cache_policy=CachePolicy()`
  - invokes twice with the same input and shows the second call is cached

## Run

```bash
./.venv/bin/python library_mastery/01_API_REFERENCE/12_cache/graph_node_caching.py
```
