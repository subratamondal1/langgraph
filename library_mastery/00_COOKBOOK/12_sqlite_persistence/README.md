# 12 — SQLite durability (checkpoint + store + cache)

Goal: learn the 3 durability pieces you asked for:
- **checkpointing** (resume graph state by `thread_id`)
- **store** (general KV persistence)
- **cache** (avoid recomputing expensive nodes)

All SQLite files are written to `library_mastery/00_COOKBOOK/_scratch/` (git-ignored).

Run:

```bash
./.venv/bin/python library_mastery/00_COOKBOOK/12_sqlite_persistence/01_sqlite_checkpointer.py
./.venv/bin/python library_mastery/00_COOKBOOK/12_sqlite_persistence/02_sqlite_store.py
./.venv/bin/python library_mastery/00_COOKBOOK/12_sqlite_persistence/03_sqlite_cache.py
```

