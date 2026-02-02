from pathlib import Path
import sys

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _utils import show, step, title


title("02 — Lists + dicts (how data changes)")

step("1) Input: list of numbers")
nums = [1, 2, 3]
show("nums (input)", nums)

step("2) 'Inside': compute a transformed list")
doubled = []
for n in nums:
    doubled.append(n * 2)
show("doubled (inside)", doubled)

step("3) Output: store result in a dict")
output = {"original": nums, "doubled": doubled}
show("output", output)

