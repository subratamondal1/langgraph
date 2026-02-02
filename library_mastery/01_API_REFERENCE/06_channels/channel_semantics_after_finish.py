from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from langgraph.channels import LastValueAfterFinish, NamedBarrierValueAfterFinish

    banner("LastValueAfterFinish")
    lv = LastValueAfterFinish(int, key="x")
    lv.update([1])
    show("available after update?", lv.is_available())
    lv.finish()
    show("available after finish?", lv.is_available())
    show("get()", lv.get())
    lv.consume()
    show("available after consume?", lv.is_available())

    banner("NamedBarrierValueAfterFinish")
    barrier = NamedBarrierValueAfterFinish(str, names={"A", "B"})
    barrier.update(["A"])
    show("available after A?", barrier.is_available())
    barrier.update(["B"])
    show("available after A+B (before finish)?", barrier.is_available())
    barrier.finish()
    show("available after finish?", barrier.is_available())
    show("get()", barrier.get())
    barrier.consume()
    show("available after consume?", barrier.is_available())


if __name__ == "__main__":
    main()

