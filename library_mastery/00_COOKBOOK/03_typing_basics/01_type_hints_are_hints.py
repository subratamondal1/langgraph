from pathlib import Path
import sys

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _utils import show, step, title


title("01 — Type hints are NOT runtime enforcement")

step("1) A function can have type hints")
def add_one(x: int) -> int:
    return x + 1


step("2) When you pass the right type, it behaves as expected")
show("add_one(10)", add_one(10))

step("3) Python still lets you pass the wrong type at runtime")
try:
    # This will crash because 'hello' + 1 is not valid.
    add_one("hello")  # type: ignore[arg-type]
except TypeError as e:
    show("TypeError", str(e))

step("4) The key point: hints help tooling (mypy/pyright), not Python runtime")
print("Type hints = guidance for humans and tools.")

