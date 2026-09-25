# Changelog

Milestone-level history. Entries summarize what shipped and reference the
detailed writeups in `docs/milestones.md` and `docs/architecture.md`; commands
and behavior described here must match the current `README.md` — if they
diverge, the code and README are correct, not this file.

## Unreleased — Retrieval quality, audit → validated repair, real-bug suite

- Graph nodes and code chunks share one stable identity (`symbol_node_ids`);
  duplicate qualified names (`foo#2`) now map to their own chunk, and graph
  expansion starts from the exact node of each seed.
- Optional semantic embeddings for any OpenAI-compatible endpoint
  (`REPOAGENT_EMBEDDING_PROVIDER=openai`). Token-dense inputs that a local
  server rejects are retried alone and halved.
- Configurable graph policies (edge weights, uncertain-edge weight, seed
  cap, gating, depth). The default is now `calls_inherits`, chosen from
  pooled measurements on 45 tasks.
- Semantic and LLM listwise rerankers, and an optional rerank pool. NDCG@K
  added to retrieval metrics. Retrieval benchmark arms (`graph_*`,
  `rerank_*`).
- `repoagent audit --repair --execute` runs the best verified finding
  through the unchanged M7 validated repair.
- Real-bug suite `benchmarks/real_repair.json` (20 SWE-rebench tasks) with
  pinned images and requirements, the `benchmark-import swerebench` and
  `benchmark-verify` commands, per-stage failure reporting, and image
  digests in manifests.
- Sandbox: pinned requirements (`SANDBOX_PINNED_REQUIREMENTS` or
  `SANDBOX_REQUIREMENTS_FILE`) and a `src/` import root for src-layout
  projects.
- Investigator: a mistyped citation no longer aborts hypothesis generation,
  and shortened symbol names are grounded to cited evidence. New
  `best_hypothesis` repair ablation.
- `REPOAGENT_LLM_REASONING_EFFORT`, mypy with the pydantic plugin
  (`scripts/typecheck.py`, clean), and pip-audit in CI.

## Unreleased — Web workflows (RepairGraph / DiscoveryGraph)

- Added `RepairGraph` and `DiscoveryGraph`: top-level LangGraph workflows
  composing the existing Investigator, Developer/Reviewer, sandbox repair
  loop, and audit detector/evidence/verifier pipeline without duplicating any
  of them.
- Added GitHub-URL-driven web workflows: hardened, credential-free shallow
  fetch into an isolated workspace (`adapters/github_source.py`), live stage
  progress derived from real LangGraph node execution via a LangChain
  callback handler, and deterministic workflow limits (LLM calls, tokens,
  task deadline) consolidated in `domain/limits.py` / `ai/budget.py`.
- Added LangChain integration at the edges only: a chat-model adapter
  (`ai/langchain_chat.py`), a retriever/tool exposing the existing
  BM25+vector+graph fusion (`retrieval/langchain_adapters.py`), and
  bidirectional embedding adapters. The custom hybrid RAG and native graph
  were not replaced.
- Added API endpoints: `POST /api/tasks/repair`, `POST /api/tasks/discover`,
  `POST /api/tasks/{id}/findings/{finding_id}/repair` (discovery → repair
  handoff on the same fetched snapshot), `GET /api/tasks/{id}/graph`
  (bounded interactive view, `?format=graph.json` download).
- Rebuilt the web app: GitHub URL + operation selection home page, live
  per-stage progress display, repair and discovery result views (evidence,
  diff, reviewer decisions, baseline/patched test and Ruff comparison,
  verified/uncertain/rejected finding cards), and an interactive SVG
  knowledge-graph explorer (zoom/pan, kind/edge filters, node detail panel
  with callers/callees/imports/inheritance).
- Added a deterministic per-job task-timeout watchdog (`adapters/job_queue.py`):
  a `threading.Timer` marks a job `FAILED` at `workflow_task_timeout` wall
  time regardless of what step it's stuck in, guarded against a late natural
  completion overwriting an already-reported timeout. Not an LLM agent —
  the original spec explicitly excludes an LLM watchdog; this closes the one
  real gap (`BudgetedProvider`'s deadline only checks at LLM call
  boundaries) with a plain timer.
- Wired `LangChainChatProvider` through the same rate-limit gatekeeper
  (`ai/throttle.SlidingWindowLimiter`) that `GroqProvider`/`OpenAIChatProvider`
  already use, closing a gap found in code review where a LangChain-backed
  provider bypassed throttling entirely.
- Added `docs/PRD.md`, `docs/TODO.md`, `docs/CONTRIBUTING.md`, this file.

## M9 — Repository audit / issue discovery

- Added `repoagent audit` / `RepoAgent.audit()`: deterministic AST and graph
  detectors discover candidate issues (broad exception handling, mutable
  defaults, unguarded `None` access, resource leaks, subprocess risk, dead
  code, TODO markers, circular imports, coupling, optional Ruff), enriched
  with bounded hybrid/graph RAG evidence, then adjudicated one at a time by
  an LLM Issue Verifier into VERIFIED / UNCERTAIN / REJECTED.
- `--repair` converts the highest-confidence VERIFIED candidate into the
  existing `Issue` model and runs the unchanged M6/M7 repair pipeline —
  no second repair implementation.
- Added `graphify` / `GraphifyService`: one graph build persisted as both
  versioned `graph.json` and an Obsidian vault, reusing the existing graph
  and exporter rather than building a second graph model.

## M8 — Benchmarking, API, dashboard

- Benchmark suite/task format with fixture, BugsInPy, and SWE-bench adapters;
  pinned-commit materialization via hardened host `git`.
- Retrieval / investigate / repair benchmark modes, ablation flags
  (`RepairFeatures`), hidden-test evaluation in a fresh sandbox overlay.
- `JsonlResultStore` with reproducibility manifests (version, commit, suite
  hash, config, provider/model, sandbox image — never secrets).
- FastAPI service (`repoagent serve`) with a local job queue, security policy
  (allowlisted roots, gated execution, bearer token for non-loopback hosts),
  and background job endpoints that never block on long-running work.
- First React + TypeScript dashboard (superseded by the web-workflow rebuild
  above; local-path-only, no GitHub fetch, no live stage granularity beyond
  job events).

## M7 — Sandboxed validation and bounded repair loop

- `repair --execute` / `RepoAgent.repair_and_validate`: static validation
  detection, allowlisted command policy, hardened `DockerSandboxRunner`,
  baseline vs. patched pytest/Ruff with regression detection, deterministic
  failure triage, an LLM Failure Analyzer, bounded Developer revision
  retries, bounded Investigator re-entry, persisted attempt histories.
- A repair is reported `VALIDATED` only if the patched workspace's full test
  run actually passed — the reporter downgrades any status that lacks a
  passing patched validation.

## M6 — Developer / Reviewer / static patch proposals

- Read-only `Developer → static validator → Reviewer` LangGraph consuming M5
  evidence. Produces bounded unified diffs, validated only in memory
  (existing paths, hunk context, size, Python syntax). Reviewer independently
  returns approve/revise/reject with bounded revisions. No patch is applied
  or executed — that is M7's job.

## M5 — LangGraph Investigator

- Stateful, read-only investigation graph: issue analysis, iterative
  retrieve → assess → refine, hypothesis generation and a challenge/evaluate
  loop, all under hard iteration/query/evidence/tool-call limits.
- Groq and OpenAI (and OpenAI-compatible, e.g. z.ai/GLM) provider adapters
  behind a vendor-independent `LLMProvider` protocol; provider-reported
  token accounting via `CountingProvider`.
- Durable JSON investigation reports; Obsidian notes.

## M4 — Code knowledge graph

- `RepositoryGraphBuilder`: DEFINES/CONTAINS/IMPORTS/INHERITS/CALLS edges
  from M2 analysis, conservative name-based call resolution (unresolved
  targets marked, never invented).
- Bounded, cycle-safe graph traversal and expansion; `hybrid_graph` retrieval
  strategy fusing hybrid RRF seeds with graph-expanded candidates through the
  same fusion implementation (no duplicated ranking logic).
- `repoagent graph` / `export-obsidian` / `graphify` CLI commands.

## M3 — Hybrid retrieval

- Structure-aware `CodeChunker` (functions, methods, classes, module
  sections) with stable, content-addressed chunk IDs.
- `BM25Retriever` (identifier-aware tokenization), `HashingEmbeddingProvider`
  + `LocalVectorStore` (deterministic, offline), reciprocal-rank-fusion
  `HybridRetriever`, optional keyword-overlap reranker.
- `IndexService`/`IndexStore` persistence; `RetrievalEvaluator` (Recall@K,
  MRR, HitAt@K, Precision@K) with no LLM in the loop.

## M2 — Repository analysis

- Ignore-aware, symlink-safe `FileDiscovery`; `PythonAnalyzer` over the
  standard `ast` module (never imports or executes target code); typed
  `CodeSymbol`/`Relationship`/`ImportInfo` extraction with per-file error
  isolation.

## M1 — Foundation

- Public `RepoAgent` SDK facade over a `TaskService` / `TaskStore` protocol
  boundary; `SQLiteTaskStore` adapter; Typer CLI routed entirely through the
  SDK; validated settings (`REPOAGENT_` prefix, explicit dotenv only); no
  network/storage side effects at construction time.
