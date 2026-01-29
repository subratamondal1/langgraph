"""
05_example_durability_checkpoint_resume.py

Goal: Show why durability forces design decisions in:
- IDs (stable task identity across resume)
- ordering (deterministic commit)
- concurrency (tasks can run in parallel, but commit must be replayable)

We simulate:
1) Run step 1, execute ONE task, then "crash"
2) Resume from a checkpoint

Case A: stable task IDs -> we can dedupe and avoid re-running work.
Case B: random task IDs -> resume can't dedupe; work gets repeated.
"""

from __future__ import annotations

import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable


@dataclass
class Checkpoint:
    # "Durable record" of completed task outputs: task_id -> (item, result)
    completed: dict[str, tuple[int, int]]


def stable_task_id(item: int) -> str:
    # Deterministic: can be recomputed on resume.
    return f"worker:item={item}"


def random_task_id(_: int) -> str:
    # Non-deterministic: changes on resume -> can't dedupe.
    return str(uuid.uuid4())


def worker(item: int) -> int:
    time.sleep(random.uniform(0.01, 0.05))
    return item * 2


def run_step_with_possible_crash(
    items: list[int],
    checkpoint: Checkpoint,
    task_id_fn: Callable[[int], str],
    crash_after_n_completions: int,
) -> Checkpoint:
    # Create tasks (id + payload)
    tasks: list[tuple[str, int]] = [(task_id_fn(x), x) for x in items]

    # Skip tasks already completed (dedupe)
    runnable = [(tid, x) for tid, x in tasks if tid not in checkpoint.completed]

    with ThreadPoolExecutor(max_workers=4) as pool:
        future_to_task = {pool.submit(worker, x): (tid, x) for tid, x in runnable}
        completions = 0

        for fut in as_completed(future_to_task):
            tid, x = future_to_task[fut]
            result = fut.result()

            # "Durable capture": persist the task's output keyed by task_id.
            # This is the key idea: on resume, stable task IDs let you see that
            # this output already exists and avoid repeating work.
            checkpoint.completed[tid] = (x, result)
            completions += 1

            print(f"  finished {tid} (item={x}) -> result={result}")
            print(f"  checkpoint.completed task_ids now: {sorted(checkpoint.completed)}")

            if completions >= crash_after_n_completions:
                raise RuntimeError("💥 simulated crash after some tasks completed")

    return checkpoint


def demo(task_id_fn: Callable[[int], str], title: str) -> None:
    items = [1, 2, 3]
    ckpt = Checkpoint(completed={})

    print(f"\n=== {title} ===")
    print("Items:", items)

    print("\nRun #1 (will crash after 1 completion)")
    try:
        run_step_with_possible_crash(items, ckpt, task_id_fn, crash_after_n_completions=1)
    except RuntimeError as exc:
        print("Caught crash:", exc)

    print("\nResume from checkpoint (run remaining tasks)")
    try:
        run_step_with_possible_crash(items, ckpt, task_id_fn, crash_after_n_completions=10)
    except RuntimeError as exc:
        print("Unexpected crash:", exc)

    print("\nFinal checkpoint:")
    for tid in sorted(ckpt.completed):
        item, result = ckpt.completed[tid]
        print(f" - {tid}: item={item} result={result}")

    # Show what "final output" assembly might look like.
    # With stable IDs, we can deterministically assemble results in item order.
    if task_id_fn is stable_task_id:
        assembled = [ckpt.completed[stable_task_id(item)][1] for item in items]
        print("\nAssembled results (deterministic item order):", assembled)
    else:
        print(
            "\nAssembled results: cannot deterministically assemble by 'task_id_fn(item)'\n"
            "because IDs change on resume. Notice duplicates: the same item may appear\n"
            "multiple times under different random task IDs."
        )


def main() -> None:
    demo(stable_task_id, "Case A: Stable IDs (dedupe works on resume)")
    demo(random_task_id, "Case B: Random IDs (dedupe breaks; resume repeats work)")

    print(
        "\nTakeaway:\n"
        "- Durability (resume) needs stable task identity.\n"
        "- Concurrency means completion order varies.\n"
        "- So commits must apply writes in a deterministic order to stay replayable."
    )


if __name__ == "__main__":
    main()
