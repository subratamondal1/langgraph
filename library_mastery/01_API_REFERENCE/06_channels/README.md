# Section 6 — Channels (`langgraph.channels`)

This folder is a runnable companion to **Section 6** of `library_mastery/01_API_REFERENCE.md`.

Goal: understand channels as the core state/merge primitive:
- every channel defines a stored value type + update type + merge behavior
- “two writers” errors are usually “your channel forbids multiple updates per step”
- `StateGraph` schemas compile into a concrete channel per state key

## Files

- `00_cookbook.py`
  - production-first channel selection + schema-to-channel compilation

- `channel_semantics_after_finish.py`
  - demonstrates channels whose values only become readable after `finish()`
  - shows `consume()` clearing semantics

- `schema_compiles_to_channels.py`
  - defines a state schema with a reducer and compiles a graph
  - prints the compiled channel classes for each key (how your schema becomes runtime storage)

## Run

```bash
./.venv/bin/python library_mastery/01_API_REFERENCE/06_channels/schema_compiles_to_channels.py
```
