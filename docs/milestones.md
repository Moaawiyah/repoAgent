# Milestone implementation roadmap

M1, M2, and M3 are implemented. Complete and validate each milestone before
advancing. All development gates: passing pytest, Ruff lint/format, >85%
statement coverage, and <=150 physical lines per Python file. Use meaningful
unit/integration tests.

| Milestone | Implementation | Acceptance evidence |
| --- | --- | --- |
| M1 foundation | Package, configuration, domain input/task/event models, CLI, SQLite TaskStore, metadata logging, docs and CI. | Offline tests for persistence, transactions, CLI, invalid inputs and inert execution boundaries; built-wheel smoke test. |
| M2 ingestion | Public GitHub clone/local copy, selected commit, isolated snapshots, ignore-aware discovery, language/file classification, README/docs/config/tests/history extraction, Python AST and structural chunk metadata. | Unfamiliar synthetic Git/local fixtures; original trees unchanged, commit fidelity, nested ignore rules, symlink/path/size rejection, AST/chunk line accuracy. |
| M3 retrieval | BM25, real embeddings/vector adapter, metadata filters, reciprocal-rank fusion, reranker, query decomposition and strategies A–D. | Deterministic retrieval fixtures and real embedding integration; measured Recall@K/MRR on labeled tasks, no fake vectors described as semantic search. |
| M4 graph | Dependency/import/call/inheritance/reference graph, neighborhood expansion, strategy E. | Known graph fixtures including dynamic/unresolved references; bounded expansion, deterministic results, retrieval comparisons. |
| M5 investigation | Budgeted context, tests/docs/history inclusion, typed investigator, evidence-grounded localization, provider protocol and OpenAI-compatible adapter. | Validated structured responses, evidence IDs/spans, missing-provider failures, mocked offline tests and separately labeled real runs. |
| M6 repair | Developer/reviewer agents, minimal unified diffs, safe patch application to disposable snapshots. | Traversal/symlink/binary/invalid patch rejection, unrelated-change review, reproducible diffs; output remains unvalidated until M7. |
| M7 validation | Docker sandbox, controlled dependency preparation, baseline and patched pytest/Ruff/coverage, regression detection, resource limits. | Sandbox integration tests, timeout/cleanup/secrets restrictions, baseline comparison and newly failing test detection. |
| M8 retry | Persist attempts, analyze failures, revise retrieval/context/hypotheses, bounded retry loop. | A repair requiring new evidence, termination on limits/repeated attempts, complete attempt histories. |
| M9 benchmarks | Synthetic suite, BugsInPy adapter, SWE-bench/Verified subset adapters, strategy comparison and exports. | Real task runs with dataset/model/revision/configuration provenance and raw artifacts; no fabricated scores. |
| M10 product | FastAPI over shared application services, background jobs, events, dashboard, deployment. | CLI/API behavior parity, durable job lifecycle, API authorization and deployment-specific isolation checks; dashboard follows engine validation. |

## Evaluation measures

Record Recall@K, MRR where labels allow it, correct-file and correct-symbol
localization, root-cause accuracy where independently labeled, patch generation,
test pass and regression-free repair rates, overall solve rate, average attempts,
estimated/measured token usage, and execution time. Preserve denominators and
unavailable measurements. Use the same tasks/configuration budgets for retrieval
strategies A–E. Benchmark ground truth belongs only to evaluators.

## Future API surface

FastAPI adapters will expose `POST /repositories`, `POST /repositories/{id}/index`,
`POST /tasks`, and `GET /tasks/{id}` with `/events`, `/patch`, and `/evaluation`
subresources. No HTTP server is implemented or required by M1.

## M2 delivered

M2 is implemented: local `RepositorySource` validation, ignore-aware and
symlink-safe `FileDiscovery` (honors `.gitignore`), `PythonAnalyzer` using the
standard `ast` module (modules, classes, functions, methods, async,
parameters, annotations, decorators, docstrings, line ranges), conservative
`ImportClassifier` (internal/stdlib/external/unknown), deterministic
`RelationshipBuilder` (imports, inheritance, containment, definitions), and
the `RepositoryAnalyzer` orchestration returning a typed `RepositoryAnalysis`.
The CLI `analyze <path>` command presents a summary or `--json` structure;
per-file syntax/encoding/size/read errors are recorded without aborting.
GitHub cloning and commit selection remain deferred to later ingestion work.

## M3 delivered, limitations, and next step

M3 is implemented: `CodeChunker` produces deterministic structure-aware
chunks (functions, methods, class preambles without duplicated method bodies,
and module-level residual code) with stable identities derived from
repository, file, qualified symbol, and source hash; `BM25Retriever` provides
lexical search over identifier-aware tokenization (snake_case/CamelCase
splitting that preserves whole identifiers); `HashingEmbeddingProvider`
provides deterministic offline embeddings over tokens and character
trigrams; `LocalVectorStore` provides cosine similarity behind the
`VectorStore` protocol; `HybridRetriever` fuses lexical and semantic rankings
with Reciprocal Rank Fusion; an optional deterministic `KeywordOverlapReranker`
reorders candidates; `IndexService`/`SearchService` orchestrate indexing and
search behind the SDK facade; `JsonIndexStore` persists snapshots under the
data directory; and `RetrievalEvaluator` measures Recall@K, MRR, HitRate@K,
and Precision@K per strategy from real retrieval runs.

Remaining M3 gaps: the local hashing provider captures lexical/sub-word
similarity, not vendor semantic embeddings (the provider protocol is the
seam); the vector store is in-memory and rebuilt from the persisted snapshot
per search; no incremental indexing, caching, BM25 persistence, reranker
models, query decomposition, or metadata filters yet; evaluation cases are
supplied as JSON data rather than bundled labeled suites.

Next: **M4 graph** — dependency/import/inheritance/reference graph and
neighborhood expansion over M2 relationships, evaluated with the M3 framework
as strategy E against strategies A–D. Keep all target execution deferred to
M7.
