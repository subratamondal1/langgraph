from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from langgraph.func import entrypoint, task

    @task
    def square(x: int) -> int:
        return x * x

    @entrypoint()
    def workflow(values: list[int]) -> dict:
        futures = [square(v) for v in values]  # fan-out
        results = [f.result() for f in futures]  # fan-in
        return {"input": values, "squares": results}

    banner("Functional fan-out/fan-in")
    show("invoke output", workflow.invoke([1, 2, 3, 4]))


if __name__ == "__main__":
    main()

