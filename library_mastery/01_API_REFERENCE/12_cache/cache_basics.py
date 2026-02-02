from __future__ import annotations

from pathlib import Path
import sys
import time

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from langgraph.cache.memory import InMemoryCache

    cache = InMemoryCache()

    banner("set/get")
    # FullKey is (NamespaceTuple, key) at the public surface.
    cache.set({(("demo",), "k1"): ({"value": 123}, None)})
    show("get(k1)", cache.get([(("demo",), "k1")]))

    banner("ttl expiry")
    cache.set({(("demo",), "k2"): ({"value": "short-lived"}, 1)})
    show("immediate", cache.get([(("demo",), "k2")]))
    time.sleep(1.1)
    show("after sleep", cache.get([(("demo",), "k2")]))

    banner("clear namespace")
    cache.set({(("demo",), "k3"): ({"value": "persist"}, None)})
    show("before clear", cache.get([(("demo",), "k3")]))
    cache.clear([("demo",)])
    show("after clear", cache.get([(("demo",), "k3")]))


if __name__ == "__main__":
    main()

