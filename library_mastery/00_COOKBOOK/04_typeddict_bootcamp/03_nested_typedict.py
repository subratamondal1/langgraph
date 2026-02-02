from pathlib import Path
import sys
from typing import TypedDict

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _utils import show, step, title


title("03 — Nested TypedDict (dict inside dict)")

step("1) Define nested shapes")
class Address(TypedDict):
    city: str
    country: str


class Person(TypedDict):
    name: str
    address: Address


step("2) Input")
person: Person = {"name": "Ada", "address": {"city": "London", "country": "UK"}}
show("person (input)", person)


step("3) Inside: access nested dicts")
def format_person(p: Person) -> dict:
    print("Inside format_person(...)")
    show("p (inside)", p)
    addr = p["address"]
    return {"line": f"{p['name']} — {addr['city']}, {addr['country']}"}


out = format_person(person)
show("out (output)", out)

