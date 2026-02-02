# 05 — Reducers + `Annotated` (the key LangGraph idea)

LangGraph state updates can happen from multiple nodes in the same step.
If two nodes write the same key, LangGraph needs a rule to **merge** them.

That merge rule is called a **reducer**, and it's usually attached like this:

```py
from typing import Annotated, TypedDict

def append(left: list[str], right: list[str] | None) -> list[str]:
    return left + (right or [])

class State(TypedDict):
    log: Annotated[list[str], append]
```

Run:

```bash
./.venv/bin/python library_mastery/00_COOKBOOK/05_reducers_and_annotated/01_reducer_function.py
./.venv/bin/python library_mastery/00_COOKBOOK/05_reducers_and_annotated/02_annotated_is_just_metadata.py
```

