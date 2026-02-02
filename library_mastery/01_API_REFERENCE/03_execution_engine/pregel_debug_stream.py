from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, print_graph, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from langgraph.channels import EphemeralValue, LastValue, Topic
    from langgraph.pregel import NodeBuilder, Pregel

    # node1: input -> double -> b + c
    node1 = (
        NodeBuilder()
        .subscribe_only("a")
        .do(lambda x: x + x)
        .write_to("b", "c")
    )

    # node2: reacts to b -> double -> c
    node2 = NodeBuilder().subscribe_only("b").do(lambda x: x + x).write_to("c")

    app = Pregel(
        nodes={"node1": node1.build(), "node2": node2.build()},
        channels={
            "a": EphemeralValue(str),
            "b": LastValue(str),
            "c": Topic(str, accumulate=True),
        },
        # Use a single input channel name (str) so `get_graph()` can simulate input.
        # (With a list input_channels, draw_graph currently simulates an empty dict input.)
        input_channels="a",
        output_channels=["b", "c"],
    )

    banner("ASCII Graph")
    print_graph(app.get_graph())

    banner("invoke() output")
    out = app.invoke("foo")
    show("output", out)

    banner("stream(mode='tasks')")
    for chunk in app.stream("bar", stream_mode="tasks"):
        print(chunk)

    banner("stream(mode='debug')")
    for chunk in app.stream("baz", stream_mode="debug"):
        print(chunk)


if __name__ == "__main__":
    main()
