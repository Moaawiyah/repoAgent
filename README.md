# RepoAgent

RepoAgent is an autonomous repository engineering agent for Python codebases.
Given an unfamiliar repository and a bug report, it analyzes the code
statically, retrieves evidence with hybrid and graph-enhanced RAG, and
investigates the root cause with a LangGraph workflow. It then generates a
minimal patch, has it reviewed, and validates the patch in an isolated Docker
sandbox, retrying with failure analysis when validation fails. Every stage is
measured by a reproducible benchmark harness and exposed through a CLI, a
Python SDK, a FastAPI service, and a small React dashboard.

RepoAgent never modifies the repository you point it at. Patches are applied
only to disposable copies, and target code runs only inside the sandbox.

> **Status:** M1–M8 are implemented. Measured retrieval results and a first
> live-model localization run are below. Docker-validated repair success with
> a live model has **not been measured** yet (Groq daily token quota
> exhausted); see [Benchmark results](#benchmark-results).

## Architecture

```text
                 RepoAgent (CLI · Python SDK · FastAPI · dashboard)
                                   │
        ┌──────────────────────────┴──────────────────────────┐
        │                                                     │
 Repository analysis (AST, M2)                         Issue / task
        │                                                     │
 Code knowledge graph (M4)                                    │
        │                                                     │
 BM25 + vector + RRF + graph expansion (M3/M4) ───────────────┤
        │                                                     │
        └──────────────────────────┬──────────────────────────┘
                                   ▼
                     Investigator (LangGraph, M5)
                                   ▼
                          Developer (M6)
                                   ▼
                  Static patch validator → Reviewer
                                   ▼
               Docker sandbox: baseline → patched validation (M7)
                                   ▼
                          pytest / Ruff results
                             ↙            ↘
                          FAIL            PASS → validated repair
                            ↓
          deterministic triage → Failure Analyzer → retry
          (bounded; Investigator re-entry when the root cause is uncertain)
                                   ▼
             Benchmark runner · metrics · failure categories (M8)
```

Layering follows the project rules: presentation (CLI, API, dashboard) calls
the SDK. The SDK calls application services, which depend on domain models
and ports. Adapters implement those ports: SQLite and JSON stores,
Groq/OpenAI providers, the Docker sandbox, and the job queue. See
[architecture](docs/architecture.md).

## Capabilities by milestone

| Milestone | Implemented capability |
| --- | --- |
| M1 | Package, validated settings, SQLite task store, CLI, SDK facade |
| M2 | Ignore-aware, symlink-safe discovery and Python AST analysis (symbols, imports, relationships) |
| M3 | Structure-aware chunking, BM25, hashing embeddings, vector store, reciprocal-rank fusion, reranking, retrieval evaluation |
| M4 | Code knowledge graph (defines, contains, imports, inherits, calls), bounded expansion, `hybrid_graph` retrieval, Obsidian export |
| M5 | LangGraph Investigator: evidence assessment, hypotheses and challenge loop, Groq and OpenAI adapters |
| M6 | Developer, static patch validator, and Reviewer graph producing minimal unified diffs |
| M7 | Docker sandbox, allowlisted commands, baseline/patched pytest and Ruff, failure analysis, bounded retries |
| M8 | Benchmark framework (fixtures, BugsInPy, SWE-bench adapters), ablation flags, metrics and failure taxonomy, token-efficiency work, FastAPI with background jobs, React dashboard |

Future ideas, **not implemented**: durable distributed job queue,
multi-language analyzers, semantic embedding models, per-instance SWE-bench
environment images, a hosted multi-tenant service.

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). Docker is required
only for sandboxed validation. Node 22+ is needed only to build the dashboard.

```sh
uv sync --locked
uv run repoagent --help
cp .env.example .env   # set REPOAGENT_LLM_PROVIDER / MODEL / API_KEY for agent features
```

Analysis, indexing, search, graph inspection, and retrieval benchmarks run
offline without an LLM.

Provider rate limits are handled in three layers:

- Proactive throttling: set `REPOAGENT_LLM_TOKENS_PER_MINUTE` and
  `REPOAGENT_LLM_REQUESTS_PER_MINUTE` to your plan's limits (for example
  Groq on-demand `openai/gpt-oss-20b`: 8000 TPM).
- Bounded HTTP 429 retries that honor `retry-after`
  (`REPOAGENT_LLM_RATE_LIMIT_RETRIES`, `REPOAGENT_LLM_RATE_LIMIT_MAX_WAIT`).
- Fail-fast when the provider asks for a longer wait, such as an exhausted
  daily token quota.

## CLI usage

```sh
uv run repoagent analyze ./project
uv run repoagent index ./project
uv run repoagent search ./project "where are sessions refreshed" --strategy hybrid_graph
uv run repoagent graph ./project --symbol "pkg.module.Class.method"
uv run repoagent --env-file .env investigate ./project "Uppercase emails cannot log in"
uv run repoagent --env-file .env repair ./project "Uppercase emails cannot log in"            # static proposal
uv run repoagent --env-file .env repair ./project "Uppercase emails cannot log in" --execute  # Docker-validated
uv run repoagent benchmark fixtures --mode retrieval --k 5
uv run repoagent --env-file .env benchmark fixtures --mode repair --ablation full --ablation no_retry
uv run repoagent benchmark-report <run_id>
uv run repoagent serve --allow-root ./tests/fixtures --execution-repo ./tests/fixtures/auth_bug \
  --dashboard dashboard/dist
```

## Example investigation

Investigation runs a bounded LangGraph loop:
`analyze_issue → plan_search → retrieve → assess_evidence → (refine | hypothesize) → evaluate → report`.
The report contains assessed evidence with file, symbol, and line provenance,
graph paths, ranked hypotheses that cite evidence IDs, uncalibrated
confidence, the termination reason, token usage, and an observable trace (no
chain-of-thought).

```text
Root cause:  Fixture: raw email equality lookup
Evidence:    app/users/repository.py:12-17  app.users.repository.UserRepository.find_by_email (relevant)
Termination: confident_root_cause
```

This example shows the report format. The values come from the offline
fixture provider in tests, not from a live model run.

## Example repair

```text
Investigation ✓ root cause localized
Sandbox       ✓ created
Baseline      ✓ tests passed (1 passed)
Attempt 1
  Developer ✓ patch generated   Reviewer ✓ approve
  ✗ 2 tests failed
  Failure Analyzer → patch missed normalization in secondary lookup
Attempt 2
  ✓ tests passed
Result: VALIDATED
```

This transcript is also a format example: the loop runs offline with a fake
sandbox and a deterministic provider. `VALIDATED` requires a completed sandbox
run, an unchanged original repository, pytest exit code 0, and no new Ruff
violations relative to the baseline. A reviewer's approval alone never
produces `VALIDATED`.

## RAG architecture

- **Chunks** follow functions, methods, class preambles, and module code, with
  stable IDs derived from the repository name, path, symbol, and source hash.
  IDs do not depend on checkout location.
- **Retrievers**: BM25 with identifier-aware tokenization; a vector search
  over deterministic hashing embeddings behind an `EmbeddingProvider`
  protocol; reciprocal-rank fusion (`hybrid`); an optional keyword reranker.
- **Graph RAG** (`hybrid_graph`): hybrid results seed a bounded,
  cycle-safe graph expansion, scored by seed rank × distance decay × edge
  weight and fused with RRF. Each result carries lexical rank, vector rank,
  and the graph path.

## Knowledge graph

The graph has module, class, function, and method nodes with typed
`DEFINES`/`CONTAINS`/`IMPORTS`/`INHERITS`/`CALLS` edges. Call resolution is
conservative: ambiguous calls are marked `resolved: false` instead of guessed.
The same graph feeds retrieval, the Obsidian exporter, and the API/dashboard
neighborhood view (`GET /api/graph`). There is no separate graph system for
visualization.

## LangGraph workflows

- **Investigator**: iterative retrieval and hypothesis challenge loop, with
  hard limits on iterations, queries, evidence, tool calls, and context size.
- **Repair (M6)**: Developer → static validator → Reviewer, with bounded
  revision loops.
- **Validated repair (M7)**: baseline → propose (reuses M6) → execute →
  analyze → (propose | reinvestigate | report). A terminal status always
  routes to the report, and the recursion limit is derived from the attempt
  limits.

## Docker sandbox

Each run gets a fresh copy of the repository, excluding `.git`, secrets,
symlinks, and special files. The patch is re-verified against the copy.
Validation uses allowlisted command kinds mapped to constant argv lists;
LLM output never becomes a shell command. The container runs with
`--network none`, a read-only root filesystem, a tmpfs `/tmp`, all
capabilities dropped, `no-new-privileges`, a non-root user, memory/CPU/PID/
file-size limits, and no host environment. Dependency installation (wheels
only) runs in a separate container that does not mount the repository.
Output is capped, and timeouts kill the container. A real Docker integration
test uses a hostile target whose own tests confirm the isolation from inside
the container: no network, host paths invisible, read-only root, non-root
user, and no host secrets.

## Benchmark methodology

Benchmark tasks include the repository commit, issue, expected files and
symbols, gold patch, fail-to-pass and pass-to-pass tests, hidden tests, and
the expected outcome. Labels stay in the evaluator. Retrieval mode is
LLM-free. Investigate mode scores localization against the primary
hypothesis. Repair mode runs the full M7 loop and then an independent
hidden-test run in a fresh sandbox. Ablations (`full`, `no_graph`,
`no_reviewer`, `single_pass`, `no_retry`) toggle existing components through
flags. Each run stores `manifest.json` (version, commit, dirty flag, suite
hash, configuration, provider, image, timestamps; no secrets),
`results.jsonl`, and `summary.json`. Details:
[docs/benchmarks.md](docs/benchmarks.md).

## Benchmark results

All values below are measured. Retrieval results come from committed runs in
[`benchmarks/results/`](benchmarks/results/). Stage B and C are small subsets
chosen for repository size, so they are not representative samples.

**Retrieval (issue text as query), K = 5: Recall@5 / MRR**

| Stage (tasks) | BM25 | Vector | Hybrid | Hybrid+Graph |
| --- | --- | --- | --- | --- |
| A — internal fixtures (6) | 1.000 / 0.700 | 0.667 / 0.492 | 1.000 / 0.622 | 1.000 / **0.722** |
| B — BugsInPy subset (10)* | 0.125 / 0.200 | 0.000 / 0.000 | 0.087 / 0.083 | **0.450 / 0.350** |
| C — SWE-bench Verified subset (9) | 0.278 / 0.198 | 0.333 / **0.356** | 0.444 / 0.333 | **0.463** / 0.261 |

\*BugsInPy provides no issue text; queries are synthesized from failing test names.

Graph expansion clearly helped on the BugsInPy subset and had the best MRR on
the fixtures. On the SWE-bench subset it produced the best Recall@5 but a
lower MRR than vector or hybrid, so the Graph RAG benefit is not uniform. K = 10
results, the token-efficiency measurement (prompt characters −35.7% on
deterministic repair runs), and caveats are in
[docs/benchmarks.md](docs/benchmarks.md).

**Live investigation localization** on Stage A (6 tasks, Groq
`openai/gpt-oss-20b`, one run each; run `20260914T234945Z-dfa3f8`):

| Configuration | File / symbol localization | Avg LLM calls | Avg tokens in / out | Avg runtime | Failures |
| --- | --- | --- | --- | --- | --- |
| full (graph retrieval) | 33.3% / 33.3% | 4.50 | 6,167 / 3,590 | 68.7 s | insufficient_evidence 3, provider_error 1 |
| no_graph (hybrid only) | 66.7% / 66.7% | 4.83 | 6,262 / 3,493 | 81.8 s | provider_error 2 |

With 6 tasks and a single nondeterministic sample per configuration, this
difference is not statistically meaningful. Provider errors were schema
violations in model output (Groq `json_validate_failed`).

| Repair metric | Value |
| --- | --- |
| Validated repairs, repair success rate (hidden tests), average attempts | not measured |
| `no_reviewer`, `single_pass`, `no_retry` ablations; repair failure breakdown | not measured |

## API and dashboard

`repoagent serve` starts FastAPI on `127.0.0.1` with these endpoints:

- `POST /api/analyze`, `/api/index`, `/api/search`
- `GET /api/graph`
- `POST /api/investigate` and `POST /api/repair`: these return `202` with a
  job record and never block on the work
- `GET /api/tasks`, `/api/tasks/{id}`, `/api/tasks/{id}/result`
- `GET /api/benchmarks/runs[/{id}]`
- `GET /api/health`, `/api/config`

Jobs run on a local worker pool behind a `JobQueue` port and persist their
records and results as JSON behind a `JobStore` port. A durable queue can
replace them without changing routes.

The dashboard (`dashboard/`, React + TypeScript + Vite) submits
investigations and repairs and polls job progress. It shows the stage
timeline, evidence, root cause, graph neighborhood, patch diff, reviewer
decision, sandbox attempts, token usage, and final status.

```sh
cd dashboard && npm ci && npm run build   # then: repoagent serve --dashboard dashboard/dist ...
cd dashboard && npm run dev               # dev server proxies /api to 127.0.0.1:8000
```

## Security model

- Targets, issues, source, test output, and model output are untrusted data.
  Prompts separate them from instructions, and structured outputs are
  validated.
- The original repository is never written; its fingerprint is checked around
  every sandbox run. Only the sandbox executes target code, and only through
  allowlisted commands.
- API requests are limited to local repositories under `--allow-root`
  (resolved after symlinks, URLs rejected). **Execution** is limited to
  `--execution-repo` entries, so arbitrary repositories get analysis, search,
  and investigation only.
- The API has no shell endpoint. Binding a non-loopback host requires
  `REPOAGENT_API_TOKEN` (bearer token, constant-time comparison). Error
  responses are sanitized.
- Benchmark git fetches accept only pinned GitHub HTTPS commits with hooks,
  symlinks, and LFS disabled.
- **Remaining limitations**: Docker shares the host kernel (use gVisor, Kata,
  or a VM for hostile multi-tenant use). The dependency install phase has
  network access and installs the target's declared wheels. The API has no
  user accounts, rate limiting, or TLS termination. The local job queue is
  single-process (records persist, but queued work does not survive a
  restart).

## Limitations

- **Unmeasured repair performance.** Live-model repair success and most
  ablations are not measured. The live localization run covers only 6 tasks,
  one sample each, on a free-tier model.
- **Evaluation scope.** Benchmark subsets are small (6, 10, and 9 tasks)
  without confidence intervals. BugsInPy and SWE-bench tasks are evaluated
  for retrieval only, because repair execution needs per-project environments
  that RepoAgent does not build.
- **Analysis depth.** Python only. Hashing embeddings are lexical, not
  semantic. Call resolution is name-based.
- **Validation scope.** Validation supports pytest and Ruff. Dependency
  manifests changed by a patch are not reinstalled.
- **Confidence.** Confidence values are uncalibrated.
- **Dashboard progress.** Progress granularity comes from job events and the
  final report (no streaming of in-graph steps).

## Development

```sh
uv run ruff check . && uv run ruff format --check . && uv run pytest && uv run python scripts/check_quality.py
cd dashboard && npm run typecheck && npm test && npm run build
```

The quality gates require statement coverage strictly above 85% and at most
150 lines per Python file. Detailed per-milestone usage:
[docs/guide.md](docs/guide.md). SDK reference: [docs/sdk.md](docs/sdk.md).
