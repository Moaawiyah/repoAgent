# Documentation index

Start at the root [`README.md`](../README.md) for install/usage. This folder
holds the detailed and process documentation.

| Doc | What it's for |
| --- | --- |
| [PRD.md](PRD.md) | What RepoAgent is for, who it's for, core workflows, success criteria, hard safety constraints. Read this first to understand *why*. |
| [architecture.md](architecture.md) | System design per milestone: layering, data flow diagrams, component responsibilities. Read this to understand *how*. |
| [milestones.md](milestones.md) | What was delivered at each milestone (M1–M9) and what's explicitly not implemented. |
| [CHANGELOG.md](CHANGELOG.md) | Chronological summary of what shipped, one entry per milestone. |
| [TODO.md](TODO.md) | Prioritized, honestly-scoped backlog — what's known to be missing or unmeasured. |
| [sdk.md](sdk.md) | Python SDK usage reference with runnable examples. |
| [guide.md](guide.md) | Detailed per-command CLI usage and configuration. |
| [m5-investigation.md](m5-investigation.md) | Investigator LangGraph internals: state, nodes, routing, budgets. |
| [m5-validation.md](m5-validation.md) | How the Investigator was validated and its known failure modes. |
| [benchmarks.md](benchmarks.md) | Methodology and **measured** results only; unmeasured values are explicitly labeled. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Practical dev workflow: setup, standards summary, quality gates, commit/PR expectations. |

Full engineering standards (file-length limits, OOP/dependency boundaries,
safety rules, the exact coverage gate) live in [`SKILL.md`](../SKILL.md) at
the repository root, not here — `CONTRIBUTING.md` is the short version of it.

## Keeping these current

- Update `PRD.md` only when the product's purpose or hard constraints change.
- Update `TODO.md` for routine planning; delete items that turn out to be
  unnecessary rather than leaving them stale.
- Update `CHANGELOG.md` and `milestones.md` when a milestone ships.
- Update `architecture.md` and `sdk.md` when interfaces or data flow change.
- Never let a number in `benchmarks.md` be anything other than a value copied
  from a committed run artifact under `benchmarks/results/`.
