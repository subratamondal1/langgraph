from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from langgraph.cache.memory import InMemoryCache
    from langgraph.func import entrypoint, task
    from langgraph.types import CachePolicy, RetryPolicy

    attempts: dict[int, int] = {}
    compute_calls = {"count": 0}

    # Retry: fail once per input, then succeed.
    @task(retry_policy=RetryPolicy(initial_interval=0.0, max_interval=0.0, max_attempts=2, jitter=False))
    def flaky(x: int) -> int:
        attempts[x] = attempts.get(x, 0) + 1
        if attempts[x] == 1:
            raise ValueError(f"boom (first attempt for {x})")
        return x + 10

    # Cache: deterministic "expensive" computation.
    @task(cache_policy=CachePolicy())
    def expensive(x: int) -> int:
        compute_calls["count"] += 1
        return x * 100

    cache = InMemoryCache()

    @entrypoint(cache=cache)
    def workflow(x: int) -> dict:
        # `flaky` will retry and succeed.
        a = flaky(x).result()
        # `expensive` will be cached across invocations as long as `cache` is reused.
        b = expensive(x).result()
        return {"x": x, "flaky": a, "expensive": b}

    banner("RetryPolicy (flaky succeeds on retry)")
    show("output", workflow.invoke(7))
    show("attempts", attempts)

    banner("CachePolicy (expensive runs once for same input)")
    show("first", workflow.invoke(3))
    show("second", workflow.invoke(3))
    show("expensive compute calls", compute_calls)


if __name__ == "__main__":
    main()

