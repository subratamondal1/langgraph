# 14 — Final Project (single-file): Durable Deep Research Agent (SQLite)

This is the “end goal” you asked for:
- a single Python file
- readable top → bottom
- uses LangGraph to run a research workflow
- uses SQLite for:
  - checkpointing (resume by `thread_id`)
  - store (persist notes)
  - cache (avoid repeated “search” work)

Run (pause on interrupt, then resume):

```bash
./.venv/bin/python library_mastery/00_COOKBOOK/14_final_project/00_deep_research_agent_sqlite.py "LangGraph"
./.venv/bin/python library_mastery/00_COOKBOOK/14_final_project/00_deep_research_agent_sqlite.py --resume yes
```

Run fully automatically (auto-resume):

```bash
./.venv/bin/python library_mastery/00_COOKBOOK/14_final_project/00_deep_research_agent_sqlite.py --auto "LangGraph"
```

All SQLite files are written to `library_mastery/00_COOKBOOK/_scratch/` (git-ignored).

