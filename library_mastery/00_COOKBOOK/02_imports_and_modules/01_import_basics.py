from pathlib import Path
import sys

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _utils import show, step, title


title("01 — import basics")

step("1) Import a standard library module")
import math

show("math.pi", math.pi)
show("math.sqrt(9)", math.sqrt(9))

step("2) Import another standard module (pathlib)")
here = Path(__file__).resolve()
show("__file__", str(here))
show("parent folder", str(here.parent))

