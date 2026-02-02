from __future__ import annotations

from pprint import pformat


def banner(title: str) -> None:
    line = "=" * max(10, len(title))
    print(f"\n{line}\n{title}\n{line}")


def show(label: str, value: object) -> None:
    print(f"\n{label}:\n{pformat(value, width=100)}")


def print_graph(graph: object) -> None:
    """Best-effort graph printing.

    `langchain_core`'s ASCII rendering requires an optional dependency (`grandalf`).
    For a repo checkout (where we want examples to run everywhere), fall back to
    printing nodes/edges when the dependency isn't installed.
    """
    try:
        draw_ascii = getattr(graph, "draw_ascii")
        print(draw_ascii())
        return
    except ImportError as e:
        print(f"(graph ascii unavailable: {e})")
    except Exception as e:  # pragma: no cover
        print(f"(graph ascii failed: {type(e).__name__}: {e})")

    nodes = getattr(graph, "nodes", None)
    edges = getattr(graph, "edges", None)
    if isinstance(nodes, dict):
        print("nodes:", list(nodes.keys()))
    if isinstance(edges, list):
        print("edges:", [(e.source, e.target, e.data, e.conditional) for e in edges])
