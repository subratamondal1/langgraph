from pathlib import Path
import sys

# Make `from _utils import ...` work when running this file directly.
COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _utils import show, step, title


title("01 — Python values + printing (input → inside → output)")

step("1) Create some input data (a dict)")
input_data = {"name": "Ada", "age": 30}
show("input_data", input_data)


step("2) Define a function that takes input and returns output")
def make_greeting(data: dict) -> dict:
    print("Inside make_greeting(...)")
    show("data (inside)", data)
    return {"greeting": f"Hello {data['name']}!", "age_next_year": data["age"] + 1}


step("3) Call the function")
output = make_greeting(input_data)

step("4) See the output")
show("output", output)

