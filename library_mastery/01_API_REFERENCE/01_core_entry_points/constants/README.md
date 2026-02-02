# `langgraph.constants` (Shared Constants)

## What you import from here

Public exports:
- `START`, `END`: virtual nodes used for graph wiring.
- `TAG_NOSTREAM`: a tag used to suppress streaming for certain traced calls.
- `TAG_HIDDEN`: a tag used to hide runs/nodes in some tracing environments.

## Deprecation trap

`langgraph.constants` intentionally warns on certain imports:
- `Send` / `Interrupt` are now in `langgraph.types`.
- Many internal constants moved to `langgraph._internal._constants`.

So: treat `langgraph.constants` as a small set of stable values; don’t build new code on the deprecated proxies.

## Example

- `start_end_and_tags.py` prints the constants and shows a typical place you’d pass tags.

