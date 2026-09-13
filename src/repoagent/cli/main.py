"""Thin CLI entry point; dependencies are constructed only for operations."""

from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer

from repoagent import __version__
from repoagent.cli.commands import Json, register
from repoagent.cli.runtime import errors, output, service

app = typer.Typer(
    no_args_is_help=True, help="RepoAgent — M1 repository engineering foundation."
)
tasks = typer.Typer(no_args_is_help=True, help="Inspect persisted task records.")
app.add_typer(tasks, name="tasks")


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"repoagent {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    data_dir: Annotated[
        Path | None, typer.Option(help="Application data directory.")
    ] = None,
    env_file: Annotated[Path | None, typer.Option(help="Explicit dotenv file.")] = None,
    version: Annotated[
        bool, typer.Option("--version", callback=version_callback, is_eager=True)
    ] = False,
) -> None:
    ctx.obj = {"data_dir": data_dir, "env_file": env_file}


@tasks.command("show")
def show(ctx: typer.Context, task_id: UUID, json: Json = False) -> None:
    """Read a task, including its capability limitation."""
    with errors():
        output(service(ctx).get(task_id), json)


@tasks.command("events")
def events(ctx: typer.Context, task_id: UUID, json: Json = False) -> None:
    """Read events in stable sequence order."""
    with errors():
        output(service(ctx).events(task_id), json)


register(app)
