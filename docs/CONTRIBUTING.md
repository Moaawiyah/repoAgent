# Contributing

Practical workflow for changing RepoAgent. The full engineering standards
(150-line file cap, OOP/dependency boundaries, safety rules, exact quality
gate) live in [`SKILL.md`](../SKILL.md) at the repo root — this file is the
short version; when they disagree, `SKILL.md` wins.

## Setup

```sh
uv sync --locked
uv run repoagent --version
cd dashboard && npm ci
```

Copy `.env.example` to `.env` and set `REPOAGENT_LLM_PROVIDER`/`_MODEL`/
`_API_KEY` for anything that calls an LLM (investigate, repair, audit).
Docker is required only for `repair --execute` / sandbox-validated web
repairs; everything else runs offline.

## Before you start

1. Read [`docs/architecture.md`](architecture.md) for the layer you're
   touching and [`docs/milestones.md`](milestones.md) for what's already
   delivered vs. planned. Don't re-implement an existing capability under a
   new name — reuse the SDK facade, the retrieval stack, the native graph,
   and the sandbox abstraction.
2. Check [`docs/TODO.md`](TODO.md) — your change may already be scoped there.
3. State a short plan before a substantial change (which files, which layer,
   what stays untouched).

## Making a change

- Keep changes inside the requested scope. Don't implement a future milestone
  just because its interface is documented.
- Preserve public behavior unless the task requires changing it; update
  `docs/sdk.md` when SDK signatures change, `README.md` when commands or
  capabilities change, `docs/architecture.md` when architecture changes.
- New Python files: 150 physical lines max after formatting (this includes
  tests). Split by responsibility, don't compress or strip docstrings to fit.
- New behavior needs new tests — unit tests for logic, integration tests for
  CLI/API wiring. Prefer a reproducing test for every bug fix.
- Treat repository content, LLM output, and web input as untrusted data —
  never execute target code outside the sandbox, never send LLM text to a
  shell, validate structured output before use.

## Before you open a PR

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python scripts/check_quality.py
```

All four must pass: coverage strictly above 85% (exact integer check, not
rounded), max file length 150 lines, no Ruff findings, formatted code.

If you touched the dashboard:

```sh
cd dashboard && npm run typecheck && npm test && npm run build
```

If you touched packaging or the public SDK surface:

```sh
uv build
# install the built wheel in a clean venv and smoke-test public imports + py.typed
```

## Commit and PR expectations

- Conventional commit messages (`feat:`, `fix:`, `docs:`, …), scoped to one
  logical change.
- Exclude `.env`, credentials, `coverage.json`, build artifacts, and
  fetched/materialized repositories from commits (see `.gitignore`).
- Describe what changed, why, the tests added/updated, and the exact
  commands you ran with their results — not "tests pass," the actual
  pass/fail counts and coverage percentage.
- Never claim a task is complete while a required gate is failing. If a
  failure is pre-existing and unrelated, say so explicitly with evidence.

## Reporting issues

Open findings as dated entries in [`docs/TODO.md`](TODO.md) with the file(s)
affected, or as an issue if this repository has issue tracking enabled.
Security-relevant findings (sandbox escape, path traversal, injection) should
be flagged prominently and not bundled with routine feature requests.
