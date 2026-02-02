# Section 9 — Managed Values (`langgraph.managed`)

This folder is a runnable companion to **Section 9** of `library_mastery/01_API_REFERENCE.md`.

Goal: understand managed values as “runtime-computed state”:
- managed keys are allowed in `state_schema`
- managed keys are **forbidden** in `input_schema` / `output_schema`
- values are computed from the runtime scratchpad (step counters, limits, etc.)

## Files

- `00_cookbook.py`
  - production-first managed values usage (graceful stop + schema rules)

- `managed_values_basic.py`
  - reads `RemainingSteps` / `IsLastStep` inside a node

- `managed_values_forbidden_in_input_output.py`
  - demonstrates the schema validation error when managed values appear in input/output schemas

- `managed_values_over_steps.py`
  - creates a tiny cycle and streams values so you can watch managed values change per step

## Run

```bash
./.venv/bin/python library_mastery/01_API_REFERENCE/09_managed_values/managed_values_over_steps.py
```
