from __future__ import annotations

from pathlib import Path
import operator
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from langgraph.channels import BinaryOperatorAggregate
    from langgraph.types import Overwrite

    banner("BinaryOperatorAggregate + Overwrite")
    total = BinaryOperatorAggregate(int, operator.add)
    total.update([1, 2, 3])
    show("after add(1,2,3)", total.get())

    # Overwrite replaces the stored value for this super-step.
    total.update([Overwrite(10), 999])
    show("after Overwrite(10), then 999", total.get())


if __name__ == "__main__":
    main()

