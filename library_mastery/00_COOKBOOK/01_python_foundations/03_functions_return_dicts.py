from pathlib import Path
import sys

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _utils import show, step, title


title("03 — Functions that return dicts (this is the LangGraph mental model)")

step("1) Think of 'state' as a dict")
state = {"count": 0, "log": []}
show("state (input)", state)


step("2) A 'node' is usually just a function(state) -> dict update")
def increment_count(current_state: dict) -> dict:
    print("Inside increment_count(...)")
    show("current_state (inside)", current_state)
    next_count = current_state["count"] + 1
    return {"count": next_count, "log": current_state["log"] + [f"count={next_count}"]}


step("3) Apply the node function")
update = increment_count(state)
show("update (returned)", update)

step("4) Merge the update into the state (simple merge)")
state = {**state, **update}
show("state (output)", state)

