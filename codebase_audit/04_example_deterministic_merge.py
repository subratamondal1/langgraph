"""
04_example_deterministic_merge.py

Goal: Show how "stable merging" resolves parallel writes deterministically,
and what happens if you DON'T enforce a stable order.

We simulate two parallel tasks that both append to the same "messages" list.
- If we commit in completion order, results can flip (A,B) vs (B,A).
- If we commit in a stable sorted order, results are always the same.
"""

from __future__ import annotations

import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


def task_a(_: dict[str, Any]) -> dict[str, Any]:
    time.sleep(random.uniform(0.01, 0.05))
    return {"messages": ["A"]}


def task_b(_: dict[str, Any]) -> dict[str, Any]:
    time.sleep(random.uniform(0.01, 0.05))
    return {"messages": ["B"]}


def commit_append(existing: list[str], updates: list[dict[str, Any]]) -> list[str]:
    out = list(existing)
    for u in updates:
        out += u.get("messages", [])
    return out


def run_once(commit_mode: str) -> list[str]:
    initial_state = {"messages": ["hi"]}
    tasks = [("task_a", task_a), ("task_b", task_b)]

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_to_name = {pool.submit(fn, dict(initial_state)): name for name, fn in tasks}
        completion: list[tuple[str, dict[str, Any]]] = []
        for fut in as_completed(future_to_name):
            completion.append((future_to_name[fut], fut.result()))

    if commit_mode == "completion_order":
        ordered_updates = [u for _, u in completion]
    elif commit_mode == "stable_sorted":
        ordered_updates = [u for _, u in sorted(completion, key=lambda t: t[0])]
    else:
        raise ValueError("unknown commit_mode")

    final_messages = commit_append(initial_state["messages"], ordered_updates)
    return final_messages


def main() -> None:
    print("\n=== Deterministic merge demo ===")

    print("\nCommit mode: completion_order (can be flaky)")
    for i in range(5):
        print(f"run {i+1}:", run_once("completion_order"))

    print("\nCommit mode: stable_sorted (deterministic)")
    for i in range(5):
        print(f"run {i+1}:", run_once("stable_sorted"))

    print(
        "\nWhy this matters: if the order flips across runs, then a checkpoint/resume\n"
        "or parallel scheduling can produce different final state (hard-to-debug flakiness)."
    )


if __name__ == "__main__":
    main()

