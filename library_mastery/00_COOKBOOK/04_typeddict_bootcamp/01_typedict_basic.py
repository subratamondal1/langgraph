from pathlib import Path
import sys
from typing import TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _utils import show, step, title


title("01 — TypedDict basics (shape for dicts)")

step("1) Define a TypedDict (this describes the 'shape' of a dict)")
class User(TypedDict):
    id: str
    age: int


step("2) Input data that matches the shape")
user: User = {"id": "u1", "age": 30}
show("user (input)", user)


step("3) A function that expects a User")
def birthday(u: User) -> User:
    print("Inside birthday(...)")
    show("u (inside)", u)
    return {"id": u["id"], "age": u["age"] + 1}


step("4) Output data")
out = birthday(user)
show("out (output)", out)


step("5) Important: TypedDict is NOT runtime validation")
print("If you pass the wrong shape, Python may crash later, but TypedDict itself won't stop you.")

