from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace


def main() -> None:
    bootstrap_langgraph_namespace()

    from langgraph.func import entrypoint, task

    @task
    def add_one(x: int) -> int:
        return x + 1

    @entrypoint()
    def workflow(values: list[int]) -> list[int]:
        futures = [add_one(v) for v in values]  # fan-out
        return [f.result() for f in futures]  # fan-in

    print(workflow.invoke([1, 2, 3]))


if __name__ == "__main__":
    main()
