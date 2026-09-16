"""``graphify``: one command tying graph build, graph.json, and Obsidian.

Delegates to the same SDK/graph machinery as ``graph`` and
``export-obsidian`` (see ``graph_cli.py``) — this command adds persistence
and a single combined entry point rather than a second graph pipeline.
"""

from pathlib import Path
from typing import Annotated

import typer

from repoagent.cli.runtime import client, errors
from repoagent.cli.runtime import output as emit

Json = Annotated[bool, typer.Option("--json", help="Write structured JSON to stdout.")]
Output = Annotated[
    Path | None, typer.Option("--output", help="Write a graph.json document here.")
]
Obsidian = Annotated[
    Path | None, typer.Option("--obsidian", help="Export an Obsidian vault here.")
]
Artifacts = Annotated[
    Path | None,
    typer.Option(
        "--artifacts",
        help=(
            "Write into <dir>/<repository name>/{graph.json,vault} for any of "
            "--output/--obsidian left unset — one subdirectory per repository."
        ),
    ),
]
Overwrite = Annotated[
    bool, typer.Option("--overwrite", help="Export into a non-empty Obsidian vault.")
]


def register_graphify(app: typer.Typer) -> None:
    @app.command("graphify")
    def graphify(
        ctx: typer.Context,
        source: str,
        output: Output = None,
        obsidian: Obsidian = None,
        artifacts: Artifacts = None,
        overwrite: Overwrite = False,
        json: Json = False,
    ) -> None:
        """Build the code knowledge graph and persist graph.json/Obsidian."""
        with errors():
            result = (
                client(ctx)
                .retrieval()
                .graphify(
                    source,
                    output=output,
                    obsidian=obsidian,
                    artifacts_dir=artifacts,
                    overwrite=overwrite,
                )
            )
            emit(result, as_json=json)
