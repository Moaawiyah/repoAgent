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
