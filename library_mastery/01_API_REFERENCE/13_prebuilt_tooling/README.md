# Section 13 — Prebuilt Tooling (`langgraph.prebuilt`)

This folder is a runnable companion to **Section 13** of `library_mastery/01_API_REFERENCE.md`.

Goal: understand the building blocks behind “tool-calling agents”:
- `ToolNode`: executes tool calls found in the last `AIMessage`
- `tools_condition`: standard conditional router (`"tools"` vs `"__end__"`)
- `InjectedState` / `InjectedStore`: inject graph state/store into tool functions

## Files

- `00_cookbook.py`
  - production-first agent building blocks: ToolNode, tools_condition, injection, error handling

- `toolnode_with_tools_condition.py`
  - builds a tiny graph that:
    - creates an `AIMessage(tool_calls=[...])`
    - routes to `ToolNode` using `tools_condition`
  - prints the final message list so you can see tool results

- `tool_injection_state_and_store.py`
  - demonstrates injecting state/store into a tool via annotations
  - writes to a store from inside the tool and shows the stored value

## Run

```bash
./.venv/bin/python library_mastery/01_API_REFERENCE/13_prebuilt_tooling/tool_injection_state_and_store.py
```
