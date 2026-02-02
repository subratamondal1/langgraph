# `langgraph.errors` (Exceptions + Error Codes)

## What you import from here

Public exports include:
- `ErrorCode`: stable identifiers for troubleshooting categories.
- `GraphRecursionError`: raised when a graph exceeds `recursion_limit`.
- `InvalidUpdateError`: raised on invalid concurrent updates / invalid node returns.
- `EmptyChannelError`, `EmptyInputError`, `TaskNotFound`
- `GraphInterrupt` (internal carrier for interrupts)
- `ParentCommand` (bubble `Command` to a parent graph)

## The core mental model

LangGraph tries to fail “loudly and usefully”:
- Errors often include a linkable `ErrorCode` to point you at the right docs.
- Many “mysterious” failures are actually **state merge semantics** problems (two writers, no reducer).

## Examples

- `common_errors.py` triggers (and catches) a recursion error and a concurrent update error.

