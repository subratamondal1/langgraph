"""
02_example_messages_graph.py

Goal: Show what a "messages graph" looks like (chat history as state),
including how updates are merged and how streaming outputs can look.

This is a small educational model:
- "messages" is a channel whose merge rule is "append".
- a node returns only the new messages it wants to add.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal

StreamMode = Literal["values", "updates", "debug"]

State = dict[str, Any]
NodeFn = Callable[[State], State]


def append_messages(existing: list[str], new: Iterable[str]) -> list[str]:
    return list(existing) + list(new)


@dataclass(frozen=True)
class MiniMessagesGraph:
    node: NodeFn
    stream_mode: StreamMode = "values"

    def invoke(self, state: State) -> State:
        return list(self.stream(state))[-1] if self.stream_mode == "values" else self._run(state)

    def _run(self, state: State) -> State:
        state = {"messages": list(state.get("messages", []))}
        updates = self.node(dict(state))
        # merge rule: messages append
        state["messages"] = append_messages(state["messages"], updates.get("messages", []))
        return state

    def stream(self, state: State):
        state = {"messages": list(state.get("messages", []))}
        updates = self.node(dict(state))
        state["messages"] = append_messages(state["messages"], updates.get("messages", []))

        if self.stream_mode == "updates":
            yield {"messages": updates.get("messages", [])}
        elif self.stream_mode == "debug":
            yield {
                "event": "task_end",
                "node": self.node.__name__,
                "writes": {"messages": updates.get("messages", [])},
                "state_after_commit": dict(state),
            }
        else:
            # "values": yield the full state after commit
            yield dict(state)


def main() -> None:
    def respond(state: State) -> State:
        last = state["messages"][-1] if state["messages"] else "<empty>"
        return {"messages": [f"ai: echo({last})"]}

    input_state = {"messages": ["human: hello"]}

    print("\n=== Messages graph demo (append merge) ===")
    print(f"Input:  {input_state}")

    app = MiniMessagesGraph(node=respond, stream_mode="values")
    out = app._run(input_state)
    print(f"Output: {out}")
    print("Messages (pretty):")
    for m in out["messages"]:
        print(" -", m)

    print("\n=== Streaming mode: values ===")
    for event in MiniMessagesGraph(node=respond, stream_mode="values").stream(input_state):
        print(event)

    print("\n=== Streaming mode: updates ===")
    for event in MiniMessagesGraph(node=respond, stream_mode="updates").stream(input_state):
        print(event)

    print("\n=== Streaming mode: debug ===")
    for event in MiniMessagesGraph(node=respond, stream_mode="debug").stream(input_state):
        print(event)


if __name__ == "__main__":
    main()

