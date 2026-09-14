"""Thin CLI entry point; dependencies are constructed only for operations."""

from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer

from repoagent import __version__
from repoagent.cli.commands import Json, register
from repoagent.cli.graph_cli import register_graph
from repoagent.cli.investigate_cli import register_investigate
from repoagent.cli.repair_cli import register_repair
from repoagent.cli.retrieval_cli import register_retrieval
from repoagent.cli.runtime import client, errors, output

app = typer.Typer(
    no_args_is_help=True,
    help="RepoAgent — repository analysis, retrieval, and engineering platform.",
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
        output(client(ctx).get_task(task_id), json)


@tasks.command("events")
def events(ctx: typer.Context, task_id: UUID, json: Json = False) -> None:
    """Read events in stable sequence order."""
    with errors():
        output(client(ctx).task_events(task_id), json)


register(app)
register_retrieval(app)
register_graph(app)
register_investigate(app)
register_repair(app)
