# RepoAgent detailed usage guide

Per-milestone reference moved from the README during M8. The README is the
project overview; this guide keeps the detailed command behavior.


An independent repository engineering platform. M1–M4 provide static analysis,
structure-aware retrieval, and a code knowledge graph. **M5 adds a read-only,
LangGraph-powered Investigator with Groq and OpenAI provider adapters.**

**M6 proposes and statically reviews patches. M7 (`repair --execute`) applies an
approved patch only to a disposable copy inside a hardened Docker sandbox, runs
detected validation, analyzes failures, and retries within strict bounds. The
original repository is never modified.**

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). Install dependencies:

```sh
uv sync --locked
uv run repoagent --help
uv run repoagent --version
```

Analysis, retrieval, and automated tests run offline after installation. Live
investigation requires a configured provider and API key. Docker is required only
for `repair --execute` (M7); nothing else executes target code.

## Analyzing repositories (M2)

```sh
uv run repoagent analyze ./some-python-project
uv run repoagent analyze ./some-python-project --json
```

`analyze` accepts a local directory, validates it (existing, a directory,
readable), and performs static analysis only — target code is never imported
or executed. Extracted information:

- Python modules with docstrings and line ranges.
- Classes with base classes, decorators, docstrings, and line ranges.
- Functions, methods, and async functions with typed parameters
  (name, annotation, default, kind), return annotations, docstrings, and
  line ranges.
- Imports classified conservatively as repository-internal, standard
  library, or external.
- Relationships: imports, inheritance, containment, definitions.
- Repository summary: file/module/class/function/method counts, detected
  tests and configuration files, and per-file analysis errors.

Discovery skips vendored/ignored directories, honors `.gitignore`, and never
follows symlinks outside the repository. One malformed file is recorded as a
per-file error and does not abort the analysis. Results are deterministic.

## Indexing and searching (M3)

```sh
uv run repoagent index ./some-python-project
uv run repoagent search ./some-python-project "Where is authentication handled?"
uv run repoagent search ./some-python-project "authentication" --strategy bm25 --top-k 5
uv run repoagent search ./some-python-project "authentication" --strategy vector
uv run repoagent search ./some-python-project "authentication" --strategy hybrid --rerank
uv run repoagent search ./some-python-project "authentication" --json
```

`index` analyzes a repository (reusing M2), splits it into structure-aware
chunks aligned with functions, methods, classes, and module-level code, embeds
each chunk once, and persists the index under the data directory. Chunk IDs
are deterministic (`repository + file + qualified symbol + source hash`), so
unchanged code keeps its identity.

`search` retrieves the most relevant code with full provenance (file, symbol,
line range, source preview) rather than dumping whole files. Strategies:
`bm25` (Okapi BM25 with identifier-aware tokenization that splits
snake_case/CamelCase while preserving exact identifiers), `vector` (embedding
similarity), and `hybrid` (default; Reciprocal Rank Fusion of both, never
mixing raw score scales). `--rerank` optionally applies a deterministic
keyword-overlap reranker. JSON output is machine-readable; logs never mix
into it.

## Retrieval evaluation (LLM-free)

```sh
uv run repoagent evaluate ./some-python-project \
  --cases cases.json --top-k 5
uv run repoagent evaluate ./some-python-project \
  --cases cases.json --strategy hybrid_graph --json
```

`evaluate` runs real searches per strategy against labeled cases (query +
expected files/symbols) and reports Recall@K, MRR, HitRate@K, and Precision@K
computed from actual retrieval results — nothing is hardcoded. Strategies
compared: `bm25`, `vector`, `hybrid`, and `hybrid_graph`. See
`tests/fixtures/rag_cases.json` for the case format.

## Code knowledge graph and Obsidian export (M4)

```sh
uv run repoagent graph ./some-python-project
uv run repoagent graph ./some-python-project \
  --symbol "auth.service.AuthService.authenticate"
uv run repoagent graph ./some-python-project --json
uv run repoagent export-obsidian ./some-python-project ./repoagent-vault
```

The graph is built statically from M2 analysis — target code is never
executed:

- **Node types:** module, class, function, method. Node identity is the
  stable qualified name; nodes link to chunk IDs for retrieval.
- **Edge types:** DEFINES (module→symbol), CONTAINS (class→method),
  IMPORTS (module→module, internal only), INHERITS (class→base, unresolved
  bases kept marked rather than invented), CALLS (conservatively resolved).
- **Call resolution** is explicit about certainty: `self.method()` resolves
  against the caller's class; bare names resolve via the same module or a
  unique repo-wide name; dotted calls resolve by unique qualified suffix;
  anything else stays unresolved or partial (marked `resolved: false`) —
  never guessed.
- **Traversal is bounded** (max depth, max nodes, edge-type filters) and
  cycle-safe, recording graph distance and the full relationship path.
- `repoagent graph --symbol` shows outgoing/incoming/parent relationships;
  `--json` emits the deterministic machine-readable graph (nodes, edges,
  metadata) for future agents and tools.

`hybrid_graph` retrieval uses the hybrid ranking as seeds, expands along the
graph with bounded traversal, scores candidates by seed rank × distance
decay × relationship weight, and fuses seed and graph rankings with the same
RRF implementation — every result carries structural evidence (lexical rank,
vector rank, graph distance, relationship path).

The Obsidian exporter writes the graph as a deterministic Markdown vault
(`Repository.md`, plus `Modules/`, `Classes/`, `Functions/`, `Methods/`
notes with wikilinks for real relationships, inline code for unresolved
ones, and injection-safe source fences). It never deletes files and requires
`--overwrite` to export into a non-empty directory. Obsidian itself is never
required.

### `graphify`: graph.json and Obsidian from one build

```sh
uv run repoagent graphify ./some-python-project --artifacts artifacts
uv run repoagent graphify ./some-python-project \
  --output artifacts/graph.json \
  --obsidian artifacts/vault
uv run repoagent graphify ./some-python-project --json
```

`graphify` analyzes and builds the graph exactly once, then writes whichever
outputs you ask for: `--output` persists a versioned `graph.json`
(`schema_version`, `repository`, `nodes`, `edges`, and `metadata` —
file/symbol/relationship counts), and `--obsidian` writes the same vault
`export-obsidian` produces. `--artifacts <dir>` fills in whichever of those
two is left unset as `<dir>/<repository name>/{graph.json,vault}` — run it
repeatedly against different repositories and each gets its own
subdirectory instead of overwriting the last run's output; `--output`/
`--obsidian` still win when given explicitly. `graph.json` round-trips through
`repoagent.graph.serializer.read_graph_json` without re-analyzing the
repository, so it can seed the graph for other tools. `graph`,
`export-obsidian`, and `hybrid_graph` retrieval are unchanged and still work
standalone; `graphify` only adds a combined, persistent entry point around
the same `RepositoryGraphBuilder`/`GraphSnapshot`.

## Investigator (M5)

The Investigator runs a real stateful LangGraph workflow:

```text
analyze_issue → plan_search → retrieve → assess_evidence
                                ↑           │
                              refine ← need more evidence
                                ↑           │ enough evidence
                                └── weak ← hypothesize → evaluate → report
```

Conditional edges revisit retrieval when evidence is incomplete or a hypothesis
needs confirmation. Repeated queries are suppressed. Iteration, query, evidence,
tool-call, source-context, and model-output limits prevent runaway exploration.
Reports identify the termination reason, including provider failures and exhausted
budgets, instead of presenting incomplete investigations as successful.

Configure a private, ignored `.env` file (never place a key in `.env.example`):

```dotenv
REPOAGENT_LLM_PROVIDER=groq
REPOAGENT_LLM_MODEL=openai/gpt-oss-20b
REPOAGENT_LLM_API_KEY=your-private-key
```

Groq uses its official SDK and strict structured output. Free-tier availability
and quotas are account-dependent; a rate-limit error produces a partial
`provider_error` report. The OpenAI adapter uses its official OpenAI SDK and
also serves any OpenAI-compatible chat-completions endpoint by pairing
`REPOAGENT_LLM_PROVIDER=openai` with `REPOAGENT_LLM_BASE_URL` and a model that
endpoint serves — for example z.ai:

```dotenv
REPOAGENT_LLM_PROVIDER=openai
REPOAGENT_LLM_MODEL=glm-4.7-flashx
REPOAGENT_LLM_BASE_URL=https://api.z.ai/api/paas/v4/
REPOAGENT_LLM_API_KEY=your-private-key
```

There is no production fake-model fallback. Both adapters proactively throttle
requests to `REPOAGENT_LLM_TOKENS_PER_MINUTE`/`REPOAGENT_LLM_REQUESTS_PER_MINUTE`
when set, retry HTTP 429s within `REPOAGENT_LLM_RATE_LIMIT_RETRIES` (honoring
`retry-after`), and fail fast rather than sleep through a multi-minute quota
reset; each OpenAI-compatible base URL gets its own rate-limit budget.

```sh
uv run repoagent --data-dir /tmp/repoagent-data index ./tests/fixtures/auth_bug
uv run repoagent --env-file .env --data-dir /tmp/repoagent-data investigate \
  ./tests/fixtures/auth_bug "Users with uppercase emails cannot log in"
uv run repoagent --env-file .env --data-dir /tmp/repoagent-data investigate \
  ./tests/fixtures/auth_bug "Users with uppercase emails cannot log in" \
  --max-iterations 3 --top-k 5 --json
```

Only explicitly selected dotenv files are loaded. Keep the application data
folder outside the investigated repository. Index first, and re-index when the
repository changes: investigation reads stored source, not live files.

The automatic tool is `search_code`, through `SearchService` using `hybrid_graph`
(with hybrid fallback for indexes without a graph). The toolkit also supports
bounded `inspect_symbol`, `inspect_neighbors`, and `inspect_file` over the same
indexed data; these inspection helpers are not currently selected by graph nodes.
No agent tools execute commands, edit files, apply patches, run tests, or browse.

Evidence keeps repository/chunk identity, exact file/symbol/line provenance,
source snippets, retrieval source, and graph paths. Relevance is assessed before
hypotheses may cite it. Unknown citations and unsupported affected symbols cannot
become accepted hypotheses. Evaluation challenges alternatives and contradictions;
confidence is bounded and **uncalibrated**, not proof of correctness.

Issue text, source, and prior model output enter prompts as untrusted JSON data,
separate from system instructions. Schema validation and tool restrictions enforce
the boundary; prompt instructions cannot guarantee immunity to semantic deception.

JSON reports include typed issue analysis, executed queries, assessed evidence,
hypotheses, confidence, graph paths, usage, termination, and observable trace.
Reports persist at `<data-dir>/investigations/<UUID>.json`; traces contain actions
and concise decisions, never hidden chain-of-thought. They are separate from M1
SQLite task records, so `tasks show` does not load investigation artifacts yet.
Logs go to stderr. Provider errors exit 1; invalid input exits 2. Honest reports
ending on insufficient evidence or limits exit 0 and carry the termination reason.

To add an investigation to an Obsidian vault, first export its M4 graph notes,
then add `--export-obsidian /path/to/vault` to `investigate`. It writes one note
under `Investigations/`, linking the referenced symbols; it does not require
Obsidian. Export destinations inside the source repository are rejected.

The SDK exposes `client.investigate(path, Issue(...) or text, provider=...)`,
returning `InvestigationReport`. Provider injection supports offline testing
without subclassing the client. See [M5 architecture](m5-investigation.md).

### Investigation evaluation

```sh
uv run python scripts/benchmark_investigation.py \
  tests/fixtures/investigation_cases.json --env-file .env \
  --data-dir /tmp/repoagent-benchmark
```

Two controlled repositories cover email normalization and an inventory boundary.
Labels remain in the evaluator. Metrics measure file/symbol recall over the final
relevant evidence set, exact primary-citation localization, iterations, and
retrieval calls. They are not Recall@K across multiple search rounds. Automated
fixture-provider scores test plumbing; only live-provider runs assess model behavior.

Limitations: the existing hashing embeddings and keyword reranker are lexical
approximations, static calls may remain ambiguous, indexes can become stale,
source snippets are truncated, and there is no execution evidence or confidence
calibration. M5 runs synchronously and persists final traces; it does not offer
crash-resumable LangGraph checkpoints or a background task API.

## Unavailable workflows (task records)

```sh
uv run repoagent --data-dir .repoagent ask ./repo 'How is auth done?' --json
uv run repoagent --data-dir .repoagent fix ./repo 'Login returns 500' --json
uv run repoagent --data-dir .repoagent tasks show TASK_ID --json
```

`ask`, `fix`, and `test` validate input and record a **blocked**
task with a `capability_unavailable` event, exiting with code **3**. This is
expected behavior, not evidence of an attempted operation. Exit codes: 0
success; 1 operational failure; 2 invalid input; 3 unavailable capability.

## Python SDK

```python
from pathlib import Path
from repoagent import RepoAgent, Settings

client = RepoAgent(settings=Settings(data_dir=Path(".repoagent")))
summary = client.index("./some-python-project")
print(summary.chunk_count, summary.node_count, summary.edge_count)

response = client.search(
    "./some-python-project", "verify password", strategy="hybrid_graph", top_k=3
)
for hit in response.results:
    print(hit.rank, hit.chunk.file_path, hit.chunk.qualified_name, hit.evidence)

graph = client.retrieval().graph("./some-python-project")
print(len(graph.nodes), len(graph.edges))
```

`index`, `search`, `analyze`, and `evaluate` return typed Pydantic models.
`ask`, `fix`, `test`, `submit`, `get_task`, and `task_events`
remain available; unavailable workflows return blocked task records. The SDK
never prints, terminates the process, or installs logging handlers. Storage
and embedding providers are injectable (`index_store=`, `embedding_provider=`)
behind the `IndexStore` and `EmbeddingProvider` protocols.

## Configuration and data

Settings use the `REPOAGENT_` prefix; see `.env.example`. Task data defaults
to `~/.repoagent/tasks.sqlite3`; retrieval indexes are stored under
`<data-dir>/indexes/`. Embedding configuration: `REPOAGENT_EMBEDDING_PROVIDER`
(`hashing` deterministic local provider) and `REPOAGENT_EMBEDDING_DIMENSION`.
An index records its provider and dimension; searching with a mismatched
provider fails with a clear error instead of silently degrading. Logs contain
allowlisted metadata only. Target code is never imported or executed by
analysis, indexing, or search.

## Validation

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python scripts/check_quality.py
uv build
```

The quality helper requires fresh statement coverage strictly above 85% and
at most 150 physical lines per Python file. CI repeats validation and a wheel
smoke test on Python 3.12/3.13.

## Architecture and next step

Source modules live directly in `src/` (`sdk/`, `domain/`, `application/`,
`adapters/`, `analysis/` (M2), `retrieval/` and `evaluation/` (M3), `graph/`
and `export/` (M4), `cli/`). See
[architecture](architecture.md) for boundaries and the pipelines;
see [milestones](milestones.md) for the roadmap.

M8 benchmarking, API, and dashboard are documented in the [README](../README.md)
and [benchmarks](benchmarks.md).

## Static repair proposals (M6)

M6 extends the M5 Investigator with a separate LangGraph workflow:

```text
Investigator → Developer → Static Patch Validator → Reviewer
                                      ↑              │
                                      └── REVISE ─────┘
```

`repoagent repair` first requires a confident, evidence-backed M5 root cause. The
Developer receives only the report's assessed evidence and source snippets, then
returns a typed plan and unified diff. The validator checks bounded unified diffs
in memory: safe existing paths, hunk context, text-only changes, size, and Python
syntax. The Reviewer independently returns approve, revise, or reject. An approval
means only **approved for M7 runtime validation**.

```sh
uv run repoagent --env-file .env --data-dir /tmp/repoagent-data index ./project
uv run repoagent --env-file .env --data-dir /tmp/repoagent-data repair \
  ./project "Users with uppercase email addresses cannot log in" \
  --max-revisions 2 --json
```

The patch is never applied to the target tree and target code is never executed.
M6 exposes no shell, write, git, browser, or test tools. Revision feedback and
review history are stored in the returned report, with an explicit terminal status
for rejection, insufficient investigation, provider failure, or revision limit.
Static validation does not prove that a patch fixes behavior; use `--execute` (M7).

## Sandboxed validation and repair loop (M7)

```sh
uv run repoagent --env-file .env --data-dir /tmp/repoagent-data index ./project
uv run repoagent --env-file .env --data-dir /tmp/repoagent-data repair \
  ./project "Users with uppercase email addresses cannot log in" \
  --execute --max-attempts 3 --timeout 300
```

Without `--execute`, `repair` behaves exactly as in M6 and runs nothing;
`--max-attempts`/`--timeout` without `--execute` are rejected (exit 2).
`--execute` exits 0 only for `VALIDATED`, otherwise 1.

```text
Detect validation (static) → Docker available? → Investigator
  → Baseline (unpatched copy) → Developer → Static Validator → Reviewer
  → Sandbox (fresh copy + patch) → Validate
        PASS → VALIDATED
        FAIL → deterministic triage ─┬→ Failure Analyzer (LLM, only if needed)
                                     ├→ Developer revision (runtime feedback)
                                     └→ Investigator re-entry (root cause uncertain, bounded)
```

Example output (fixture run):

```text
Investigation
✓ root cause localized: raw email equality lookup
Sandbox
✓ created
Baseline
✗ 1 tests failed, 0 errors
Attempt 1
  Developer ✓ patch generated: Normalize both values before email comparison.
  Reviewer ✓ approve
  ✗ 2 tests failed, 0 errors
  Failure Analyzer → patch missed normalization in secondary lookup
Attempt 2
  Developer ✓ patch generated: ...
  Reviewer ✓ approve
  ✓ tests passed (3 passed, 0 skipped)
Result:
VALIDATED
```

**Statuses.** `validated`, `validation_failed` (analyzer says stop, or the
Developer repeated a failed patch), `patch_apply_failed`, `sandbox_failed`,
`timeout`, `max_attempts`, `baseline_failed` (baseline could not run to a parseable
result), `insufficient_evidence`, `validation_unavailable` (no pytest detected),
`review_rejected`, `provider_error`. Developer/Reviewer approval alone never yields
`validated`.

**Validation rule.** A repair is `VALIDATED` only if the sandbox completed, the
original repository fingerprint is unchanged, pytest exits 0 on the patched copy,
and Ruff (when the project configures it) reports no violation absent from the
baseline. The baseline distinguishes pre-existing failures (`fixed_failures`,
`persisting_failures`) from regressions (`new_failures`, `new_lint`).

**Commands.** Validation commands come from static detection
(`pyproject.toml`, `pytest.ini`, `setup.cfg`, `tox.ini`, `tests/`, `ruff.toml`),
never from model output. Command kinds are an enum mapped to constant argv
vectors (`python -m pytest -q -rfE -p no:cacheprovider -o addopts=`,
`python -m ruff check --no-cache --output-format=concise .`) and filtered by an
allowlist. Dependencies are installed wheel-only (`--only-binary=:all:`) from
specifiers that must match a strict name/extras/version grammar; URLs, paths,
options, `-e`, and markers are skipped and recorded.

**Token efficiency.** Exit codes, pytest/Ruff results, patch application,
timeouts, collection errors, lint-only failures, and repeated identical failures
are handled deterministically. The Failure Analyzer is called only for genuine test
failures and receives the issue, root cause, current diff (≤6000 chars), at most
four evidence snippets from patched files, failing tests, a ≤2000-char output
tail, and one-line summaries of previous attempts. Sandbox and index availability
are checked before any LLM call.

**Configuration** (`REPOAGENT_` prefix): `EXECUTION_TIMEOUT` (per command,
seconds), `REPAIR_MAX_ATTEMPTS`, `REPAIR_MAX_REINVESTIGATIONS`, `SANDBOX_IMAGE`,
`SANDBOX_MEMORY_MB`, `SANDBOX_CPUS`, `SANDBOX_PIDS_LIMIT`,
`SANDBOX_MAX_OUTPUT_BYTES`, `SANDBOX_INSTALL_TIMEOUT`, `SANDBOX_NETWORK`
(`install_only`|`none`), `SANDBOX_DEPENDENCIES` (`project`|`tools`|`none`),
`SANDBOX_CLEANUP` (`always`|`keep_failed_workspace`),
`SANDBOX_ALLOWED_COMMANDS`, `SANDBOX_WORKSPACE_DIR`.

**Security controls.** Every target is treated as hostile:

- A fresh host-private copy per run; `.git`, virtualenvs, caches, symlinks,
  FIFOs/devices, `.env*`, keys, `.netrc`/`.pypirc`/`.npmrc` are never copied;
  files are opened with `O_NOFOLLOW`; file-count and size limits apply.
- The patch is re-checked against the copy (path traversal, stale context, syntax)
  and written without following links; failure is `patch_apply_failed`.
- Containers: `--network none` for validation, `--read-only` root filesystem,
  `/tmp` tmpfs, `--cap-drop ALL`, `no-new-privileges`, non-root user, memory,
  swap, CPU, PID, open-file and file-size limits, `--init`, explicit minimal
  environment (no host variables), only the copy and the dependency directory
  mounted (dependencies read-only).
- Dependency preparation runs in a separate container that mounts only the empty
  dependency directory; the repository is never present while network is enabled.
- Host `docker` CLI calls use argv lists (`shell=False`), a minimal environment
  (no API keys), head/tail-bounded output capture, and process-group kill plus
  `docker rm --force` on timeout.
- Workspaces, dependency directories, and containers are removed after success,
  failure, patch errors, timeouts, and exceptions.

**Remaining isolation limitations.** Docker shares the host kernel; a kernel or
runtime escape is out of scope (use gVisor/Kata/Firecracker or a VM for stronger
isolation). Dependency installation with `install_only` network can reach any
package index host and installs the target's declared wheels, whose import-time
code then runs (offline) during tests. Docker Desktop on macOS/Windows applies
limits to its VM. Rootless Docker and user-namespace remapping are not configured
by RepoAgent. Running RepoAgent as root maps the container to `nobody`, which may
not be able to read the private workspace. Image references are validated but not
digest-pinned by default; pin `REPOAGENT_SANDBOX_IMAGE` by digest for
reproducibility.

**Other limitations.** Only Python/pytest (+Ruff) validation is supported; target
repositories needing services, databases, compilers, or sdists will fail with
`baseline_failed`/`sandbox_failed`. Dependency manifests changed by a patch are not
re-installed. Failure analysis and re-investigation are bounded but not calibrated;
retrieval for re-investigation uses the stored index snapshot. The loop is
synchronous and reports persist at `<data-dir>/repairs/<UUID>.json` without
crash-resumable checkpoints.

SDK:

```python
report = client.repair_and_validate(
    "./project", "Uppercase emails cannot log in", max_attempts=3, timeout=300
)
print(report.status, report.metrics.attempts, report.metrics.llm_calls)
for attempt in report.attempts:
    print(attempt.number, attempt.validation.summary, attempt.failure_analysis)
```

`RepoAgent(sandbox_runner=...)` accepts any `SandboxRunner` implementation; the
default is `DockerSandboxRunner`. Metrics per repair: attempts, LLM calls,
retrieval calls, investigations, files/lines changed, validation and sandbox
seconds, tests before/after, and final status.
