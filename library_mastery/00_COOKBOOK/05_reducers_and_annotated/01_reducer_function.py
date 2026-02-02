from pathlib import Path
import sys

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _utils import show, step, title


title("01 — Reducer function (merge two updates safely)")

step("1) Imagine two parts of your program both produce updates for the same key")
update_from_node_a = {"log": ["A: started"]}
update_from_node_b = {"log": ["B: processed"]}

show("update_from_node_a", update_from_node_a)
show("update_from_node_b", update_from_node_b)


step("2) Without a reducer, a simple dict merge will overwrite")
merged_bad = {**update_from_node_a, **update_from_node_b}
show("merged_bad", merged_bad)


step("3) A reducer is a function that merges values instead of overwriting")
def append(left: list[str], right: list[str] | None) -> list[str]:
    return left + (right or [])


merged_good = {"log": append(update_from_node_a["log"], update_from_node_b["log"])}
show("merged_good", merged_good)

print("\nThis exact idea is what LangGraph uses to merge state updates.")

