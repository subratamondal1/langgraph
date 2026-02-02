from pathlib import Path
import sys
from typing import TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _utils import show, step, title


title("04 — TypedDict is NOT validation (so here's manual validation)")

class User(TypedDict):
    id: str
    age: int


def validate_user(data: dict) -> User:
    """
    Simple runtime validation:
    - ensure required keys exist
    - ensure types look right
    """
    if "id" not in data:
        raise ValueError("missing key: id")
    if "age" not in data:
        raise ValueError("missing key: age")
    if not isinstance(data["id"], str):
        raise ValueError("id must be str")
    if not isinstance(data["age"], int):
        raise ValueError("age must be int")
    # If valid, we "cast" it to User
    return {"id": data["id"], "age": data["age"]}


step("1) Good input")
good = {"id": "u1", "age": 30}
show("good (input)", good)
show("validate_user(good)", validate_user(good))

step("2) Bad input (missing keys / wrong types)")
bad = {"id": 123}
show("bad (input)", bad)
try:
    validate_user(bad)
except ValueError as e:
    show("ValueError", str(e))

