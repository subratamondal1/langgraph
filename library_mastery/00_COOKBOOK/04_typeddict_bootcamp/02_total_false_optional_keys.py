from pathlib import Path
import sys
from typing import TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _utils import show, step, title


title("02 — total=False makes keys optional")

step("1) total=False means 'keys may be missing'")
class PartialUser(TypedDict, total=False):
    id: str
    age: int
    nickname: str


step("2) Input can be partial")
u1: PartialUser = {"id": "u1"}
u2: PartialUser = {"id": "u2", "age": 40}
show("u1 (input)", u1)
show("u2 (input)", u2)


step("3) Inside a function, use .get(...) for optional keys")
def describe(u: PartialUser) -> dict:
    print("Inside describe(...)")
    show("u (inside)", u)
    return {
        "id": u.get("id"),
        "age": u.get("age"),
        "nickname": u.get("nickname", "<none>"),
    }


show("describe(u1)", describe(u1))
show("describe(u2)", describe(u2))

