from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace


def main() -> None:
    bootstrap_langgraph_namespace()

    from langgraph.channels import EphemeralValue, LastValue
    from langgraph.pregel import NodeBuilder, Pregel

    # node1: reads input channel "a", writes "b"
    node1 = NodeBuilder().subscribe_only("a").do(lambda x: x + x).write_to("b")

    # node2: reads dict of subscribed values (subscribe_to vs subscribe_only),
    # then writes to "c"
    node2 = NodeBuilder().subscribe_to("b").do(lambda x: x["b"] + x["b"]).write_to("c")

    app = Pregel(
        nodes={"node1": node1, "node2": node2},
        channels={
            "a": EphemeralValue(str),
            "b": LastValue(str),  # allows exactly one write per step
            "c": EphemeralValue(str),
        },
        input_channels=["a"],
        output_channels=["b", "c"],
    )

    out = app.invoke({"a": "foo"})
    print(out)


if __name__ == "__main__":
    main()
