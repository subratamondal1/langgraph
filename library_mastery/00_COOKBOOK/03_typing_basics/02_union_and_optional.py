from pathlib import Path
import sys
from typing import Optional, Union

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _utils import show, step, title


title("02 — Union and Optional")

step("1) Union means 'this OR that'")
Number = Union[int, float]

def double(x: Number) -> Number:
    return x * 2

show("double(3)", double(3))
show("double(2.5)", double(2.5))

step("2) Optional[T] means T OR None")
def greet(name: Optional[str]) -> str:
    if name is None:
        return "Hello, stranger!"
    return f"Hello, {name}!"

show("greet(None)", greet(None))
show("greet('Ada')", greet("Ada"))

