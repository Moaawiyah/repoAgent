# RepoAgent

An independent repository engineering platform. **M1 foundation, M2 repository
analysis, and M3 hybrid code retrieval are implemented.** Model calls, agents,
patch generation, sandbox execution, and benchmarks are planned capabilities,
not working features in this release.

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). Install dependencies:

```sh
uv sync --locked
uv run repoagent --help
uv run repoagent --version
```

Runtime and tests need no API keys, Docker daemon, or network after installation.

## Analyzing repositories (M2)

```sh
uv run repoagent analyze ./some-python-project
uv run repoagent analyze ./some-python-project --json
```

`analyze` accepts a local directory, validates it (existing, a directory,
readable), and performs static analysis only — target code is never imported
or executed. Extracted information:

- Python modules with docstrings and line ranges.
- Classes with base classes, decorators, docstrings, and line ranges.
- Functions, methods, and async functions with typed parameters
  (name, annotation, default, kind), return annotations, docstrings, and
  line ranges.
- Imports classified conservatively as repository-internal, standard
  library, or external.
- Relationships: imports, inheritance, containment, definitions.
- Repository summary: file/module/class/function/method counts, detected
  tests and configuration files, and per-file analysis errors.

Discovery skips vendored/ignored directories, honors `.gitignore`, and never
follows symlinks outside the repository. One malformed file is recorded as a
per-file error and does not abort the analysis. Results are deterministic.

## Indexing and searching (M3)

```sh
uv run repoagent index ./some-python-project
uv run repoagent search ./some-python-project "Where is authentication handled?"
uv run repoagent search ./some-python-project "authentication" --strategy bm25 --top-k 5
uv run repoagent search ./some-python-project "authentication" --strategy vector
uv run repoagent search ./some-python-project "authentication" --strategy hybrid --rerank
uv run repoagent search ./some-python-project "authentication" --json
```

`index` analyzes a repository (reusing M2), splits it into structure-aware
chunks aligned with functions, methods, classes, and module-level code, embeds
each chunk once, and persists the index under the data directory. Chunk IDs
are deterministic (`repository + file + qualified symbol + source hash`), so
unchanged code keeps its identity.

`search` retrieves the most relevant code with full provenance (file, symbol,
line range, source preview) rather than dumping whole files. Strategies:
`bm25` (Okapi BM25 with identifier-aware tokenization that splits
snake_case/CamelCase while preserving exact identifiers), `vector` (embedding
similarity), and `hybrid` (default; Reciprocal Rank Fusion of both, never
mixing raw score scales). `--rerank` optionally applies a deterministic
keyword-overlap reranker. JSON output is machine-readable; logs never mix
into it.

## Retrieval evaluation (LLM-free)

```sh
uv run repoagent evaluate ./some-python-project \
  --cases cases.json --top-k 5
uv run repoagent evaluate ./some-python-project \
  --cases cases.json --strategy bm25 --json
```

`evaluate` runs real searches per strategy against labeled cases (query +
expected files/symbols) and reports Recall@K, MRR, HitRate@K, and Precision@K
computed from actual retrieval results — nothing is hardcoded. See
`tests/fixtures/rag_cases.json` for the case format. This is how retrieval
quality is measured independently of any language model, and how future
strategies (graph expansion, rerankers) will be compared.

## Unavailable workflows (task records)

```sh
uv run repoagent --data-dir .repoagent ask ./repo 'How is auth done?' --json
uv run repoagent --data-dir .repoagent fix ./repo 'Login returns 500' --json
uv run repoagent --data-dir .repoagent benchmark synthetic --json
uv run repoagent --data-dir .repoagent tasks show TASK_ID --json
```

`ask`, `fix`, `test`, and `benchmark` validate input and record a **blocked**
task with a `capability_unavailable` event, exiting with code **3**. This is
expected behavior, not evidence of an attempted operation. Exit codes: 0
success; 1 operational failure; 2 invalid input; 3 unavailable capability.

## Python SDK

```python
from pathlib import Path
from repoagent import RepoAgent, Settings

client = RepoAgent(settings=Settings(data_dir=Path(".repoagent")))
summary = client.index("./some-python-project")
print(summary.chunk_count, summary.embedding_provider)

response = client.search("./some-python-project", "verify password", top_k=3)
for hit in response.results:
    print(hit.rank, hit.chunk.file_path, hit.chunk.qualified_name, hit.score)

analysis = client.analyze("./some-python-project")
print(analysis.class_count, analysis.method_count)
```

`index`, `search`, `analyze`, and `evaluate` return typed Pydantic models.
`ask`, `fix`, `test`, `benchmark`, `submit`, `get_task`, and `task_events`
remain available; unavailable workflows return blocked task records. The SDK
never prints, terminates the process, or installs logging handlers. Storage
and embedding providers are injectable (`index_store=`, `embedding_provider=`)
behind the `IndexStore` and `EmbeddingProvider` protocols.

## Configuration and data

Settings use the `REPOAGENT_` prefix; see `.env.example`. Task data defaults
to `~/.repoagent/tasks.sqlite3`; retrieval indexes are stored under
`<data-dir>/indexes/`. Embedding configuration: `REPOAGENT_EMBEDDING_PROVIDER`
(`hashing` deterministic local provider) and `REPOAGENT_EMBEDDING_DIMENSION`.
An index records its provider and dimension; searching with a mismatched
provider fails with a clear error instead of silently degrading. Logs contain
allowlisted metadata only. Target code is never imported or executed by
analysis, indexing, or search.

## Validation

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python scripts/check_quality.py
uv build
```

The quality helper requires fresh statement coverage strictly above 85% and
at most 150 physical lines per Python file. CI repeats validation and a wheel
smoke test on Python 3.12/3.13.

## Architecture and next step

Source modules live directly in `src/` (`sdk/`, `domain/`, `application/`,
`adapters/`, `analysis/` (M2), `retrieval/` and `evaluation/` (M3), `cli/`).
See [architecture](docs/architecture.md) for boundaries and the pipelines;
see [milestones](docs/milestones.md) for the roadmap.

Next: **M4 — dependency/import/inheritance graph retrieval** built on M2
relationships and evaluated with the M3 framework (strategy E).
