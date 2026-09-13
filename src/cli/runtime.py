"""Lazy dependency wiring and safe CLI error presentation."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer
from pydantic import ValidationError

from repoagent import RepoAgent
from repoagent.config import Settings
from repoagent.domain.errors import RepoAgentError
from repoagent.domain.tasks import TaskEvent, TaskRecord
from repoagent.logging import configure_logging


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


def output(value: TaskRecord | list[TaskEvent], as_json: bool) -> None:
    if as_json:
        data = (
            value.model_dump(mode="json")
            if isinstance(value, TaskRecord)
            else [event.model_dump(mode="json") for event in value]
        )
        typer.echo(json.dumps(data))
    elif isinstance(value, TaskRecord):
        typer.echo(f"Task {value.id}: {value.status}\n{value.message or ''}")
    else:
        for event in value:
            typer.echo(
                f"{event.sequence}: {event.name} ({event.status}) {event.message}"
            )
