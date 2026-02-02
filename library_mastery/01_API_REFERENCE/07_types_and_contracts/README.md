# Section 7 — Control Plane & Data Contracts (`langgraph.types`)

This folder is a runnable companion to **Section 7** of `library_mastery/01_API_REFERENCE.md`.

Goal: understand the “control plane” primitives that make LangGraph more than a DAG:
- `Command` (update state + navigate + resume interrupts)
- `Send` (fan-out execution)
- `Overwrite` (replace aggregate values inside reducer channels)
- `StreamMode` (what the runtime emits)

## Files

- `00_cookbook.py`
  - production-first control-plane patterns: `Send`, `Command`, `interrupt/resume`, `Overwrite`

- `command_goto_routing.py`
  - uses `Command(goto=...)` to choose the next node dynamically
  - shows how this differs from static edges

- `overwrite_semantics.py`
  - demonstrates `Overwrite(...)` inside `BinaryOperatorAggregate`

- `stream_modes_quicklook.py`
  - runs one small graph and prints what different `stream_mode` settings produce

## Run

```bash
./.venv/bin/python library_mastery/01_API_REFERENCE/07_types_and_contracts/command_goto_routing.py
```
