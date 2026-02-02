from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, print_graph, show


def recipe_pregel_app_with_streaming() -> None:
    from langgraph.channels import EphemeralValue, LastValue, Topic
    from langgraph.pregel import NodeBuilder, Pregel

    node1 = (
        NodeBuilder()
        .subscribe_only("a")
        .do(lambda x: x + x)
        .write_to("b", "c")
        .build()
    )
    node2 = (
        NodeBuilder()
        .subscribe_only("b")
        .do(lambda x: x + x)
        .write_to("c")
        .build()
    )

    app = Pregel(
        nodes={"node1": node1, "node2": node2},
        channels={
            "a": EphemeralValue(str),
            "b": LastValue(str),
            "c": Topic(str, accumulate=True),
        },
        input_channels="a",
        output_channels=["b", "c"],
    )

    banner("Pregel: visualize")
    print_graph(app.get_graph())

    banner("Pregel: invoke()")
    out = app.invoke("hi")
    show("output", out)

    banner("Pregel: stream(mode='tasks')")
    for chunk in app.stream("yo", stream_mode="tasks"):
        print(chunk)


def recipe_pregel_cycle_until_none() -> None:
    from langgraph.channels import EphemeralValue
    from langgraph.pregel import NodeBuilder, Pregel
    from langgraph.pregel._write import ChannelWriteEntry

    node = (
        NodeBuilder()
        .subscribe_only("value")
        .do(lambda x: x + x if len(x) < 10 else None)
        .write_to(ChannelWriteEntry(channel="value", skip_none=True))
        .build()
    )

    app = Pregel(
        nodes={"cycle": node},
        channels={"value": EphemeralValue(str)},
        input_channels="value",
        output_channels="value",
    )

    banner("Pregel: cycle until None (stream values per step)")
    for i, chunk in enumerate(app.stream("a", stream_mode="values"), start=1):
        print(f"step={i} value={chunk!r}")


def main() -> None:
    bootstrap_langgraph_namespace()
    recipe_pregel_app_with_streaming()
    recipe_pregel_cycle_until_none()


if __name__ == "__main__":
    main()

