from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    serde = JsonPlusSerializer()

    obj = {
        "user": {"id": "u1", "tags": ["founder", "debugger"]},
        "numbers": [1, 2, 3],
        "nested": {"ok": True, "none": None},
    }

    banner("serialize")
    enc, blob = serde.dumps_typed(obj)
    show("encoding", enc)
    show("bytes_len", len(blob))

    banner("deserialize")
    decoded = serde.loads_typed((enc, blob))
    show("decoded", decoded)


if __name__ == "__main__":
    main()

