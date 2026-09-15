"""Serve the local API and optional built dashboard."""

from pathlib import Path
from typing import Annotated

import typer

from repoagent.cli.runtime import client, errors

LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def register_serve(app: typer.Typer) -> None:
    @app.command()
    def serve(
        ctx: typer.Context,
        host: str = "127.0.0.1",
        port: Annotated[int, typer.Option(min=1, max=65535)] = 8000,
        allow_root: Annotated[list[Path] | None, typer.Option("--allow-root")] = None,
        execution_repo: Annotated[
            list[Path] | None, typer.Option("--execution-repo")
        ] = None,
        dashboard: Annotated[Path | None, typer.Option()] = None,
    ) -> None:
        """Run the RepoAgent API (analysis/search/investigation; gated execution)."""
        import uvicorn

        from repoagent.api.app import create_app

        with errors():
            agent = client(ctx)
            settings = agent._settings.model_copy(
                update={
                    "api_allowed_roots": [
                        *agent._settings.api_allowed_roots, *(allow_root or [])
                    ],
                    "api_execution_repositories": [
                        *agent._settings.api_execution_repositories,
                        *(execution_repo or []),
                    ],
                }
            )  # fmt: skip
            if host not in LOOPBACK and settings.api_token is None:
                typer.echo(
                    "Invalid input: non-loopback hosts require REPOAGENT_API_TOKEN",
                    err=True,
                )
                raise typer.Exit(2)
            api = create_app(settings, dashboard=dashboard)
        uvicorn.run(api, host=host, port=port, log_level="warning")
