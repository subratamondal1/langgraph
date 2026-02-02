from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner


def main() -> None:
    bootstrap_langgraph_namespace()

    from langgraph.channels import EphemeralValue
    from langgraph.pregel import NodeBuilder, Pregel
    from langgraph.pregel._write import ChannelWriteEntry

    banner("Cycle until None")

    # A single node that writes back into the same channel it reads.
    # Each step doubles the string until it would be length >= 10, then returns None.
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
        input_channels=["value"],
        output_channels=["value"],
    )

    # `values` mode shows the output channels after each step.
    for i, chunk in enumerate(app.stream({"value": "a"}, stream_mode="values"), start=1):
        print(f"step {i}:", chunk)


if __name__ == "__main__":
    main()

