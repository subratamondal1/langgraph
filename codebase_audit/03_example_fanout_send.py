"""
03_example_fanout_send.py

Goal: Demonstrate "fan-out using Send" in Pregel terms.

Definitions:
- fan-out: one node creates many independent pieces of work.
- Send/PUSH: enqueue work to run in the *next* step (not immediately).

This toy engine has two steps:
1) router reads items and emits Send(work=item)
2) workers consume the sends and write results
"""

from __future__ import annotations

import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any


State = dict[str, Any]


@dataclass(frozen=True)
class Send:
    node: str
    payload: Any


def router(state: State) -> list[Send]:
    return [Send(node="worker", payload=x) for x in state["items"]]


def worker(x: int) -> int:
    time.sleep(random.uniform(0.01, 0.05))
    return x * 2


def main() -> None:
    state: State = {"items": [1, 2, 3], "results": []}

    print("\n=== Fan-out demo with Send ===")
    print(f"Step 0 input state: {state}")

    # STEP 0: router produces SENDs (fan-out)
    sends = router(state)
    print("Step 0 router emitted sends:")
    for s in sends:
        print(" -", s)

    # Important: workers do NOT run in step 0; they run in step 1.
    print("\nStep 1: executing worker tasks for each send (in parallel)")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(worker, s.payload): s for s in sends}
        completion_order: list[tuple[int, int]] = []  # (item, result)
        for fut in as_completed(futures):
            send = futures[fut]
            completion_order.append((send.payload, fut.result()))

    print(f"Worker completion order (non-deterministic): {completion_order}")

    # COMMIT: merge results deterministically (original item order)
    results_by_item = {item: result for item, result in completion_order}
    state["results"] += [results_by_item[item] for item in state["items"]]

    print(f"\nFinal state after commit: {state}")
    print("Expected results (stable):", [2, 4, 6])


if __name__ == "__main__":
    main()
