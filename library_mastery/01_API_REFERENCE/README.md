# Companion Materials for `01_API_REFERENCE.md`

This folder contains **hands-on, runnable examples** and **modular explanations** that correspond to the API surfaces documented in `library_mastery/01_API_REFERENCE.md`.

Each top-level folder maps to a numbered section in the reference (Sections **1–14**):

- `01_core_entry_points/` — Core Entry Points (Public Exports)
- `02_graph_construction/` — Graph Construction
- `03_execution_engine/` — Execution Engine (Pregel)
- `04_functional_api/` — Functional API
- `05_runtime_introspection/` — Runtime & In-Graph Introspection
- `06_channels/` — Channels
- `07_types_and_contracts/` — Control Plane & Data Contracts
- `08_errors_and_constants/` — Errors & Constants
- `09_managed_values/` — Managed Values
- `10_checkpointing/` — Persistence: Checkpointing
- `11_store/` — Persistence: Store
- `12_cache/` — Persistence: Cache
- `13_prebuilt_tooling/` — Prebuilt Tooling
- `14_serde_encryption/` — Serialization & Encryption

## Start With The Cookbooks

Each section folder contains a `00_cookbook.py` “production-first” tour you can run in order:

```bash
./.venv/bin/python library_mastery/01_API_REFERENCE/01_core_entry_points/00_cookbook.py
./.venv/bin/python library_mastery/01_API_REFERENCE/02_graph_construction/00_cookbook.py
# ...
```

## Run Any Example

Use the repo virtualenv (recommended):

```bash
./.venv/bin/python library_mastery/01_API_REFERENCE/02_graph_construction/build_visualize_and_stream.py
```
