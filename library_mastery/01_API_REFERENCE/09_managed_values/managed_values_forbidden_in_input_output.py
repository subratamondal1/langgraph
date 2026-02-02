from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner

bootstrap_langgraph_namespace()

from typing import TypedDict

from langgraph.graph import StateGraph
from langgraph.managed import RemainingSteps


class State(TypedDict, total=False):
    remaining: RemainingSteps
    x: int


class Input(TypedDict, total=False):
    # This is intentionally invalid: managed values are not allowed in input/output schemas.
    remaining: RemainingSteps
    x: int


def main() -> None:
    banner("Managed values are forbidden in input/output schemas")
    try:
        StateGraph(state_schema=State, input_schema=Input)
    except ValueError as e:
        print("Caught:", type(e).__name__)
        print(str(e).splitlines()[0])


if __name__ == "__main__":
    main()

