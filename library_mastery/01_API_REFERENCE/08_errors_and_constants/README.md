# Section 8 — Errors & Constants (`langgraph.errors`, `langgraph.constants`)

This folder is a runnable companion to **Section 8** of `library_mastery/01_API_REFERENCE.md`.

Goal: debug production graphs quickly:
- recognize “classical” failures (`GraphRecursionError`, `InvalidUpdateError`)
- understand why many errors are *state merge semantics* problems
- understand constants and deprecation traps (`langgraph.constants.__getattr__`)

## Files

- `00_cookbook.py`
  - production-first debugging patterns for common exceptions + constants/deprecation traps

- `recursion_limit_error.py`
  - triggers and catches `GraphRecursionError`
  - prints the first line of the message (includes a troubleshooting link)

- `invalid_update_error_fix.py`
  - triggers `InvalidUpdateError` (two writers)
  - fixes it with an `Annotated` reducer

- `constants_deprecation_proxy.py`
  - shows how `langgraph.constants` warns and proxies deprecated imports

## Run

```bash
./.venv/bin/python library_mastery/01_API_REFERENCE/08_errors_and_constants/constants_deprecation_proxy.py
```
