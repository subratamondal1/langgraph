from dataclasses import dataclass
from pathlib import Path
import sys

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _utils import show, step, title


title("03 — dataclass (we'll use this later as graph Context)")

step("1) A dataclass is a simple 'data container' class")
@dataclass
class UserContext:
    user_id: str
    org_id: str


step("2) Create one (input)")
ctx = UserContext(user_id="u1", org_id="orgA")
show("ctx", ctx)

step("3) Access fields (inside)")
show("ctx.user_id", ctx.user_id)
show("ctx.org_id", ctx.org_id)

