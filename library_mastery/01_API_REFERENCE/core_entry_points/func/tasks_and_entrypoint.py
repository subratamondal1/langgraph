from __future__ import annotations

from pathlib import Path
import sys


def _bootstrap_langgraph_namespace() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    for rel in ("libs/langgraph", "libs/checkpoint", "libs/prebuilt"):
        sys.path.insert(0, str(repo_root / rel))


def main() -> None:
    _bootstrap_langgraph_namespace()

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

