from pathlib import Path
import sys

# In this repo we keep helpers in `library_mastery/00_COOKBOOK/_bootstrap.py`.
# When you run THIS file directly, Python's import search path (sys.path)
# does NOT automatically include that parent folder.
COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("03 — sys.path and why we bootstrap LangGraph in a monorepo")

step("1) sys.path is the list of folders Python searches for imports")
show("sys.path[0:5]", sys.path[0:5])

step("2) For LangGraph, we add libs/* folders to sys.path")
repo_root = bootstrap_langgraph_namespace()
show("repo_root", str(repo_root))

step("3) Now we can import langgraph from this repo checkout")
import langgraph

show("langgraph module", str(langgraph))

