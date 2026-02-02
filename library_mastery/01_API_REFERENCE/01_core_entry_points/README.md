# Core Entry Points (Public Exports) — Hands-on Companion

This folder is a “learn-by-doing” companion to **Section 1** of `library_mastery/01_API_REFERENCE.md`.

## What “Core Entry Points” means

In this repo, `langgraph` is a **PEP 420 namespace package** built from multiple `libs/*` distributions. Practically, you don’t start with `import langgraph` and then discover everything from a single `__init__.py`.

Instead, you start from a small set of **stable import modules** (entry points) like:

- `langgraph.graph` (Graph API)
- `langgraph.func` (Functional API)
- `langgraph.pregel` (execution engine, advanced)
- `langgraph.types` / `langgraph.errors` / `langgraph.constants` (contracts + control plane)

Each entry point typically defines `__all__` so that “what’s public” is intentional.

## How to use this folder

Each subfolder maps 1:1 to an entry point module from Section 1:

- `graph/` → `langgraph.graph`
- `pregel/` → `langgraph.pregel`
- `func/` → `langgraph.func`
- `channels/` → `langgraph.channels`
- `runtime/` → `langgraph.runtime`
- `config/` → `langgraph.config`
- `types/` → `langgraph.types`
- `errors/` → `langgraph.errors`
- `constants/` → `langgraph.constants`
- `managed/` → `langgraph.managed`
- `prebuilt/` → `langgraph.prebuilt`

Each folder contains:
- `README.md` (the “why” + key mental models)
- One or more `*.py` scripts (the “how”)

## Cookbook

- `00_cookbook.py` is the “production-first” tour: minimal Graph API, Functional API, and ToolNode patterns.

## Running the scripts (repo checkout)

The scripts include a tiny `sys.path` bootstrap (via `library_mastery/01_API_REFERENCE/_bootstrap.py`) so they can be run from a repo checkout without installing packages.

From the repo root:

```bash
./.venv/bin/python library_mastery/01_API_REFERENCE/01_core_entry_points/graph/stategraph_basics.py
```
