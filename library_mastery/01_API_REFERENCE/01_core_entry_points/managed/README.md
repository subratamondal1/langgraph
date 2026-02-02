# `langgraph.managed` (Managed Values)

## What you import from here

Public exports:
- `IsLastStep`
- `RemainingSteps`

These are `typing.Annotated[...]` aliases backed by internal `ManagedValue` providers.

## The core mental model

Managed values are **state keys whose values are computed by the runtime**, not written by nodes.

They’re useful when you want node logic like:
- “If this is the last allowed step, stop.”
- “How many steps remain before recursion limit?”

## Example

- `managed_values.py` defines a state schema containing managed keys and prints them.

