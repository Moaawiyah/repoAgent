"""Lazy dependency wiring and safe CLI error presentation."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer
from pydantic import ValidationError

from repoagent import RepoAgent
from repoagent.analysis.render import render_analysis
from repoagent.analysis.results import RepositoryAnalysis
from repoagent.cli.execution_render import render_validated_repair
from repoagent.cli.graphify_render import render_graphify
from repoagent.cli.investigation_render import render_investigation
from repoagent.cli.render import (
    render_evaluation,
    render_export,
    render_graph_inspection,
    render_graph_summary,
    render_index,
    render_search,
)
from repoagent.cli.repair_render import render_repair
from repoagent.config import Settings
from repoagent.domain.errors import RepoAgentError
from repoagent.domain.investigation import InvestigationReport
from repoagent.domain.repair import RepairReport
from repoagent.domain.repair_execution import ValidatedRepairReport
from repoagent.domain.tasks import TaskEvent, TaskRecord
from repoagent.evaluation.models import EvaluationReport
from repoagent.export.obsidian import ExportSummary
from repoagent.graph.models import GraphInspection, GraphSummary
from repoagent.graph.serializer import GraphifyResult
from repoagent.logging import configure_logging
from repoagent.retrieval.models import SearchResponse
from repoagent.retrieval.persistence import IndexSummary


@contextmanager
def errors() -> Iterator[None]:
    try:
        yield
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(map(str, item['loc']))}: {item['msg']}"
            for item in exc.errors(include_input=False)
        )
        typer.echo(f"Invalid input: {details}", err=True)
        raise typer.Exit(2) from None
    except RepoAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    except OSError:
        typer.echo("Storage or filesystem operation failed", err=True)
        raise typer.Exit(1) from None


def client(ctx: typer.Context) -> RepoAgent:
    options = ctx.obj or {}
    kwargs = {}
    if options.get("data_dir") is not None:
        kwargs["data_dir"] = options["data_dir"]
    env_file: Path | None = options.get("env_file")
    if env_file is not None and not env_file.is_file():
        typer.echo("Invalid input: explicit environment file does not exist", err=True)
        raise typer.Exit(2)
    settings = Settings(_env_file=env_file, **kwargs)
    configure_logging(settings.log_level)
    return RepoAgent(settings=settings)


def output(
    value: TaskRecord
    | list[TaskEvent]
    | RepositoryAnalysis
    | IndexSummary
    | SearchResponse
    | EvaluationReport
    | GraphSummary
    | GraphInspection
    | GraphifyResult
    | ExportSummary
    | InvestigationReport
    | RepairReport
    | ValidatedRepairReport,
    as_json: bool,
) -> None:
    if as_json:
        data = (
            [event.model_dump(mode="json") for event in value]
            if isinstance(value, list)
            else value.model_dump(mode="json")
        )
        typer.echo(json.dumps(data))
        return
    renderers = (
        (TaskRecord, lambda v: f"Task {v.id}: {v.status}\n{v.message or ''}"),
        (RepositoryAnalysis, render_analysis),
        (IndexSummary, render_index),
        (SearchResponse, render_search),
        (EvaluationReport, render_evaluation),
        (GraphSummary, render_graph_summary),
        (GraphInspection, render_graph_inspection),
        (GraphifyResult, render_graphify),
        (ExportSummary, render_export),
        (InvestigationReport, render_investigation),
        (RepairReport, render_repair),
        (ValidatedRepairReport, render_validated_repair),
    )
    for value_type, renderer in renderers:
        if isinstance(value, value_type):
            typer.echo(renderer(value))
            return
    for event in value:
        typer.echo(f"{event.sequence}: {event.name} ({event.status}) {event.message}")
