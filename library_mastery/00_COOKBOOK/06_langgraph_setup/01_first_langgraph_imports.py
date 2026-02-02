from pathlib import Path
import sys

COOKBOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COOKBOOK_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import show, step, title


title("01 — First LangGraph imports")

step("1) Bootstrap the monorepo so `import langgraph...` works")
bootstrap_langgraph_namespace()

step("2) Import the core Graph API entry point")
from langgraph.graph import END, START, StateGraph

show("START", START)
show("END", END)
show("StateGraph", StateGraph)

