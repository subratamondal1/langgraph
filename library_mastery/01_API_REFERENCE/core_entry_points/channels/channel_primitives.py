from __future__ import annotations

from pathlib import Path
import operator
import sys


def _bootstrap_langgraph_namespace() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    for rel in ("libs/langgraph", "libs/checkpoint", "libs/prebuilt"):
        sys.path.insert(0, str(repo_root / rel))


def main() -> None:
    _bootstrap_langgraph_namespace()

    from langgraph.channels import (
        BinaryOperatorAggregate,
        EphemeralValue,
        LastValue,
        NamedBarrierValue,
        Topic,
    )

    # LastValue: exactly 1 update per step
    last = LastValue(int, key="x")
    last.update([1])
    print("LastValue after one update:", last.get())

    # Topic(accumulate=True): collects all updates across steps
    topic = Topic(str, accumulate=True)
    topic.update(["a", "b"])
    topic.update(["c"])
    print("Topic(accumulate=True):", topic.get())

    # BinaryOperatorAggregate: reduces all updates into a stored value
    total = BinaryOperatorAggregate(int, operator.add)
    total.update([1, 2, 3])
    print("BinaryOperatorAggregate(add):", total.get())

    # EphemeralValue: clears if no updates occur in a step
    eph = EphemeralValue(str)
    eph.update(["hello"])
    print("EphemeralValue after update:", eph.get())
    eph.update([])  # next step has no updates -> clears
    print("EphemeralValue available after empty step?:", eph.is_available())

    # NamedBarrierValue: becomes available only after all expected names are seen
    barrier = NamedBarrierValue(str, names={"A", "B"})
    barrier.update(["A"])
    print("Barrier available after A?:", barrier.is_available())
    barrier.update(["B"])
    print("Barrier available after A+B?:", barrier.is_available())


if __name__ == "__main__":
    main()

