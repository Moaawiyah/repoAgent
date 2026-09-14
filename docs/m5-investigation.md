# M5 investigation architecture

`RepoAgent.investigate` composes `InvestigationApi`, `InvestigationService`, and
`InvestigatorAgent`. The service loads the M3/M4 index once and constructs a
bounded repository toolkit. LangGraph owns node scheduling and conditional edges;
only `agent/investigator.py` imports its orchestration types. Domain models do
not depend on LangGraph or a vendor SDK.

## State and routing

`InvestigationState` is a Pydantic model holding repository/task identity, an
`Issue`, limits, issue analysis, pending/next/executed queries, deduplicated evidence,
hypotheses, iteration, confidence, termination, report, error, usage, and trace.
State contains bounded snippets rather than full repository contents.

| Node | Responsibility | Next step |
| --- | --- | --- |
| analyze_issue | Extract symptoms, concepts, identifiers, questions | plan_search or failure report |
| plan_search | Generate bounded, distinct queries | retrieve or report |
| retrieve | Search through SearchService; preserve chunk and graph provenance | assess_evidence |
| assess_evidence | Assess source relevance and remaining unknowns | refine, hypothesize, or report |
| refine | Select new queries under remaining budgets | retrieve |
| hypothesize | Validate explicit citations and affected symbols | evaluate or report |
| evaluate | Challenge hypotheses; cap weak/contradicted confidence | refine or report |
| report | Assemble evidence, alternatives, trace, and explicit termination | END |

Defaults: 3 rounds, 8 total queries, 12 evidence items, 30 tool calls, 5 hits per
query, 12,000 source characters per prompt, 2,000 maximum completion tokens, and
60 seconds per provider call. Each setting is validated. Query deduplication and
LangGraph's bounded recursion backstop supplement the budgets. Provider retries
are zero in M5: quota and transport failures remain visible, not catch-all retries.

A round can execute several queries. `iterations`, `tool_calls`, and `queries`
therefore measure different things. The final report is stored atomically in the
application data directory, outside the target repository. Final artifacts can be
read with `InvestigationStore.get(UUID)`; resumable checkpoints and SQLite
investigation task integration are not implemented.

## Providers and outputs

`LLMProvider.complete(CompletionRequest) -> CompletionResult` carries a system
message, JSON data, output schema, validated content, and usage metadata.
`structured_generate` accepts only exact JSON validated by the requested model.
The concrete Groq and OpenAI adapters use official SDK clients, structured JSON
schemas, timeouts, and sanitized errors. No SDK types leak into services or domain
models. Credentials use `SecretStr`; construction is lazy and CLI logging uses
allowlisted metadata.

Typed outputs include `IssueAnalysis`, `SearchPlan`, `EvidenceAssessment`,
`HypothesisSet`, and `InvestigationDecision`. `RootCauseHypothesis` retains
supporting/contradicting evidence IDs, affected symbols, confidence, open questions,
and status. Unknown citations are rejected; uncited or unsupported hypotheses
are discarded. A strengthened evaluation with direct cited source is required
for high confidence. These checks validate provenance, not the truth of model
reasoning. Confidence remains uncalibrated.

## Retrieval, evidence, and safety

`RepositoryToolkit.search_code` delegates to `SearchService.search` with reranking
and hybrid-graph retrieval. Search caches index/retriever construction for the
investigation. Reranking preserves structural provenance, correcting the earlier
loss of graph paths at that boundary. File/symbol/neighborhood helpers read only
indexed chunks and graph objects; they cannot access arbitrary live paths.

`EvidenceItem` records repository ID, chunk ID, file, qualified symbol, start/end
lines, snippet, query, retrieval source/rank, graph hops, relevance, and rationale.
Evidence IDs are stable chunk IDs; duplicates do not inflate evidence counts.
Snippet budgets are shared across items, and prompt data marks further truncation.
A reference alone is not proof. Graph paths describe static relationships, not
observed execution. Partial graph resolution remains an inherited M4 limitation.

Issue text and repository content are untrusted data, encoded separately from
trusted instructions. All model outputs are also untrusted. The agent has no
shell, execution, browser, write, commit, or patch tool. Export and report writes
are application operations restricted outside the target tree. Obsidian notes
reference the existing M4 graph vault; create that vault before adding notes if
resolved wikilinks are desired. No hidden chain-of-thought is requested or stored.

## Validation and limitations

Offline tests use deterministic providers only under `tests/support/`. They run
actual LangGraph and actual retrieval, covering both kinds of refinement loop,
empty evidence, alternatives, exhausted budgets, malformed outputs, invented
citations, confidence constraints, provider SDK mapping, persistence, CLI JSON,
source immutability, and export path checks. The labeled benchmark isolates
expected files and symbols from the agent and requires precise primary citations.
Scripted test scores are not AI performance measurements.

Source is the existing M2/M3 local index, not a revision-pinned Git checkout. Reindex
when it changes. The default embedding provider uses hashing and the reranker
uses keyword overlap. Live model calls are synchronous. Token estimates use
characters/4 and are labeled estimates; provider counts are separate. M5 does not
run target tests, verify behavior dynamically, apply repairs, or expose FastAPI.

Official references: [LangGraph graph API](https://docs.langchain.com/oss/python/langgraph/graph-api),
[Groq structured outputs](https://console.groq.com/docs/structured-outputs),
[Groq quotas](https://console.groq.com/docs/rate-limits).
