from __future__ import annotations

from pathlib import Path
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage

    from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages

    banner("Append + auto-IDs")
    left = [HumanMessage(content="hi")]  # no id provided
    right = [AIMessage(content="hello")]  # no id provided
    out = add_messages(left, right)
    show("left", [(m.type, m.content, m.id) for m in left])
    show("right", [(m.type, m.content, m.id) for m in right])
    show("merged", [(m.type, m.content, m.id) for m in out])

    banner("Overwrite by ID")
    msg_id = out[0].id
    overwritten = add_messages(out, [HumanMessage(content="hi (edited)", id=msg_id)])
    show("before", [(m.type, m.content, m.id) for m in out])
    show("after", [(m.type, m.content, m.id) for m in overwritten])

    banner("Delete by ID")
    to_delete = overwritten[1].id
    deleted = add_messages(overwritten, [RemoveMessage(id=to_delete)])
    show("after delete", [(m.type, m.content, m.id) for m in deleted])

    banner("Delete all")
    deleted_all = add_messages(deleted, [RemoveMessage(id=REMOVE_ALL_MESSAGES)])
    show("after delete-all", [(m.type, m.content, m.id) for m in deleted_all])


if __name__ == "__main__":
    main()

