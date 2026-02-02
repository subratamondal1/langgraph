from __future__ import annotations

from pathlib import Path
import sys
import uuid

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


class TransientError(Exception):
    """A retryable error (LangGraph's default retry predicate will retry this)."""


def recipe_parallel_tasks() -> None:
    from langgraph.func import entrypoint, task

    @task
    def add_one(x: int) -> int:
        return x + 1

    @entrypoint()
    def workflow(values: list[int]) -> list[int]:
        futures = [add_one(v) for v in values]
        return [f.result() for f in futures]

    banner("Functional API: parallel fan-out/fan-in")
    show("output", workflow.invoke([1, 2, 3]))


def recipe_previous_with_checkpointer() -> None:
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.func import entrypoint

    @entrypoint(checkpointer=InMemorySaver())
    def counter(_: int, *, previous: int | None = None) -> int:
        return (previous or 0) + 1

    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}}

    banner("Functional API: previous across invocations (same thread_id)")
    show("first", counter.invoke(0, cfg))
    show("second", counter.invoke(0, cfg))


def recipe_retry_and_cache() -> None:
    from langgraph.cache.memory import InMemoryCache
    from langgraph.func import entrypoint, task
    from langgraph.types import CachePolicy, RetryPolicy

    attempts: dict[int, int] = {}
    expensive_calls = {"count": 0}

    @task(retry_policy=RetryPolicy(initial_interval=0.0, max_interval=0.0, max_attempts=2, jitter=False))
    def flaky(x: int) -> int:
        attempts[x] = attempts.get(x, 0) + 1
        if attempts[x] == 1:
            raise TransientError(f"boom (first attempt for {x})")
        return x + 10

    @task(cache_policy=CachePolicy())
    def expensive(x: int) -> int:
        expensive_calls["count"] += 1
        return x * 100

    cache = InMemoryCache()

    @entrypoint(cache=cache)
    def workflow(x: int) -> dict:
        return {"flaky": flaky(x).result(), "expensive": expensive(x).result()}

    banner("Functional API: RetryPolicy + CachePolicy")
    show("first", workflow.invoke(7))
    show("attempts", attempts)
    show("cache hit", workflow.invoke(7))
    show("expensive_calls", expensive_calls)


def recipe_interrupt_and_resume() -> None:
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.func import entrypoint, task
    from langgraph.types import Command, interrupt

    @task
    def generate(topic: str) -> str:
        return f"Draft about {topic}"

    @entrypoint(checkpointer=InMemorySaver())
    def review(topic: str) -> dict:
        draft = generate(topic).result()
        human = interrupt({"question": "Approve?", "draft": draft})
        return {"draft": draft, "review": human}

    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}}

    banner("Functional API: stream until interrupt")
    for chunk in review.stream("langgraph", cfg):
        print(chunk)

    banner("Functional API: resume")
    for chunk in review.stream(Command(resume={"approved": True, "notes": "ship it"}), cfg):
        print(chunk)


def main() -> None:
    bootstrap_langgraph_namespace()
    recipe_parallel_tasks()
    recipe_previous_with_checkpointer()
    recipe_retry_and_cache()
    recipe_interrupt_and_resume()


if __name__ == "__main__":
    main()

