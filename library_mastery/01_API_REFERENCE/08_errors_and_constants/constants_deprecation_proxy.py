from __future__ import annotations

from pathlib import Path
import sys
import warnings

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner


def main() -> None:
    bootstrap_langgraph_namespace()

    banner("Deprecated proxy: importing Send from langgraph.constants")
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")

        # This triggers langgraph.constants.__getattr__ and emits a deprecation warning.
        from langgraph.constants import Send  # noqa: F401

    for w in captured:
        print(f"{w.category.__name__}: {w.message}")


if __name__ == "__main__":
    main()

