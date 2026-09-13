# RepoAgent

An independent repository engineering platform. **M1 foundation is implemented.**
Repository ingestion, retrieval, model calls, patch generation, sandbox execution,
and benchmarks are planned capabilities, not working features in this release.

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). Install dependencies:

```sh
uv sync --locked
uv run repoagent --help
uv run repoagent --version
```

Runtime and tests need no API keys, Docker daemon, or network after installation.

## Current behavior

```sh
uv run repoagent --data-dir .repoagent analyze https://github.com/Moaawiyah/repoAgent.git --json
uv run repoagent --data-dir .repoagent fix ./some-repository 'Login returns 500' --json
uv run repoagent --data-dir .repoagent benchmark synthetic --json
uv run repoagent --data-dir .repoagent tasks show TASK_ID --json
uv run repoagent --data-dir .repoagent tasks events TASK_ID --json
```

`index`, `analyze`, `ask`, `fix`, `test`, and `benchmark` validate input and record a
**blocked** task with a `capability_unavailable` event. They exit with code **3**.
This is expected M1 behavior, not evidence of an analysis or attempted repair.
Task inspection works across CLI invocations. JSON is written to stdout; logs
and errors go to stderr. Global options precede the command.

Exit codes: 0 success; 1 operational failure; 2 invalid input; 3 unavailable capability.
Accepted benchmark names: `synthetic`, `bugsinpy`, `swe-bench`, `swe-bench-verified`.
Local input must be an existing directory. Public GitHub URL syntax is validated;
remote existence and visibility are not checked until ingestion. Issue arguments
are inert natural-language text in M1; GitHub issue fetching is not implemented.

## Python SDK

The same application is available as an object-oriented, in-process SDK:

```python
from pathlib import Path
from repoagent import RepoAgent, Settings, TaskStatus

client = RepoAgent(settings=Settings(data_dir=Path(".repoagent")))
task = client.analyze("https://github.com/Moaawiyah/repoAgent.git", commit="main")
assert task.status is TaskStatus.BLOCKED  # M1 does not analyze repositories yet
print(task.message)
print(client.get_task(task.id))
print(client.task_events(task.id))
```

Methods: `index`, `analyze`, `ask`, `fix`, `test`, `benchmark`, `submit`,
`get_task`, and `task_events`. All return typed Pydantic records, with UUIDs,
enums and timestamps intact. Use `model_dump(mode="json")` for JSON-ready data.

Construction is lazy; storage is opened on the first valid operation. The SDK
does not print, terminate the process, or install logging handlers. SQLite owns
connections per operation, so the client does not need a `close()` call. The CLI
uses this SDK and provides its own formatting, logging and exit codes.

For custom storage, pass `RepoAgent(store=your_task_store)` using the exported
`TaskStore` protocol. This bypasses default SQLite and environment configuration.
No subclass of `RepoAgent` is required. See [SDK contracts](docs/sdk.md) for input,
error and extension behavior.

## Configuration and data

Settings use the `REPOAGENT_` prefix; see `.env.example`. Data defaults to
`~/.repoagent/tasks.sqlite3`. `--data-dir` overrides the environment. Dotenv files
are read only with an explicit `--env-file PATH`; process environment values take
precedence over dotenv values. Retry count, context budget, and execution timeout
are validated future policy settings and **inactive in M1**.

Task records persist the supplied repository and question/issue locally. Logs
contain allowlisted metadata only, not issue text or repository content. Treat the
application data directory as private; it is not encrypted. Do not supply secrets
as issue text. Help and version do not create storage or access target repositories.

## Validation

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python scripts/check_quality.py
uv build
```

Pytest produces fresh statement coverage for the package and quality helper. The
quality helper checks complete production-file coverage data, requires coverage
strictly above 85%, and enforces at most 150 physical lines per Python file,
including tests. CI repeats validation and a wheel smoke test on Python 3.12/3.13.

## Architecture and next step

Source modules live directly in `src/` (for example, `src/sdk/` and
`src/domain/`). Packaging maps that directory to the public `repoagent` name,
so SDK imports and CLI commands remain unchanged.

See [architecture](docs/architecture.md) for boundaries, storage contracts, legacy
reuse decisions and safety constraints; see [milestones](docs/milestones.md) for
the complete roadmap and milestone acceptance criteria.

Next: **M2 — isolated repository snapshots and deterministic Python AST/chunk
extraction.** The original target repository must never be modified directly.
