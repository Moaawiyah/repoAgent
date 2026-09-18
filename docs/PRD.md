# Product Requirements: RepoAgent

Status document, not marketing copy. Claims here must match measured or
implemented behavior in `docs/milestones.md` and `docs/benchmarks.md`; when
they diverge, the code and the benchmark artifacts are the source of truth.

## 1. Problem

Fixing a bug in an unfamiliar Python repository requires: locating the
relevant code, forming a root-cause hypothesis grounded in evidence (not
guesswork), producing a minimal correct patch, and confirming the patch
doesn't regress anything — without ever risking the developer's working tree
or running untrusted code on their machine. Most "AI coding agent" demos skip
the isolation and verification steps and report success on the model's say-so.

## 2. Goal

Given a GitHub repository URL and either a bug description or nothing (audit
mode), produce an evidence-backed, sandboxed-validated outcome — a patch with
passing baseline/patched tests, or a set of classified findings — and show the
user exactly what evidence supports it, without ever modifying the source
repository or executing its code outside a hardened sandbox.

## 3. Users

- **A developer** with a bug report but unfamiliar with the codebase, who
  wants a starting patch plus the reasoning and evidence behind it, not a
  black-box diff.
- **A maintainer** who wants a repository audited for evidence-backed issues
  (resource leaks, broad exception handling, circular imports, risky
  subprocess usage, etc.) without asking an LLM to freely browse the tree and
  hallucinate findings.
- **An engineer evaluating RepoAgent itself**, who needs reproducible,
  honestly-labeled metrics rather than a demo cherry-picked to look good.

## 4. Non-goals

- Not a general-purpose autonomous coding agent — no arbitrary shell access,
  no free-form multi-file refactors, no execution of LLM-generated commands.
- Not multi-language. Python (AST-based) only; see [Limitations](#8-known-limitations-and-non-goals).
- Not a hosted multi-tenant SaaS. The API has no accounts, no rate limiting,
  no TLS termination — it is a local/demo service (`repoagent serve`).
- Not a replacement for CI. Sandbox validation runs pytest/Ruff once per
  attempt; it does not replace a project's full CI matrix.

## 5. Core workflows (implemented)

### 5.1 Repair

```
GitHub URL + issue description
  → fetch (hardened, read-only, isolated workspace)
  → static analysis + knowledge graph + hybrid/graph retrieval index
  → Investigator (LangGraph): evidence retrieval/refinement, hypothesis
    challenge loop, bounded iterations
  → Developer → static patch validator → Reviewer (approve/revise/reject,
    bounded revisions)
  → [optional] Docker sandbox: baseline vs. patched pytest + Ruff, failure
    analysis, bounded retries with re-investigation
  → typed report: root cause, evidence, diff, review decision, test/lint
    comparison, token usage
```

Sandbox validation is opt-in per repository (`REPOAGENT_API_EXECUTION_GITHUB`
allowlist on the web API); without it, the repair stops at a statically
reviewed, unapplied, unexecuted patch proposal.

### 5.2 Discover

```
GitHub URL (no issue text required)
  → fetch + analysis + graph
  → deterministic AST detectors (exceptions, mutable defaults, resource
    handling, subprocess risk, dead code, TODO markers) + graph detectors
    (circular imports, coupling) + optional Ruff
  → deduplicate overlapping candidates
  → RAG evidence enrichment (existing hybrid/graph retrieval, bounded)
  → LLM Issue Verifier: VERIFIED / UNCERTAIN / REJECTED with confidence and
    reasoning, one call per candidate
  → typed report: findings by status, evidence, graph location
```

Discovery never repairs automatically. A VERIFIED finding can be sent to the
repair workflow only on explicit user action ("Attempt Repair"), reusing the
same fetched snapshot.

### 5.3 Interfaces

Every workflow is reachable identically from: the Typer CLI, the in-process
Python SDK (`from repoagent import RepoAgent`), the FastAPI service
(background jobs, never blocking HTTP), and the React web app (live stage
progress, evidence, diffs, and an interactive repository graph).

## 6. Success criteria

A workflow run is only reported successful when the underlying deterministic
check actually passed:

- **Repair** is `VALIDATED` only if the patched workspace's full pytest run
  passes with no new failures and no new Ruff violations versus baseline —
  never on the model's or the Reviewer's word alone.
- **Discovery** findings are VERIFIED only via a structured, evidence-grounded
  LLM call against retrieved snippets, never a free-form claim; UNCERTAIN is a
  first-class, expected outcome, not a defect.
- **Retrieval** quality is reported as Recall@K / MRR / Hit@K against labeled
  cases, computed with no LLM in the loop.
- Every reported metric must trace to a committed run artifact
  (`benchmarks/results/`) or be explicitly marked "not measured" — see
  `docs/benchmarks.md`. Fabricated or estimated numbers are a spec violation.

## 7. Safety requirements (hard constraints, not preferences)

- The original repository is never modified; only disposable copies are
  patched.
- Target repository code is never imported or executed on the host — analysis
  is static (Python `ast`) only; execution happens exclusively inside the
  Docker sandbox via allowlisted commands (pytest, Ruff), `--network none`
  after dependency install, resource/time limits, and a post-run fingerprint
  check.
- Repository content, issue text, and LLM output are untrusted data, never
  instructions; prompts separate them and structured outputs are validated
  before use.
- GitHub URLs are validated to a strict `https://github.com/<owner>/<repo>`
  form before any fetch; git fetches run with hooks, symlinks, LFS, and
  credential helpers disabled.
- No hidden chain-of-thought is persisted or displayed — only concise,
  structured decisions, evidence, and rationale.

## 8. Known limitations and non-goals

See `README.md#limitations` for the current, maintained list (unmeasured
live-repair success, small/non-representative benchmark subsets, Python-only
analysis, lexical-only embeddings, name-based call resolution, uncalibrated
confidence, polling-based web progress, no multi-tenant accounts). This PRD
does not duplicate that list to avoid drift; update the README, not this file,
when a limitation changes.

## 9. Out of scope for "done"

Backlog and prioritization live in `docs/TODO.md`, not here. This document
describes what the product is for; it is updated only when the product's
purpose or hard constraints change, not for routine feature work.
