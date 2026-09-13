"""Retrieval commands: index, search, and strategy evaluation."""

import json
from pathlib import Path
from typing import Annotated

import typer

from repoagent.cli.runtime import client, errors, output
from repoagent.evaluation.models import RetrievalCase
from repoagent.retrieval.models import RetrievalStrategy

Json = Annotated[bool, typer.Option("--json", help="Write structured JSON to stdout.")]
Strategy = Annotated[
    RetrievalStrategy, typer.Option("--strategy", help="Retrieval strategy.")
]
TopK = Annotated[int, typer.Option("--top-k", help="Maximum hits to return.")]


def _load_cases(path: Path) -> list[RetrievalCase]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [RetrievalCase.model_validate(item) for item in data]
    except (OSError, TypeError, ValueError):
        typer.echo(
            "Invalid input: cases file must contain labeled case objects",
            err=True,
        )
        raise typer.Exit(2) from None


def register_retrieval(app: typer.Typer) -> None:
    @app.command("index")
    def index(ctx: typer.Context, source: str, json: Json = False) -> None:
        """Index a repository for hybrid code retrieval (M3)."""
        with errors():
            output(client(ctx).retrieval().index(source), json)

    @app.command("search")
    def search(
        ctx: typer.Context,
        source: str,
        query: str,
        strategy: Strategy = RetrievalStrategy.HYBRID,
        top_k: TopK = 5,
        rerank: Annotated[
            bool, typer.Option("--rerank", help="Apply deterministic reranking.")
        ] = False,
        json: Json = False,
    ) -> None:
        """Retrieve the most relevant code for a natural-language query."""
        with errors():
            response = (
                client(ctx)
                .retrieval()
                .search(source, query, strategy=strategy, top_k=top_k, rerank=rerank)
            )
            output(response, json)

    @app.command("evaluate")
    def evaluate(
        ctx: typer.Context,
        source: str,
        cases: Annotated[
            Path, typer.Option("--cases", help="JSON file with labeled cases.")
        ],
        strategy: Annotated[
            RetrievalStrategy | None,
            typer.Option("--strategy", help="Single strategy; default compares all."),
        ] = None,
        top_k: TopK = 5,
        json: Json = False,
    ) -> None:
        """Measure Recall@K, MRR, and more per retrieval strategy."""
        with errors():
            labeled = _load_cases(cases)
            strategies = (strategy,) if strategy else None
            report = (
                client(ctx)
                .retrieval()
                .evaluate(source, labeled, k=top_k, strategies=strategies)
            )
            output(report, json)
