from __future__ import annotations

from pprint import pformat


def banner(title: str) -> None:
    line = "=" * max(10, len(title))
    print(f"\n{line}\n{title}\n{line}")


def show(label: str, value: object) -> None:
    print(f"\n{label}:\n{pformat(value, width=100)}")

