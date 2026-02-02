from pprint import pformat


def title(text: str) -> None:
    line = "=" * len(text)
    print("\n" + line)
    print(text)
    print(line)


def show(label: str, value: object) -> None:
    print(f"\n{label}:")
    print(pformat(value, width=100))


def step(text: str) -> None:
    print("\n--- " + text)

