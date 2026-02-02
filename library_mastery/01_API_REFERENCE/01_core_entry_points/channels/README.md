# `langgraph.channels` (Channel Primitives)

## What you import from here

Channels are the **state storage + merge rules** used by `Pregel`.

Public exports:
- Base: `BaseChannel`
- Value channels: `AnyValue`, `LastValue`, `LastValueAfterFinish`, `UntrackedValue`, `EphemeralValue`
- Reducer channel: `BinaryOperatorAggregate`
- Barrier channels: `NamedBarrierValue`, `NamedBarrierValueAfterFinish`
- Topic channel: `Topic`

## The core mental model

Every channel defines:
- a **stored value type**
- an **update type**
- an `update(updates: Sequence[Update]) -> bool` method that merges all writes from a step

Important consequence:
- Many channels enforce “**only one write per step**” (e.g. `LastValue`), which is why concurrent updates without reducers can fail.

## Example

- `channel_primitives.py` demonstrates common behaviors (single writer, accumulation, barriers).

