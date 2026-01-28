# 03 — DEVELOPER HANDBOOK

This is a practical “how to work here” guide for the LangGraph monorepo.

---

## 1) THE MECHANICS (Build & Run)

### Repo shape (what you’re actually running)

- This is a **monorepo**. Each publishable library lives in `libs/<name>/`.
- There is no single application entrypoint. You “run” the repo by:
  - running **tests** in a target library,
  - running the **CLI** (`langgraph`) from `libs/cli`,
  - running **examples** (Python notebooks/scripts under `examples/`),
  - running a **local API server** via `langgraph dev` / `langgraph up` (server runtime is pulled in as dependencies).

### Prereqs

- **Python:** `>=3.10` is supported; **3.11+ is recommended** (async context propagation is better).
- **uv:** used everywhere (`uv sync`, `uv run`, `uv lock`).
- **Docker:** required for several integration-heavy test suites (Postgres/Redis via `docker compose`).
- **Node.js (optional):**
  - only needed for JS example templates under `libs/cli/js-*`,
  - and for a few dev conveniences (e.g., `npx concurrently` used by `libs/langgraph/Makefile:test_watch_all`).

### Local setup options

#### Option A (recommended): work per-library

Pick the library you’re changing and create its environment from its pinned `uv.lock`.

Examples:

- Core engine:
  - `cd libs/langgraph`
  - `uv sync --frozen --group dev`
- CLI:
  - `cd libs/cli`
  - `uv sync --frozen --group dev`
- SDK:
  - `cd libs/sdk-py`
  - `uv sync --frozen --group dev`

Then run commands via `uv run ...` (so you use that library’s venv and pinned deps).

#### Option B (quick bootstrap): root “editable installs”

At repo root:

- `make install`

This creates a venv and installs each `libs/*` Python package editable. It’s fine for quick import-time development, but it does **not** replace per-library `uv sync` when you need the right lint/test dependency sets.

### How to run things locally (common flows)

#### Run the core library tests (the closest thing to “run the app”)

- `cd libs/langgraph`
- `make test`

Notes:

- This suite tries to start services via Docker (`docker compose`) and also starts a local dev server (see `make start-dev-server`).
- If you don’t have Docker available, many tests can be skipped by setting `NO_DOCKER=true`:
  - `NO_DOCKER=true make test`

#### Run the CLI locally

- `cd libs/cli`
- `uv run langgraph --help`

Useful commands:

- `uv run langgraph new ...`
- `uv run langgraph dev -c path/to/langgraph.json --no-browser`
- `uv run langgraph up -c path/to/langgraph.json`

#### Run JS example templates (optional)

JS templates are under `libs/cli/js-examples/` and `libs/cli/js-monorepo-example/`.

- They use Yarn Classic per `packageManager: yarn@1.22.22`.
- Example:
  - `cd libs/cli/js-examples`
  - `yarn install`
  - `yarn build` / `yarn test`

### Hidden env vars / secrets you will trip over

#### API keys (examples + SDK)

- Example `.env` templates exist:
  - `libs/cli/examples/.env.example` includes placeholders for:
    - `OPENAI_API_KEY`
    - `ANTHROPIC_API_KEY`
    - `TAVILY_API_KEY`
  - `libs/cli/js-examples/.env.example` is a “copy me” stub.

SDK auto-load precedence (if you don’t explicitly pass an API key):

- `LANGGRAPH_API_KEY` → `LANGSMITH_API_KEY` → `LANGCHAIN_API_KEY`

#### CLI deployment keys

The `langgraph up` command explicitly warns about:

- `LANGSMITH_API_KEY` (local dev with LangSmith Deployment access)
- `LANGGRAPH_CLOUD_LICENSE_KEY` (production licensing)

#### Dev/test toggles

- `NO_DOCKER=true` — skip Docker-dependent tests (used by `libs/langgraph/tests/conftest.py`).
- `LANGGRAPH_TEST_FAST=1` — “fast mode” for `libs/prebuilt` tests.
- `POSTGRES_VERSION` / `POSTGRES_VERSIONS` — drive Postgres docker image selection for checkpoint-postgres tests.
- `LANGGRAPH_CLI_NO_ANALYTICS=1` — disable CLI analytics/telemetry.
- `LOG_LEVEL=warning` — used by `libs/langgraph/Makefile` when starting the dev server.

#### Port collisions to watch for

Docker compose in tests binds ports that may conflict with local services:

- Redis: `6379`
- Postgres for langgraph/prebuilt tests: `5442`
- Postgres for checkpoint-postgres tests: `5441`

### Debugging: how to attach a debugger to this stack

#### Debugging core engine logic (fastest loop)

- Use pytest with a debugger:
  - `cd libs/langgraph`
  - `TEST=tests/test_pregel.py make test` (narrow scope)
  - or: `uv run pytest -k <pattern> -s --pdb`

Also useful for engine-level introspection:

- Run graphs with `debug=True` and/or stream modes that include `"debug"`/`"tasks"`/`"checkpoints"` to see step-by-step behavior.

#### Debugging the CLI

- Run as a module so you can breakpoint inside:
  - `cd libs/cli`
  - `uv run python -m langgraph_cli --help`

For the API server in dev mode:

- `langgraph dev` supports `--debug-port` (remote debugging). Start it with a debug port, then attach from your IDE (VSCode/PyCharm) to that port.

#### Debugging Docker-based runs

- Use `langgraph up --verbose` and inspect container logs:
  - `docker compose logs -f`
- If you need interactive debugging inside a container, you’ll typically inject `debugpy` and expose a port (the CLI supports debugger options like `--debugger-port` for `langgraph up`).

---

## 2) THE SAFETY NET (Testing Strategy)

### Where tests live

Each library owns its own tests:

- `libs/langgraph/tests/`
- `libs/prebuilt/tests/`
- `libs/checkpoint/tests/`
- `libs/checkpoint-sqlite/tests/`
- `libs/checkpoint-postgres/tests/`
- `libs/sdk-py/tests/`
- `libs/cli/tests/` (unit + integration split)

### Exact commands to run tests

Repo-wide (runs each library’s `make test`):

- `make test`

Per library:

- `cd libs/<lib> && make test`

Run a single file / subset (supported across libraries):

- `cd libs/<lib>`
- `TEST=path/to/test_file.py make test`
- `TEST='-k pattern -vv' make test` (pytest args can be passed via `TEST`)

### Unit vs integration: what’s actually happening

- **Unit-heavy / fast-ish:**
  - `libs/sdk-py/tests/` (client/schema/auth/encryption logic)
  - `libs/checkpoint/tests/` (checkpoint + serde; Redis cache tests skip if no Redis on `localhost:6379`)
  - `libs/checkpoint-sqlite/tests/` (SQLite; no Docker required)
- **Integration-heavy / slow-ish (Docker required):**
  - `libs/langgraph/tests/` (starts Postgres+Redis via docker compose and starts a dev server)
  - `libs/prebuilt/tests/` (docker compose Postgres+Redis)
  - `libs/checkpoint-postgres/tests/` (docker Postgres; loops versions by default)
  - `libs/cli/tests/integration_tests/` (exercises CLI workflows; may invoke Docker paths)

### Coverage

- Coverage tooling is explicitly wired for `libs/langgraph`:
  - `cd libs/langgraph && make coverage`
- Other libraries rely on pytest pass/fail + lint/typecheck rather than explicit coverage targets.

### Gap analysis vs Hot Path (from Step 2)

Hot path modules were identified in:

- `libs/langgraph/langgraph/pregel/main.py`
- `libs/langgraph/langgraph/pregel/_loop.py`
- `libs/langgraph/langgraph/pregel/_algo.py`
- `libs/langgraph/langgraph/pregel/_runner.py`
- `libs/langgraph/langgraph/graph/state.py`

Are they covered by tests? **Yes.**

Evidence:

- `libs/langgraph/tests/test_algo.py` directly tests `prepare_next_tasks(...)` (core scheduling).
- `libs/langgraph/tests/test_pregel.py` imports `SyncPregelLoop` and `PregelRunner` and exercises compiled graphs heavily.

---

## 3) THE ARCHAEOLOGY (Git & People)

### Timeline: is it alive or a zombie?

This repo is **active**.

Recent signals from `git log` (dates are commit dates in this working copy):

- Latest commit: `2026-01-28`
- Recent releases:
  - `release: langgraph and prebuilt 1.0.7` on `2026-01-22`
  - `release(cli): 0.4.12` on `2026-01-23`

### People / bus factor (quick signal)

In the last ~200 commits, multiple humans contribute repeatedly (plus bots like Dependabot), suggesting this is not a single-maintainer “bus factor 1” project.

### Issue tracker / external references

- Primary coordination appears to be **GitHub PRs/issues** (commit messages include PR numbers; code contains links to GitHub issues).
  - Example references found:
    - `libs/langgraph/tests/test_large_cases.py` references a GitHub issue in a regression test docstring.
    - `libs/checkpoint-postgres/langgraph/store/postgres/base.py` references a pgvector GitHub issue in a comment.
- No strong evidence of Jira/Linear references in-tree (no `linear.app` / `jira.com` hits in a broad search).

