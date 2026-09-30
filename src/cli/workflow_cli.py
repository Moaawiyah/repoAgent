"""LangGraph workflow diagram command."""

import json as json_module
from typing import Annotated

import typer

from repoagent.workflows.diagrams import compiled_workflows, workflow_diagrams

Json = Annotated[bool, typer.Option("--json", help="Write {name: mermaid} JSON.")]
Name = Annotated[
    str | None, typer.Argument(help="One workflow; all workflows when omitted.")
]


def register_workflow(app: typer.Typer) -> None:
    @app.command("workflow-diagram")
    def workflow_diagram(name: Name = None, json: Json = False) -> None:
        """Print Mermaid diagrams of the compiled LangGraph workflows."""
        if name is not None and name not in compiled_workflows():
            raise typer.BadParameter(
                f"expected one of {sorted(compiled_workflows())}", param_hint="NAME"
            )
        diagrams = workflow_diagrams(name)
        if json:
            typer.echo(json_module.dumps(diagrams, indent=2))
            return
        for key, mermaid in diagrams.items():
            typer.echo(f"%% {key}\n{mermaid}")
