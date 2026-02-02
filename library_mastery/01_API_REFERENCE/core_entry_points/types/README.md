# `langgraph.types` (Contracts + Control Plane)

## What you import from here

This module is the “control plane” and shared contracts:
- `StreamMode`, `StreamWriter`
- `RetryPolicy`, `CachePolicy`
- `Interrupt`, `interrupt`
- `Send`, `Command`, `Overwrite`
- plus execution/state objects (`StateSnapshot`, `PregelTask`, etc.)

## The core mental model

### `Send`
Represents “run this node with this input”. It’s useful for **fan-out**:
- generate a list of `Send(...)` objects
- LangGraph runs one task per send

### `interrupt` + `Command(resume=...)`
`interrupt(value)` pauses execution (requires a checkpointer), emits an interrupt event, and lets a client resume later via `Command(resume=...)`.

## Examples

- `send_and_interrupt.py` shows:
  - fan-out using `Send`
  - human-in-the-loop pause/resume using `interrupt` + `Command`

