from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from langgraph.store.memory import InMemoryStore

    store = InMemoryStore()

    banner("put/get")
    store.put(("users",), "u1", {"name": "Ada", "role": "admin"})
    store.put(("users",), "u2", {"name": "Bob", "role": "user"})
    show("u1", store.get(("users",), "u1").value)  # type: ignore[union-attr]
    show("u2", store.get(("users",), "u2").value)  # type: ignore[union-attr]

    banner("search(filter=...) (no embeddings needed)")
    admins = store.search(("users",), filter={"role": "admin"})
    show("admins", [item.value for item in admins])

    banner("list_namespaces")
    show("namespaces", list(store.list_namespaces(prefix=("users",))))


if __name__ == "__main__":
    main()

