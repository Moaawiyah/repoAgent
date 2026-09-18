# Python SDK contracts

`from repoagent import RepoAgent` is the public entry point for local Python
consumers. It is an in-process SDK, not an HTTP client or an LLM-provider SDK.
The CLI uses this same facade. M1 scope is unchanged: all engineering operations
record blocked tasks and return the milestone explanation.

## OOP and dependency direction

`RepoAgent` composes `TaskService`, which depends on `TaskStore`. The default
adapter is `SQLiteTaskStore`. Supply another `TaskStore` implementation through
`RepoAgent(store=store)` without inheriting from the client or changing services.
The SDK owns lazy dependency wiring; adapters own connections and transactions.
No caller should need imports from `cli`, `application`, or `adapters` for normal
SDK usage. Domain models, errors, Settings and TaskStore are exported publicly.
The distribution includes `py.typed` for downstream type checkers.

## API

| Method | Inputs | Output |
| --- | --- | --- |
| `RepoAgent(settings=None, store=None)` | Keyword-only settings and/or injected store. | A lazy client; no storage I/O. |
| `index(source, *, commit=None)` | Existing local directory. | `IndexSummary` (M3/M4). |
| `analyze(source, *, commit=None)` | Same repository input. | `RepositoryAnalysis` (M2). |
| `ask(source, question, *, commit=None)` | Repository and nonempty text. | Blocked `TaskRecord` (use `investigate`). |
| `fix(source, issue, *, commit=None)` | Repository and nonempty text. | Blocked `TaskRecord` (use `repair_and_validate`). |
| `test(source, *, commit=None)` | Repository input. | Blocked `TaskRecord` placeholder. |
| `benchmarks()` | — | `BenchmarkApi` (`run`, `load`, `runs`); see M8 section. |
| `submit(request)` | Validated `TaskRequest`. | Blocked `TaskRecord`. |
| `get_task(task_id)` | UUID or UUID string. | Persisted `TaskRecord`. |
| `task_events(task_id)` | UUID or UUID string. | Sequence-ordered `list[TaskEvent]`. |

Methods are synchronous. Construction snapshots explicitly supplied Settings;
otherwise environment settings are loaded on the first valid operation. An
injected store takes precedence over settings and bypasses default configuration.
The SDK installs no log handlers and never exits the process. Applications may
configure the `repoagent` logger themselves. Calls can emit metadata through it.
There are no client-owned long-lived connections to close. Callers should avoid
sharing a lazily initialized client between threads; use a client per worker and
choose an adapter that supports the required concurrency.

## Error behavior

- Invalid repository/configuration/request values raise Pydantic `ValidationError`.
- Malformed task UUID strings raise `ValueError` before storage initialization.
- Unknown tasks raise `TaskNotFound`; unsupported databases raise `UnsupportedSchema`.
- Illegal storage transitions raise `InvalidTransition`.
- Filesystem/SQLite failures raise a sanitized `StorageError` at the SDK boundary.
- Domain operational errors inherit from exported `RepoAgentError`.
- Unavailable capabilities are persisted **blocked results**, not exceptions.

Custom adapters should raise domain errors for their backend-specific failures.
Consumers must check `TaskRecord.status`; receiving a record does not mean an
engineering task succeeded. No context manager, async client, remote API calls,
agent runner, or provider implementation is implied by this facade.

## Extending later milestones

Implement new use cases in application services with typed models and protocols.
Expose stable facade methods and keep presentation in CLI/API adapters. Inject
model, retrieval, source and sandbox implementations when their milestones arrive.
Do not make SDK consumers configure internal agent graphs or backend SDK objects
for ordinary usage. Avoid empty inheritance hierarchies and giant service classes.

## M5 investigation

```python
from repoagent import Issue, RepoAgent, Settings

client = RepoAgent(settings=Settings(_env_file=".env"))
client.index("./project")
report = client.investigate(
    "./project",
    Issue(description="Uppercase emails cannot log in"),
    max_iterations=3,
    top_k=5,
)
print(report.termination_reason, report.primary_hypothesis)
```

`provider=` accepts the vendor-neutral `LLMProvider` protocol. The SDK composes
`InvestigationApi` and the application service; it does not print, exit, or install
handlers. Reports and observable traces persist outside the repository in
`<data-dir>/investigations/`. Provider failure returns a typed partial report with
`provider_error`; missing configuration/index raises a domain error before a run.
`Issue`, `InvestigationReport`, `InvestigationLimits`, `EvidenceItem`,
`RootCauseHypothesis`, `TerminationReason`, and `LLMProvider` are public imports.
Use `client.retrieval()` for graph/evaluation/export capabilities. M5 offers no
code modification or execution methods to the agent.

## M6 repair

`client.repair(source, issue, max_revisions=2, provider=...)` indexes no new
content; callers must index first. It returns a typed `RepairReport` containing the
M5 investigation, optional `PatchProposal`, deterministic `StaticValidation`,
review history, and an explicit status. The SDK never writes target code or runs it.

## M7 validated repair

`client.repair_and_validate(source, issue, max_attempts=None, max_revisions=None,
timeout=None, provider=None)` returns a `ValidatedRepairReport` with the
investigation, detected `ValidationPlan`, baseline `ValidationResult`, every
`RepairAttempt` (patch, reviews, validation, failure analysis, summary), metrics,
and an `ExecutionStatus`. Inject `RepoAgent(sandbox_runner=...)` to replace the
default `DockerSandboxRunner`; implementations must satisfy the `SandboxRunner`
protocol and clean up on exit. The SDK never runs target code outside the runner.

## M8 benchmarks

```python
client = RepoAgent(settings=Settings(_env_file=".env"))
run = client.benchmarks().run("benchmarks/fixtures.json", mode="retrieval", k=5)
print(run.summary.experiments[0].retrieval["hybrid_graph"])
run = client.benchmarks().run("fixtures", mode="repair", ablations=["full", "no_retry"])
client.benchmarks().runs()
client.benchmarks().load(run.manifest.run_id)
```

`investigate(..., use_graph=False)` and `repair_and_validate(..., features=RepairFeatures(...))`
expose the ablation flags. The M1 placeholder `benchmark(suite)` method, which
returned a blocked task record, was replaced by `benchmarks()`. The API
(`repoagent.api.app.create_app`) accepts an injected `ApiContext` holding the
client, policy, job queue, job store, and provider.

## Web workflows and LangChain adapters

```python
client = RepoAgent(settings=Settings(_env_file=".env"))
flows = client.workflows()  # optional: loader=callable(url) -> RepositoryHandle
found = flows.discover("https://github.com/owner/repo", progress=print)
verified = VerifiedIssue.from_report(found.report, found.report.candidates[0].id)
fixed = flows.repair(
    found.repository.source, verified.to_issue(), execute=False, handle=found.repository
)
retriever = client.langchain_retriever("./project")  # LangChain BaseRetriever
```

`discover` never repairs. `VerifiedIssue` rejects anything not `VERIFIED`.
`progress` receives `(stage_key, StageStatus, detail)`. Every workflow runs
under `WorkflowLimits.from_settings` (LLM calls, tokens, task deadline,
candidate cap, existing loop limits). Any LangChain chat model can be passed as
`provider=LangChainChatProvider(model)`, and any LangChain `Embeddings` as
`RepoAgent(embedding_provider=LangChainEmbeddingProvider(emb, name=..., dimension=...))`.
