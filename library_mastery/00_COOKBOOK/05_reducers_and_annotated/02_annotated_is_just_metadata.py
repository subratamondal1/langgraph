from pathlib import Path
import sys
from typing import Annotated, get_args, get_origin

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _utils import show, step, title


title("02 — Annotated is just metadata attached to a type")

def append(left: list[str], right: list[str] | None) -> list[str]:
    return left + (right or [])


step("1) Annotated[T, metadata] wraps a normal type + extra metadata")
T = Annotated[list[str], append]

show("origin", get_origin(T))
show("args", get_args(T))

step("2) For LangGraph, that 'metadata' is the reducer function")
type_part, reducer = get_args(T)
show("type_part", type_part)
show("reducer", reducer)

print("\nLangGraph reads this metadata to know how to merge concurrent updates.")

