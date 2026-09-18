# TODO / Backlog

Actionable, honestly-scoped work items. Each item names the gap and where it
lives; it is not a promise of a delivery date. Move an item to "Done" only
when it is implemented, tested, and documented — not when it is merely
started. Keep this list truthful: an item that turns out to be unnecessary
should be deleted, not marked done.

Sourced from `README.md#limitations`, `docs/benchmarks.md`, and open
questions noted during the M9 web-app build. Update this file, not the PRD,
for routine planning.

## High priority

- [ ] **Measure live-model repair success.** `repair_and_validate` has no
      measured Docker-validated success rate with a live model (Groq quota was
      exhausted during the last run). Re-run `benchmarks/fixtures.json` in
      `repair` mode end to end and commit the results under
      `benchmarks/results/`.
- [ ] **Workspace garbage collection.** Fetched GitHub workspaces
      (`<data-dir>/workspaces/`) are never cleaned up. Add an age- or
      count-based eviction policy (`sdk/workflows.py`, `adapters/github_source.py`).
- [ ] **Multi-tenant task isolation.** `/api/tasks` lists every job with no
      accounts or ownership. Fine for the local/demo deployment target; must be
      resolved before any shared/hosted deployment (`api/job_routes.py`,
      `api/workflow_routes.py`).

## Medium priority

- [ ] **Streamed progress.** Web workflow progress is polled every 1.2s
      (`dashboard/src/components/TaskPage.tsx`). An SSE or WebSocket endpoint
      would remove the latency/poll-storm tradeoff for longer-running repairs.
- [ ] **Larger, representative benchmark subsets.** Current B/C stages (10 and
      9 tasks) are explicitly non-representative samples chosen for repository
      size (`docs/benchmarks.md`). Expand sample size and add confidence
      intervals before citing aggregate numbers externally.
- [ ] **Per-project environments for BugsInPy/SWE-bench repair.** Repair
      execution is retrieval-only for stages B/C today because per-project
      Python environments aren't built (`src/benchmark/task_executor.py`).
- [ ] **Confidence calibration.** Hypothesis/verifier confidence values are
      uncalibrated (never checked against outcome frequency). Needs a labeled
      calibration set before confidence numbers can be trusted quantitatively.
- [ ] **Graph view for very large repositories.** `graph/view.py` truncates
      at 600 nodes and rebuilds from the snapshot on every request; no
      caching, no server-side clustering for repos well beyond that size.

## Lower priority / exploratory

- [ ] **Semantic embeddings.** Default `HashingEmbeddingProvider` is lexical
      (hashed tokens + trigrams), not semantic. A real embedding model adapter
      exists via the LangChain `Embeddings` bridge
      (`retrieval/langchain_adapters.py`) but is not the default; needs a
      recall/MRR comparison before switching defaults.
- [ ] **Type-aware call resolution.** `CALLS` edges in the knowledge graph are
      name-based (`graph/resolver.py`); attribute calls on same-named methods
      across types stay ambiguous. Would need lightweight type inference.
- [ ] **Multi-language analyzers.** Python-only via `ast`. A second language
      would need its own analyzer behind the existing `RepositorySource`/
      symbol protocols without touching Python-specific code.
- [ ] **Durable job queue.** `LocalJobQueue` is an in-process thread pool;
      queued (not yet started) work does not survive a process restart. A
      Redis/RQ or Celery adapter can implement the same `JobQueue` port.
- [ ] **Dependency-manifest-aware revalidation.** If a patch changes
      `pyproject.toml`/`requirements.txt`, dependencies are not reinstalled
      before patched validation (`validation/detection.py`).

## Done (recently)

- [x] Web app: GitHub-URL-driven Repair/Discover UI, live stage progress,
      interactive repository graph, discovery → repair handoff — this build.
- [x] LangGraph `RepairGraph`/`DiscoveryGraph` wrapping M5–M7 agents without
      duplicating repair/retrieval logic — this build.
- [x] Deterministic workflow limits (LLM call/token budget, task deadline)
      consolidated in `domain/limits.py` — this build.
- [x] Repository audit / issue discovery capability (M9, prior session).
- [x] Graphify unified `graph.json` + Obsidian pipeline (M4 follow-up).

## From the 2026-09-18 code review (`/code-review high`, web-workflow diff)

All 10 findings were verified against source. The 3 most severe were fixed
immediately (with regression tests); the rest are logged here rather than
fixed unreviewed, since several are legitimate scope/severity tradeoffs.

### Fixed

- [x] **Deterministic task-timeout watchdog.** `WorkflowLimits.task_timeout_seconds`
      only bounded gaps between LLM calls (via `BudgetedProvider`); a job
      stuck in a non-LLM step had no wall-clock cap. `adapters/job_queue.py`
      now schedules a `threading.Timer` per job that marks it `FAILED` at the
      deadline, guarded so a late natural completion can never overwrite an
      already-reported timeout. No LLM involved — this is exactly the
      deterministic limit the original spec asked for, not the forbidden LLM
      watchdog agent. Covered by `tests/unit/test_job_queue_watchdog.py`.
- [x] **`LangChainChatProvider` now shares the rate-limit gatekeeper.**
      Wired through the same `SlidingWindowLimiter` (`ai/throttle.py`) that
      `GroqProvider`/`OpenAIChatProvider` use, via optional
      `tokens_per_minute`/`requests_per_minute`/`limiter=` constructor
      arguments (off by default, preserving prior behavior). Covered by
      `tests/unit/test_langchain_rate_limit.py`.

- [x] **GitHub install race (TOCTOU).** `GitHubRepositorySource._install()`
      unconditionally `rmtree()`d the target and renamed staging into it, with
      the `.ready` marker checked before, not during, install — concurrent
      jobs fetching the same commit could destroy each other's installed
      workspace. Fixed with a module-level per-target lock
      (`adapters/github_source.py`); covered by
      `tests/unit/test_github_source_concurrency.py`.
- [x] **Verifier LLM call count inflated by budget exhaustion.**
      `verify_candidates()` set `verification_llm_calls=len(candidates)` even
      for candidates short-circuited by `LLMBudgetExceeded` before ever
      reaching the provider. Fixed to count only calls that actually reached
      the provider (`application/audit_verification.py`); covered by an
      assertion added to `test_exhausted_budget_leaves_candidates_uncertain_with_reason`.
- [x] **`discover(..., limit=0)` silently used the configured default.**
      `limit or self.limits.discovery_candidates` treats `0` as unset because
      `0` is falsy in Python. Fixed to check `is not None`
      (`sdk/workflows.py`); covered by
      `test_explicit_zero_limit_is_honored_not_treated_as_unset`.

### Open — logged, not yet fixed

- [ ] **Sandbox-eligibility check races the `/api/config` fetch.**
      `TaskPage.tsx`'s `repairFinding()` reads `config` from React state; if
      the user clicks "Attempt Repair" before the initial `api.config()`
      promise resolves, `sandbox` silently evaluates to `false` even for an
      allowlisted repository. Fails safe (no sandbox, not an unintended
      sandbox), so low severity, but should show a "still loading server
      config" state instead of silently downgrading.
- [ ] **Crashed vs. intentionally-skipped stages look identical in the UI.**
      `domain/workflow.py`'s `settle()` maps every remaining `PENDING` stage
      to `SKIPPED` on both success and failure, so a stage the workflow never
      reached because it crashed renders with the same neutral "–" icon as a
      stage that was legitimately not applicable (e.g. Docker validation on a
      static-only repair). The failed stage itself is still marked ✗ and the
      job-level error banner shows, so this is a polish gap, not a
      correctness bug — worth a distinct status if the stage model changes.
- [ ] **`repair_finding` assumes a GitHub `handle.source`.**
      `api/workflow_routes.py`'s `repair_finding()` only calls
      `parse_github_url(handle.source)` inside the `sandbox_validation`
      branch; a `DiscoveryWorkflowResult` produced via direct SDK use against
      a local path (bypassing the GitHub-only web route but sharing the job
      store) would raise `RepositoryInvalid` (400) instead of a
      policy-forbidden (403) response. Not reachable from the web UI today.
- [ ] **`JobKind` conflates legacy and workflow task shapes.** `REPAIR`/
      `VALIDATED_REPAIR` are reused for both the old local-path jobs
      (`job_routes.py`) and the new GitHub-workflow jobs
      (`workflow_routes.py`), forcing consumers (`api/task_results.py`,
      `TaskPage.tsx`) to runtime-check for a `workflow` field instead of
      trusting `kind` alone. Would need a real discriminated union per
      producer to clean up.
- [ ] **`GET /tasks/{id}/graph` rebuilds the graph from scratch every call.**
      `api/task_results.py`'s `task_graph()` re-parses and re-builds the
      whole repository graph on every request instead of reusing the
      `GraphSnapshot` already built once during the workflow's
      `analyze_repository` stage. Fine for the fixture-sized repos used in
      tests/demos; will be a real latency cost on larger repositories or
      repeated task views.
- [ ] **`local_handle()`'s `RepositoryHandle.name` breaks the owner/name
      slug contract.** `workflows/discovery_nodes.py`'s default loader sets
      `name` to the bare directory basename, while
      `GitHubRepositorySource.materialize()` sets it to `owner/name`; the
      sandbox-allowlist checks (`TaskPage.tsx`, `ApiPolicy.github_execution`)
      assume the latter. Only matters if a workflow is ever run against a
      local path without an explicit `loader=` override (not exercised by
      the current web routes, which are GitHub-only).
- [ ] **`GraphExplorer`'s force-directed layout runs synchronously on the
      main thread.** `dashboard/src/graph/layout.ts` is O(n²) per iteration;
      near the 600-node truncation cap this can visibly block the UI thread
      during the initial render. Consider a Web Worker or an iteration cap
      tied to node count.
- [ ] **GitHub URL validation is duplicated.** `domain/github.py` (server,
      authoritative) and `dashboard/src/validation.ts` (client,
      instant-feedback mirror) implement the same rules independently by
      design (the client can't import Python), but they should be checked
      against each other whenever either changes — there's no automated
      cross-check today.
- [ ] **Legacy `/api/investigate` and `/api/repair` job endpoints never pass
      `stages`.** `api/job_routes.py` doesn't pass a `stages` list to
      `ctx.jobs.submit(...)`, so `JobRecord.stages` stays empty for those two
      routes. Currently unreachable from the dashboard (it now submits only
      through `/api/tasks/repair` and `/api/tasks/discover`), so low
      priority, but would surface as "no progress shown" if anything else
      calls the legacy routes directly.
