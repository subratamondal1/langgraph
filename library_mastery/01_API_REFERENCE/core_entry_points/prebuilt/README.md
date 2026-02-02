# `langgraph.prebuilt` (Optional High-Level Helpers)

## What you import from here

This entry point comes from the `langgraph-prebuilt` distribution (bundled alongside `langgraph`).

Public exports:
- `ToolNode`, `tools_condition`
- `ToolRuntime`, `InjectedState`, `InjectedStore`
- `create_react_agent` (**deprecated**)
- `ValidationNode` (**deprecated**)

## The core mental model

Prebuilt modules help you assemble common agent patterns faster:
- `ToolNode` executes tool calls found in the last `AIMessage`.
- `tools_condition` is commonly used in conditional routing:
  - if the model produced tool calls → run `ToolNode`
  - else → finish

If you want the newest agent-building APIs, note the deprecations:
- `create_react_agent` moved toward `langchain.agents`
- `ValidationNode` is deprecated in favor of newer patterns

## Example

- `tool_node_basic.py` runs a tool call without any LLM by crafting an `AIMessage(tool_calls=[...])`.

