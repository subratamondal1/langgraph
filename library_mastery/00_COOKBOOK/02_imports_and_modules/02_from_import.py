from pathlib import Path
import sys

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _utils import show, step, title


title("02 — from ... import ...")

step("1) from math import sqrt")
from math import sqrt

show("sqrt(16)", sqrt(16))

step("2) from datetime import datetime")
from datetime import datetime

now = datetime.utcnow()
show("now (utc)", now.isoformat())

