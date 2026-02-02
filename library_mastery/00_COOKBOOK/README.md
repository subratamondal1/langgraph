# LangGraph Bootcamp Cookbook (Start From Zero)

You said you want to learn **how to use LangGraph like a developer** (“drive the car”), starting from **absolute basics**, with **simple files** you can read top → bottom and run to see **input → inside → output**.

This folder is that bootcamp.

## How to use this bootcamp

1) Go **in order** (folders are numbered).
2) In each folder, run the scripts in order (files are numbered).
3) Read the code top → bottom. Every script prints:
   - what the input looks like
   - what the data looks like inside the function/node
   - what the output looks like

## Run

From repo root:

```bash
./.venv/bin/python library_mastery/00_COOKBOOK/01_python_foundations/01_values_and_print.py
```

## Notes

- This repo is a monorepo. `langgraph` is a namespace package built from `libs/*`.
  Scripts that use LangGraph call `bootstrap_langgraph_namespace()` (defined in `library_mastery/00_COOKBOOK/_bootstrap.py`)
  so you can run examples without installing packages.
- Generated SQLite files go into `library_mastery/00_COOKBOOK/_scratch/` (ignored by git).

