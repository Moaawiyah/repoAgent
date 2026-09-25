# Benchmark methodology and measured results (M8)

Every number on this page was copied from run artifacts committed under
[`benchmarks/results/`](../benchmarks/results/) (`manifest.json`,
`results.jsonl`, `summary.json`). Values that were not measured are marked
**not measured**. None are estimated.

## Infrastructure

```text
suite JSON ──► BenchmarkRunner ──► per task: materialize ─► index ─► labels
                                     │
                                     ├─ retrieval   (LLM-free Recall@K / MRR / Hit@K per strategy)
                                     ├─ investigate (Investigator → localization vs. labels)
                                     └─ repair      (M7 loop + evaluator-only hidden tests)
                                                   ▼
                         JsonlResultStore: manifest.json · results.jsonl · summary.json
```

- **Tasks** (`BenchmarkTask`) carry the repository (a local fixture or a pinned
  GitHub commit), the issue text, expected files and symbols, an optional gold
  patch, validation criteria (fail-to-pass and pass-to-pass tests, hidden
  tests), and the expected outcome. Labels, gold patches, and hidden tests
  never enter agent context.
- **Adapters** stay outside the core agent. `benchmark-import bugsinpy`
  converts a local BugsInPy checkout. `benchmark-import swebench` converts
  SWE-bench JSON or JSONL exports. When a gold patch exists, expected symbols
  are derived deterministically: the innermost function or method overlapping
  each changed hunk, excluding tests.
- **Materialization** fetches pinned commits with host `git`, used only as a
  data transport. Hooks, symlinks, LFS filters, and non-HTTPS protocols are
  disabled. Only `https://github.com/<owner>/<repo>` sources with full
  40-character SHAs are accepted. `.git` is removed after checkout.
- **Experiments** reuse the real system behind feature flags (`RepairFeatures`):
  `full`, `no_graph` (hybrid retrieval without graph expansion), `no_reviewer`
  (static validation still gates patches), `single_pass` (one investigation
  iteration), and `no_retry` (one sandbox attempt, no re-investigation).
- **Hidden tests**: after a `VALIDATED` repair, an independent evaluator run
  applies the agent's final patch plus the hidden tests in a fresh Docker
  sandbox. A task counts as a success only if that full pytest run passes.
- **Failure categories** are assigned deterministically: setup, provider,
  localization, insufficient evidence, incorrect root cause, patch generation,
  review rejection, patch apply, test failure, regression, timeout, sandbox,
  max attempts, validation unavailable.
- **Reproducibility**: each manifest records the RepoAgent version, commit, and
  dirty flag; the suite SHA-256; task IDs; the experiment configuration
  (mode, flags, K, attempts, timeout); the provider and model; the embedding
  configuration; the sandbox image; Python and platform; and timestamps.
  Secrets are never recorded; a test verifies that an API key is absent from
  the manifest.

## Stages

| Stage | Tasks | Source | Issue text | Repair execution |
| --- | --- | --- | --- | --- |
| A — internal fixtures | 6 | `benchmarks/fixtures.json`, synthetic repositories in `tests/fixtures/` | Hand-written bug reports | Supported (visible tests plus hidden tests) |
| B — BugsInPy subset | 10 (PySnooper 1–3, httpie 1–2, cookiecutter 1–2, tqdm 1–2, thefuck 1) | soarsmu/BugsInPy metadata | **Synthesized** from failing test names (BugsInPy has no issue text) | Not supported (per-project Python environments are not prepared) |
| C — SWE-bench Verified subset | 9 (`pallets__flask-5014`, `psf__requests-{1142,1724,1766,1921,2317,2931,5414,6028}`) | `princeton-nlp/SWE-bench_Verified`, rows fetched via the Hugging Face datasets API | Original problem statements (truncated to 6000 characters) | Not supported (no per-instance environment images) |

Stage A fixtures were verified in the real Docker sandbox before use. On the
buggy code, visible tests pass and hidden tests fail. With a reference patch,
the hidden tests pass. This held for all 6 tasks. The Stage B and C subsets
were chosen for small repository size, not for difficulty, so they are **not**
representative samples of either benchmark.

## Retrieval strategy comparison (LLM-free, measured)

The query is the issue text. Expected items are the labeled files plus derived
symbols. Recall@K counts distinct expected items within the top K. MRR uses
the first relevant rank. Hit@K means at least one expected item appears in the
top K. Embeddings use the local hashing provider (lexical and sub-word, not a
semantic model).

**K = 5**

| Stage | BM25 R@5 / MRR | Vector R@5 / MRR | Hybrid R@5 / MRR | Hybrid+Graph R@5 / MRR | Hybrid+Graph Hit@5 |
| --- | --- | --- | --- | --- | --- |
| A fixtures (6) | 1.000 / 0.700 | 0.667 / 0.492 | 1.000 / 0.622 | 1.000 / **0.722** | 1.000 |
| B BugsInPy (10) | 0.125 / 0.200 | 0.000 / 0.000 | 0.087 / 0.083 | **0.450 / 0.350** | 0.700 |
| C SWE-bench Verified (9) | 0.278 / 0.198 | 0.333 / **0.356** | 0.444 / 0.333 | **0.463** / 0.261 | 0.667 |

**K = 10**

| Stage | BM25 R@10 / MRR | Vector R@10 / MRR | Hybrid R@10 / MRR | Hybrid+Graph R@10 / MRR |
| --- | --- | --- | --- | --- |
| A fixtures | 1.000 / 0.700 | 1.000 / 0.515 | 1.000 / 0.622 | 1.000 / **0.722** |
| B BugsInPy | 0.300 / 0.245 | 0.158 / 0.043 | 0.125 / 0.066 | **0.454 / 0.274** |
| C SWE-bench Verified | **0.667** / 0.246 | 0.444 / 0.384 | 0.556 / 0.331 | 0.556 / **0.406** |

Runs: A `20260914T232912Z-2dc7e9` and `20260914T232948Z-aa01bd`; B
`20260914T232912Z-d9658c` and `20260914T232949Z-57690c`; C
`20260914T232928Z-479641` and `20260914T232953Z-fe5557`.

What these measurements show:

- On BugsInPy, graph expansion was the strongest strategy at both K values.
  Recall@5 was 0.450 versus 0.087 for hybrid. The synthesized issue text names
  failing tests, and graph edges connect test-adjacent symbols to library code.
- On the SWE-bench subset, graph expansion **did not** consistently help. It
  had the best Recall@5 but a lower MRR@5 than vector or hybrid. At K = 10,
  BM25 had the highest recall.
- The fixtures are too small to discriminate strategies on recall, because
  every strategy except vector saturates. Hybrid+Graph had the best MRR.
- Sample sizes are 6, 10, and 9 tasks, and no confidence intervals are
  reported. Treat these as directional results, not statistically established
  ones.
- Hybrid+Graph MRR can decrease as K grows because graph expansion depth
  scales with `top_k`, which changes the ranking.
- A reproducibility bug was found and fixed during M8. Chunk IDs used as
  ranking tie-breakers included a hash of the checkout's absolute path, so
  results depended on the data directory location. The numbers above were
  produced after the fix and were re-run in a second location with identical
  results.

## Token efficiency (measured prompt size)

The same two deterministic repair runs were measured before and after focusing
the prompt context: auth fixture (two sandbox attempts) plus inventory fixture.
The prompts are the real prompts RepoAgent builds; only the model responses are
scripted. These figures count **characters** sent (system plus user). They are
not provider tokens.

| Stage | Before | After | Change |
| --- | --- | --- | --- |
| `patch_proposal` (3 calls) | 16,779 | 9,278 | −45% |
| `patch_review` (2 calls) | 12,883 | 4,407 | −66% |
| `evidence_assessment` (2) | 10,736 | 7,746 | −28% |
| `hypothesis_set` (2) | 11,068 | 8,428 | −24% |
| `investigation_decision` (2) | 11,783 | 9,143 | −22% |
| **Total (all stages)** | **69,112** | **44,413** | **−35.7%** |

Changes:

- Prompts send evidence provenance plus the snippet instead of full internal
  records (no chunk IDs, repository IDs, ranks, or originating queries).
- Graph paths are sent as compact strings.
- Developer evidence is deduplicated, with cited evidence first.
- The Reviewer sees only evidence cited by the root cause or located in files
  the patch changes (at most 6 items).
- The Reviewer no longer receives the previously failed diff.

A regression test enforces these properties. Repair metrics also record
provider-reported input and output tokens and per-stage call counts.

## LLM-dependent results

### Investigation localization with ablation (measured)

Run `20260914T234945Z-dfa3f8`: Stage A fixtures (6 tasks), Groq
`openai/gpt-oss-20b`, investigate mode, ablations `full` and `no_graph`, one
run per task. Success means the primary hypothesis cites evidence in a gold
file.

| Metric | full (graph retrieval) | no_graph (hybrid only) |
| --- | --- | --- |
| Tasks attempted | 6 | 6 |
| File localization (primary hypothesis) | 2/6 (33.3%) | 4/6 (66.7%) |
| Symbol localization | 2/6 (33.3%) | 4/6 (66.7%) |
| Average LLM calls | 4.50 | 4.83 |
| Average retrieval calls | 6.33 | 6.33 |
| Average input / output tokens | 6,167 / 3,590 | 6,262 / 3,493 |
| Average runtime per task (s) | 68.7 | 81.8 |
| Failures | insufficient_evidence 3, provider_error 1 | provider_error 2 |

Per task:

- `full` localized inventory and pagination. It ended with insufficient
  evidence on auth, slugify, and config (`max_queries`), and hit a provider
  error on cache.
- `no_graph` localized auth, inventory, slugify, and pagination, and hit
  provider errors on config and cache.

Interpretation:

- In this run the graph-free configuration localized more tasks, which is the
  opposite direction from the retrieval-only fixture comparison.
- With 6 tasks, one sample per configuration, and a nondeterministic model,
  this difference is **not** statistically meaningful. A proper ablation needs
  repeated runs.
- The `full` failures were mostly the model declining to reach confidence,
  not retrieval misses. Hit@5 was 1.0 for every strategy on these fixtures.
- Groq enforced 8,000 tokens per minute during this run (68 rate-limit waits),
  which inflates runtimes.

Provider errors were diagnosed afterwards with typed error reasons:

- Groq returned `400 json_validate_failed`, meaning the model produced JSON
  that violated the required schema.
- The model occasionally mistyped an evidence ID. RepoAgent now discards only
  the mistyped citation instead of failing the stage. This change was already
  in place for this run.

### Repair and remaining ablations

| Metric | Value |
| --- | --- |
| Validated repairs / repair success rate (hidden tests) | **not measured** |
| Average repair attempts, sandbox time | **not measured** |
| `no_reviewer`, `single_pass`, `no_retry` ablations | **not measured** |
| Repair failure breakdown | **not measured** |

Two repair runs were started and stopped without complete results. Their
partial records are not reported as results. The first run failed on schema
rejections and rate limits. The second found the account's Groq **daily**
quota for `openai/gpt-oss-20b` (200,000 tokens/day) exhausted by the runs
above.

As a result, RepoAgent now:

- throttles proactively (`REPOAGENT_LLM_TOKENS_PER_MINUTE`,
  `REPOAGENT_LLM_REQUESTS_PER_MINUTE`);
- retries 429s within a bounded budget;
- fails fast when the server's requested delay exceeds
  `REPOAGENT_LLM_RATE_LIMIT_MAX_WAIT`;
- records typed failure reasons.

Offline tests cover every repair path with a deterministic provider and a fake
sandbox; those tests exercise plumbing and are not model results. To produce
the missing values once quota is available:

```sh
uv run repoagent --env-file .env benchmark fixtures --mode repair \
  --ablation full --ablation no_reviewer --ablation no_retry --max-attempts 3
uv run repoagent --env-file .env benchmark fixtures --mode investigate \
  --ablation full --ablation no_graph --ablation single_pass
uv run repoagent benchmark-report <run_id>
```

## Retrieval improvements, 2026-09 (measured)

Four suites, 45 tasks in total: A fixtures (6), B BugsInPy (10), C SWE-bench
Verified subset (9), and the new real-repair suite D (20, see below). The
query is the issue text; K = 5. "Pooled" means the mean over all 45 tasks,
not the mean of suite means. Two embedding configurations were measured:
the offline hashing provider and a semantic model served locally
(`openai:qwen3-embedding:0.6b` through Ollama's OpenAI-compatible endpoint).

Runs (all under `benchmarks/results/`): hashing
`20260925T043438Z-b6382c` (A), `20260925T043439Z-0a3ff5` (B),
`20260925T043455Z-be1fe7` (C), `20260925T043526Z-baac03` (D); semantic
`20260925T025635Z-e69e6d` (A), `20260925T025708Z-64624c` (B),
`20260925T032856Z-4bee0e` (C), `20260925T035708Z-7be51b` (D). In the
semantic runs the `full` arm used the then-default `legacy` graph policy.
The tables below therefore name the policy explicitly.

### Embeddings and strategies (Recall@5 / MRR)

| Suite | BM25 | Hashing vector | Semantic vector | BM25 + semantic (hybrid) | BM25 + semantic + graph (`calls_inherits`) |
| --- | --- | --- | --- | --- | --- |
| A fixtures (6) | 1.000 / 0.700 | 0.667 / 0.492 | 0.667 / 0.506 | 0.833 / 0.486 | 1.000 / 0.667 |
| B BugsInPy (10) | 0.125 / 0.200 | 0.000 / 0.000 | 0.150 / 0.045 | 0.138 / 0.110 | 0.442 / 0.483 |
| C SWE-bench (9) | 0.278 / 0.198 | 0.333 / 0.356 | 0.333 / 0.287 | 0.444 / 0.343 | 0.278 / 0.259 |
| D real-repair (20) | 0.632 / 0.723 | 0.413 / 0.489 | 0.674 / 0.693 | 0.672 / 0.721 | **0.721 / 0.875** |
| **Pooled (45)** | 0.497 / 0.499 | 0.339 / 0.354 | 0.489 / 0.443 | 0.529 / 0.478 | **0.607 / 0.637** |

For comparison, hashing hybrid+graph (`calls_inherits`) pools to
0.566 / 0.544 (NDCG@5 0.402), and semantic hybrid+graph (`calls_inherits`)
to 0.607 / 0.637 (NDCG@5 0.425).

- Semantic vectors are much stronger than hashing vectors on real issue
  text: D Recall@5 is 0.674 vs 0.413, and pooled 0.489 vs 0.339.
- The full semantic pipeline (BM25 + semantic + graph) is the best pooled
  configuration and the best on D, the suite whose queries are real issues.
- On C it is not: plain hybrid wins there (0.444 vs 0.278 Recall@5). Graph
  expansion does not help every repository.
- The hashing provider remains the default because it is offline and
  deterministic. Semantic embeddings are opt-in (`REPOAGENT_EMBEDDING_PROVIDER=openai`).

### Graph expansion ablations (hybrid+graph, pooled over 45 tasks)

| Policy | Hashing R@5 / MRR / NDCG@5 | Semantic R@5 / MRR / NDCG@5 |
| --- | --- | --- |
| `legacy` (all edges, previous behavior) | 0.563 / 0.526 / 0.393 | 0.587 / 0.568 / 0.393 |
| **`calls_inherits` (new default)** | 0.566 / 0.544 / 0.402 | **0.607 / 0.637 / 0.425** |
| `focused` (calls+inherits, uncertain edges ×0.3) | **0.569 / 0.556 / 0.406** | 0.578 / 0.619 / 0.425 |
| `resolved_only` (no uncertain edges) | 0.556 / 0.534 / 0.392 | 0.569 / 0.561 / 0.385 |
| `seeds5` (expand top-5 seeds only) | 0.557 / 0.519 / 0.391 | 0.587 / 0.568 / 0.386 |
| `gated` (graph ×0.5 when BM25 and vector agree on #1) | 0.535 / 0.496 / 0.365 | 0.581 / 0.553 / 0.383 |
| `seeds5_gated` (seeds5 + gated + uncertain ×0.3) | 0.522 / 0.505 / 0.367 | not measured |
| `depth1` | 0.535 / 0.522 / 0.375 | not measured |
| `half_weight` (graph list ×0.5 in RRF) | 0.509 / 0.503 / 0.363 | 0.598 / 0.554 / 0.380 |
| no graph (hybrid) | 0.495 / 0.492 / 0.353 | 0.529 / 0.478 / 0.358 |

- Graph expansion improves pooled localization over plain hybrid under both
  embeddings. Most of the gain comes from BugsInPy, where the query names
  tests and CALLS edges lead from tests to library code.
- Dropping structural edges (CONTAINS, DEFINES, IMPORTS) is the selective
  change that helped. `calls_inherits` beats `legacy` on every pooled metric
  under both embeddings, so it is the new default (`REPOAGENT_GRAPH_POLICY`).
  Per suite it is not uniform: with hashing embeddings it is slightly worse
  than `legacy` on C (0.407 vs 0.463 Recall@5) and D (0.508 vs 0.533).
- The "avoid expansion when evidence is strong" heuristics (`gated`,
  `seeds5_gated`, `half_weight`) made results **worse** on pooled data. They
  are kept only as ablations.
- Down-weighting statically uncertain CALLS edges (`focused`) was the best
  choice with hashing embeddings and second-best with semantic ones. The
  difference from `calls_inherits` is within noise at this sample size.

### Reranking (hybrid+graph, pooled over 45 tasks unless noted)

Every reranker reorders a 20-candidate pool into the top 5, except
`keyword_topk`, which reorders only the top 5. That is how the Investigator
uses reranking.

| Reranker | Hashing R@5 / MRR | Semantic R@5 / MRR |
| --- | --- | --- |
| none | 0.566 / 0.544 (`calls_inherits`) | 0.587 / 0.568 (`legacy`) |
| keyword, top-5 only (Investigator) | 0.566 / 0.519 | D only: 0.708 / 0.808 vs 0.708 / 0.867 without |
| keyword, 20-candidate pool | 0.511 / 0.507 | 0.574 / 0.522 |
| semantic (embedding similarity fused with rank) | 0.557 / 0.484 | **0.667 / 0.613** |

- The keyword reranker is mostly another lexical signal and does not help.
  With a pool it hurts, and at top-5 it lowers MRR. It stays the
  deterministic default for tests.
- The semantic reranker only helps with semantic embeddings. There it gives
  the best pooled Recall@5 (0.667 vs 0.587) and the best D result
  (0.776 / 0.875). With hashing embeddings it is harmful, which is expected
  because it just re-applies the same lexical vectors.

**LLM listwise reranker (incomplete run).** The run with local
`qwen3:4b` (thinking disabled, 16k context) on suite D was stopped after 6
of 20 tasks to bound wall-clock time. It is reported here as incomplete,
not as a result. On those 6 tasks (semantic index, `legacy` policy, run
`20260925T043332Z-22e59f`), hybrid+graph went from Recall@5 / MRR
0.458 / 0.722 without reranking to 0.792 / 0.833 with it. It cost 3 LLM
calls and about 12k input tokens per task. BM25 and hybrid were unchanged
or slightly worse. This is promising but not established; it needs the
full suite and repeated runs.

## Stage D: real-bug repair suite

[`benchmarks/real_repair.json`](../benchmarks/real_repair.json) contains 20
real single-file bugs from 20 unfamiliar open-source repositories. They were
imported from `nebius/SWE-rebench` (filtered split) and range from 1k to 23k
Python LOC. Examples include sqlparse, idna, python-tabulate, boltons, lark,
fastkml, pynmea2, esper, sql-metadata, circuitbreaker, django-environ,
pyspellchecker, asgiref, svgpathtools, dissect.cstruct, borax, crosstl,
canopen, and pymap3d. Every task records:

- the repository and pinned 40-character commit;
- the original issue text;
- expected files (from the gold patch) and expected symbols (the innermost
  function or method overlapping each gold hunk);
- FAIL_TO_PASS and PASS_TO_PASS test IDs;
- hidden tests: the full contents of every test file after applying the
  upstream test patch. These are evaluator-only and never shown to the agent;
- the gold patch;
- a pinned environment: a digest-pinned image
  (`python@sha256:2d97f691…`, Python 3.9) plus the frozen requirements from
  SWE-rebench, which replace the project's declared ranges. Conda-built
  packages have no version in the freeze and stay unpinned by name.

**Verification before use (no LLM).** `repoagent benchmark-verify` runs each
task in its own pinned sandbox and admits it only if all three checks pass:

1. The visible suite passes on the buggy commit. M7 needs a green suite
   before it can mark a repair `VALIDATED`.
2. The hidden tests fail on the buggy code.
3. The gold patch plus the hidden tests pass.

54 candidates were checked; the full log with reasons is in
[`benchmarks/real_repair.verification.jsonl`](../benchmarks/real_repair.verification.jsonl).

| Outcome | Tasks |
| --- | --- |
| Verified and selected | 20 |
| Verified, not selected (repository under 750 LOC) | 5 |
| Excluded: visible suite fails on the buggy commit in the pinned environment | 21 |
| Excluded: a pinned wheel is not available for linux/arm64, or a requirement line is malformed | 8 |

This filter biases the suite toward projects with self-contained test
suites. The exclusions are recorded, not hidden.

**Reproduce:**

```sh
# rows: JSONL export of nebius/SWE-rebench (datasets-server /rows API)
uv run repoagent benchmark-import swerebench rows.jsonl --output candidates.json \
  --item andialbrecht__sqlparse-676 --item kjd__idna-83 ...   # image pinned by digest
uv run repoagent benchmark-verify candidates.json --output benchmarks/real_repair.json
uv run repoagent benchmark real_repair --mode retrieval --k 5
uv run repoagent --env-file .env benchmark real_repair --mode repair \
  --ablation full --ablation best_hypothesis --max-attempts 3
```

Repair results report every task, including failed ones. Each failure is
assigned both a fine-grained category and one of seven stages: `retrieval`,
`investigation`, `provider_schema`, `patch_generation`, `reviewer_rejection`,
`sandbox_setup`, or `validation_test`. Summaries also report first-attempt
successes, regressions, hidden-test success rate, LLM calls,
input and output tokens, and runtime. Each manifest records the
`sandbox_image_digest` and every task's pinned image.

### Stage D repair results (measured, local model)

Run `20260925T034754Z-b6ba84` used the full M7 pipeline with the local
`qwen3:4b` served by Ollama (16k context, `REPOAGENT_LLM_REASONING_EFFORT=none`).
Settings were hashing embeddings, the `legacy` graph policy, 3 attempts, and a
600 s command timeout. No paid API was used. Every task is reported.

| Metric | Value |
| --- | --- |
| Tasks attempted | 20 |
| Validated repairs / hidden tests resolved | **0 / 0** |
| First-attempt successes, regressions | 0, 0 |
| File / symbol localization (primary hypothesis, 19 measured) | 5.3% / 5.3% |
| Average LLM calls, input / output tokens | 4.0, 9,083 / 1,550 |
| Average runtime per task | 255 s |
| Failures by stage | investigation 12, provider_schema 5, retrieval 2, sandbox_setup 1 |

Where it broke:

- **Investigation (12).** Retrieval usually surfaced the right file (suite D
  hybrid+graph Recall@5 is 0.533 with hashing embeddings), but the
  Investigator ended without a supported hypothesis, so no patch was ever
  proposed. Traces showed two defects in hypothesis validation. A single
  mistyped evidence ID failed the entire stage as `provider_error`, and a
  hypothesis naming `ulabel` instead of `idna.core.ulabel` was discarded.
  Both are now fixed (see below).
- **Provider/schema (5).** The 4B model produced JSON that violated the
  stage schema, or a call timed out.
- **Retrieval (2).** The expected file was never in the evidence.
- **Sandbox/setup (1).** `pymap3d-66` has no pytest configuration that
  RepoAgent's static detector recognizes, so it cannot be validated.

**Fixes after this run and their status.** Unknown citations are now
discarded individually, the same way evidence assessment already handled
them. Shortened symbol names are grounded to the unique cited qualified
name. The new ablation `best_hypothesis`
(`RepairFeatures.require_confident_root_cause=False`) sends the best-ranked,
evidence-grounded hypothesis to the Developer when the investigation ends
on a budget. Sandbox validation and hidden tests remain the only arbiters.
A post-fix run (`full` + `best_hypothesis`) was **stopped after 1 of 20
tasks** to bound wall-clock time, so its effect on repair success is **not
measured**. On that one task, `best_hypothesis` produced 2 grounded
hypotheses and reached the Developer, whose patch output then failed
schema validation. An earlier pre-fix `best_hypothesis` run was also
stopped (2 tasks) and is not reported.

This measures the pipeline with a small local model. It says nothing about
repair capability with a stronger model. A 4B model rarely declares a
confident root cause, and the Developer's structured patch output is
demanding. To measure with a hosted model:

```sh
uv run repoagent --env-file .env benchmark real_repair --mode repair \
  --ablation full --ablation best_hypothesis --max-attempts 3
```


## Reproducing Stage B and C suites

```sh
git clone --depth 1 https://github.com/soarsmu/BugsInPy /tmp/BugsInPy
uv run repoagent benchmark-import bugsinpy /tmp/BugsInPy \
  --output benchmarks/generated/bugsinpy.json \
  --item PySnooper:1 --item PySnooper:2 --item PySnooper:3 --item httpie:1 \
  --item httpie:2 --item cookiecutter:1 --item cookiecutter:2 --item tqdm:1 \
  --item tqdm:2 --item thefuck:1

# SWE-bench Verified rows for the two repositories (Hugging Face datasets server)
for repo in psf/requests pallets/flask; do
  curl -sG https://datasets-server.huggingface.co/filter \
    --data-urlencode dataset=princeton-nlp/SWE-bench_Verified \
    --data-urlencode config=default --data-urlencode split=test \
    --data-urlencode "where=\"repo\"='$repo'" --data-urlencode length=100
done  # save rows[].row as JSONL, then:
uv run repoagent benchmark-import swebench rows.jsonl \
  --output benchmarks/generated/swe-bench-verified.json --item psf__requests-1142 ...

uv run repoagent benchmark benchmarks/generated/bugsinpy.json --mode retrieval --k 5
```

Generated suites and dataset exports are git-ignored. Only RepoAgent-authored
fixture suites and result artifacts are committed.
