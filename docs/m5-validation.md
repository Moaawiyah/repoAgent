# M5 implementation and validation report

M5 implementation and offline validation are complete. Live Groq validation is
pending a private API key; no live model success or accuracy is claimed.
The implementation was completed in the renamed `repoAgent` checkout.
No commits, pushes, target execution, patches, or M6 functionality were performed.
The unrelated `session-ses_f654.md` was preserved.

## Architecture and SDK

1. **Dependencies:** LangGraph **1.2.11** (`>=1.2.11,<2`), Groq **1.7.0**,
   OpenAI **3.13.0**, with `uv.lock` updated. Adapters use official SDKs.
2. **State:** typed repository/issue/task identity, limits, issue analysis,
   pending/next/executed queries, deduplicated source evidence, hypotheses,
   iteration, confidence, termination, error, usage, report, and observable trace.
3. **Nodes:** analyze_issue, plan_search, retrieve, assess_evidence, refine,
   hypothesize, evaluate, report. LangGraph controls scheduling and termination.
4. **Conditional edges:** assessment loops through refine when evidence is weak;
   evaluation loops through refine when a hypothesis needs confirmation. Failure,
   exhausted budgets, no evidence, or sufficiently supported confidence ends a run.
5. **Tools:** automatic search_code through SearchService/hybrid_graph; bounded
   snapshot-only inspect_symbol, inspect_neighbors, inspect_file helpers are also
   available. The graph currently selects searches, not those inspection helpers.
6. **Provider architecture:** SDK composition → application service → provider
   protocol → Groq/OpenAI official adapter. No model credentials are hardcoded.
   No production fake provider. Synchronous M5 calls have timeouts and no retries.
7. **Structured models:** IssueAnalysis, SearchPlan, EvidenceAssessment,
   HypothesisSet, InvestigationDecision, InvestigationReport. Exact JSON,
   field bounds, and extra-field rejection validate model responses.
8. **Evidence:** stable chunk/repository IDs, source path/symbol/lines/snippet,
   retrieval source/rank, graph paths, assessed relevance and concise rationale.
   Reranking now retains graph provenance; snapshots/retrievers are cached per run.
9. **Hypotheses:** explicit supporting/contradicting citations, affected symbols,
   alternatives, status, open questions, and bounded confidence. Invented citations
   are rejected; unsupported symbols/uncited hypotheses cannot become accepted
   causes. Evidence assessment and hypothesis evaluation must agree before a
   high-confidence termination. Confidence is uncalibrated.
10. **Limits:** iterations, total unique queries, evidence items, tool calls,
    source characters, output tokens, timeout, and LangGraph recursion backstop.
    Incomplete and provider-error reports retain explicit termination reasons.
11. **Prompt boundary:** repository content, issue text, and previous model output
    are untrusted JSON data separate from system instructions. No command, write,
    execution, browser, commit, or patch tool exists. This cannot guarantee that
    a model will never be semantically misled.
12. **Storage/export:** atomic JSON report and trace artifacts under application
    data; safe Obsidian investigation notes outside the target. Neither store
    contains hidden chain-of-thought. M1 SQLite task APIs remain separate.

## Executed validation

Local Python: **3.13.0**. CI is configured for **3.12 and 3.13**; remote CI was not run.

| Command/check | Observed result |
| --- | --- |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed; 163 formatter-managed files unchanged |
| `uv run pytest` | 298 passed, 1 skipped |
| `uv run pytest --cov=repoagent --cov-report=term-missing` | 298 passed, 1 skipped |
| `uv run python scripts/check_quality.py` | Passed; maximum Python length 150 |
| `uv build` | Wheel and source distribution built |
| Installed-wheel smoke | Public imports, py.typed, CLI help/version, SDK indexing, LangGraph partial-report persistence passed |
| Offline CLI manual fixture | Readable and JSON output, two retrieval rounds, actual source references/graph paths, target unchanged |

Statement coverage: **3065 / 3131 = 97.8920%**, covering production modules and the
quality scripts. The skipped existing discovery test reports “root-specific
discovery behavior.” No coverage exclusions or threshold reductions were added.

An initial offline wheel installation failed because dependency wheels were not
cached. Downloading those dependencies allowed the isolated installation and
smoke tests to pass. The final rebuilt wheel was reinstalled and checked again.

The starting tree contained partial M5 work: the baseline had an import-lint
failure and 16 test collection errors. These were resolved; existing M1–M4 tests
pass. The public `RepoAgent.evaluate(...)` entry point remains available. Task
service composition was extracted to keep the facade below the 150-line limit.

## Investigation tests and measured benchmark

Added tests cover immediate evidence, iterative retrieval, hypothesis-driven
re-search, maximum rounds, multiple hypotheses, no evidence, malformed output
at each model stage, total query/tool/evidence budgets, source prompt boundaries,
fabricated citations, unsupported symbols, contradictory evidence, confidence
constraints, SDK adapter mappings/errors, durable reports, export traversal and
symlink rejection, JSON failure exit codes, and forbidden subprocess execution.
Deterministic providers live only in `tests/support/`.

Two controlled benchmark repositories cover uppercase-email login and exact-stock
reservation. Labels stay in the evaluator; precise localization requires primary
supporting evidence matching the expected file and symbol.

| Offline test-provider metric | Measured value |
| --- | --- |
| Tasks | 2 |
| Mean relevant file recall | 1.0 |
| Mean relevant symbol recall | 1.0 |
| Exact primary-citation localization | 2/2 |
| Mean investigation iterations | 2.0 |
| Mean retrieval calls | 2.0 |

These are **scripted routing/evaluator checks, not AI accuracy results**. Recall
uses the final relevant-evidence set across rounds, not a single Recall@K ranking.
Live Groq benchmark results and confidence calibration are **unavailable**.

The offline manual CLI trace searched `email login lookup`, assessed missing
information, refined to `email lookup comparison iteration 1`, and searched again.
Actual evidence included `AuthService.login`, `UserRepository.find_by_email`, and
`normalize_email`. One preserved graph path was
`app.auth.controller.login_route → calls → app.auth.service.AuthService.login`.
Manual artifacts are in `/private/tmp/repoagent-m5-manual/report.txt` and
`report.json`; they explicitly use the fixture provider.

## Live configuration and remaining limitations

Groq is selected with model `openai/gpt-oss-20b`. At final verification, no private
`.env` existed and this process had no configured API key. A key found in the
tracked example was removed; it should be rotated. Automatic review rejected
creating a second credential copy in a temporary file, and that copy was not made.
Set the replacement key in ignored `.env` and run the README's explicit
`--env-file .env` command to complete live validation.

Existing retrieval uses hashing embeddings and keyword reranking. Static graph
relationships can be ambiguous; indexed source can be stale and snippets are
bounded. Investigation does not verify behavior through execution. Reports are
persisted on completion; crash-resumable checkpoints, background workers, SQLite
investigation task integration, arbitrary inspection-tool selection, and remote
repository ingestion are not implemented by M5.

Recommended next milestone: **M6 — typed Developer/Reviewer outputs, minimal patch
artifacts, and safe isolated patch application**. Keep patches unvalidated until
M7 provides sandbox execution. No M6 functionality was implemented here.

## Files created

The list includes pre-existing partial M5 files completed during this task.

- `docs/m5-investigation.md`
- `scripts/benchmark_investigation.py`
- `src/adapters/investigation_store.py`
- `src/agent/__init__.py`
- `src/agent/discovery.py`
- `src/agent/evaluation.py`
- `src/agent/evidence.py`
- `src/agent/investigator.py`
- `src/agent/prompts.py`
- `src/agent/reasoning.py`
- `src/agent/reporting.py`
- `src/agent/routing.py`
- `src/agent/shared.py`
- `src/agent/state.py`
- `src/ai/__init__.py`
- `src/ai/chat.py`
- `src/ai/groq_provider.py`
- `src/ai/models.py`
- `src/ai/openai_provider.py`
- `src/ai/provider.py`
- `src/ai/structured.py`
- `src/application/investigation.py`
- `src/cli/investigate_cli.py`
- `src/cli/investigation_render.py`
- `src/domain/evidence.py`
- `src/domain/investigation.py`
- `src/domain/investigation_limits.py`
- `src/domain/issue_analysis.py`
- `src/evaluation/investigation.py`
- `src/export/investigation.py`
- `src/sdk/investigation.py`
- `src/sdk/tasks.py`
- `src/tools/__init__.py`
- `src/tools/inspection.py`
- `src/tools/models.py`
- `src/tools/repository.py`
- `tests/__init__.py`
- `tests/fixtures/auth_bug/README.md`
- `tests/fixtures/auth_bug/app/__init__.py`
- `tests/fixtures/auth_bug/app/auth/__init__.py`
- `tests/fixtures/auth_bug/app/auth/controller.py`
- `tests/fixtures/auth_bug/app/auth/service.py`
- `tests/fixtures/auth_bug/app/models.py`
- `tests/fixtures/auth_bug/app/users/__init__.py`
- `tests/fixtures/auth_bug/app/users/repository.py`
- `tests/fixtures/auth_bug/pyproject.toml`
- `tests/fixtures/auth_bug/tests/__init__.py`
- `tests/fixtures/auth_bug/tests/test_login.py`
- `tests/fixtures/inventory_bug/inventory.py`
- `tests/fixtures/investigation_cases.json`
- `tests/integration/test_investigate_cli.py`
- `tests/support/__init__.py`
- `tests/support/providers.py`
- `tests/support/scripted.py`
- `tests/unit/test_agent_graph.py`
- `tests/unit/test_agent_tools.py`
- `tests/unit/test_ai_providers.py`
- `tests/unit/test_export_investigation.py`
- `tests/unit/test_injection_defense.py`
- `tests/unit/test_investigation_benchmark.py`
- `tests/unit/test_investigation_cases.py`
- `tests/unit/test_investigation_challenges.py`
- `tests/unit/test_investigation_models.py`
- `tests/unit/test_investigation_storage.py`
- `tests/unit/test_provider_adapters.py`
- `docs/m5-validation.md`

## Files modified

- `.env.example`
- `.github/workflows/ci.yml`
- `README.md`
- `docs/architecture.md`
- `docs/milestones.md`
- `docs/sdk.md`
- `pyproject.toml`
- `src/__init__.py`
- `src/application/searching.py`
- `src/cli/main.py`
- `src/cli/runtime.py`
- `src/config.py`
- `src/domain/errors.py`
- `src/retrieval/rerank.py`
- `src/sdk/client.py`
- `tests/unit/test_sdk_injection.py`
- `uv.lock`
