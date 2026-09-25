"""Benchmark CLI: run suites, show stored reports, import external datasets."""

import json as jsonlib
from pathlib import Path
from typing import Annotated

import typer

from repoagent.benchmark.experiment import (
    ABLATIONS,
    RETRIEVAL_ABLATIONS,
    BenchmarkMode,
    ablation_names,
)
from repoagent.benchmark.loaders import BenchmarkError, resolve_suite
from repoagent.benchmark.report import render_benchmark
from repoagent.cli.runtime import client, errors

Json = Annotated[bool, typer.Option("--json", help="Write structured JSON.")]


def _emit(run, as_json: bool) -> None:
    if as_json:
        typer.echo(run.model_dump_json())
    else:
        typer.echo(render_benchmark(run.manifest, run.summary))


def register_benchmark(app: typer.Typer) -> None:
    @app.command()
    def benchmark(
        ctx: typer.Context,
        suite: Annotated[str, typer.Argument(help="Suite file or ./benchmarks name.")],
        mode: Annotated[BenchmarkMode, typer.Option()] = BenchmarkMode.RETRIEVAL,
        task: Annotated[list[str] | None, typer.Option("--task")] = None,
        ablation: Annotated[
            list[str] | None,
            typer.Option(
                "--ablation",
                help=f"LLM modes: {', '.join(ABLATIONS)}. "
                f"Retrieval: {', '.join(RETRIEVAL_ABLATIONS)}",
            ),
        ] = None,
        k: Annotated[int, typer.Option("--k", min=1, max=50)] = 5,
        max_attempts: Annotated[int, typer.Option(min=1, max=10)] = 3,
        timeout: Annotated[int | None, typer.Option(min=1, max=3600)] = None,
        json: Json = False,
    ) -> None:
        """Run a benchmark; retrieval mode is LLM-free, repair mode uses Docker."""
        try:
            resolve_suite(suite)
            known = ablation_names(mode)
            unknown = [name for name in ablation or [] if name not in known]
            if unknown:
                raise BenchmarkError(f"Unknown ablation(s): {', '.join(unknown)}")
        except BenchmarkError as error:
            typer.echo(f"Invalid input: {error}", err=True)
            raise typer.Exit(2) from None
        with errors():
            api = client(ctx).benchmarks()
            run = api.run(
                suite,
                mode=mode,
                ablations=ablation,
                task_ids=task,
                k=k,
                max_attempts=max_attempts,
                timeout=timeout,
                progress=lambda r: typer.echo(
                    f"{r.task_id} [{r.experiment}] {r.status}", err=True
                ),
            )
            _emit(run, json)

    @app.command("benchmark-report")
    def benchmark_report(ctx: typer.Context, run_id: str, json: Json = False) -> None:
        """Summarize a stored benchmark run from its JSONL results."""
        with errors():
            _emit(client(ctx).benchmarks().load(run_id), json)

    @app.command("benchmark-import")
    def benchmark_import(
        ctx: typer.Context,
        dataset: Annotated[
            str, typer.Argument(help="bugsinpy, swebench, or swerebench")
        ],
        source: Path,
        output: Annotated[Path, typer.Option("--output")],
        item: Annotated[list[str], typer.Option("--item", help="Bug or instance")],
        name: str = "swe-bench-verified",
        origin: str = "princeton-nlp/SWE-bench_Verified",
        image: Annotated[
            str, typer.Option(help="swerebench image template (pinned by digest).")
        ] = "python:{python}-slim",
    ) -> None:
        """Convert a local dataset checkout/export into a RepoAgent suite."""
        from repoagent.benchmark.adapters import import_bugsinpy, import_swebench
        from repoagent.benchmark.loaders import read_records

        with errors():
            if dataset == "bugsinpy":
                suite = import_bugsinpy(source, item)
            elif dataset == "swerebench":
                api = client(ctx).benchmarks()
                records = read_records(source)
                suite, skipped = api.import_swerebench(records, item, image)
                for instance, reason in skipped.items():
                    typer.echo(f"Skipped {instance}: {reason}", err=True)
            elif dataset == "swebench":
                suite = import_swebench(read_records(source), item, name, origin)
            else:
                raise BenchmarkError("Dataset must be bugsinpy, swebench or swerebench")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(jsonlib.dumps(suite.model_dump(mode="json"), indent=2))
            typer.echo(f"Wrote {len(suite.tasks)} task(s) to {output}")

    @app.command("benchmark-verify")
    def benchmark_verify(
        ctx: typer.Context,
        suite: Annotated[str, typer.Argument(help="Suite file or ./benchmarks name.")],
        task: Annotated[list[str] | None, typer.Option("--task")] = None,
        output: Annotated[
            Path | None, typer.Option(help="Verified-only suite.")
        ] = None,
        json: Json = False,
    ) -> None:
        """Check pinned environments, hidden tests, and gold patches (Docker)."""
        from repoagent.benchmark.loaders import load_suite

        with errors():
            checks = client(ctx).benchmarks().verify(suite, task_ids=task)
            for check in checks:
                line = check.model_dump_json() if json else _check_line(check)
                typer.echo(line)
            if output is not None:
                loaded = load_suite(resolve_suite(suite))
                keep = {c.task_id for c in checks if c.verified}
                tasks = [t for t in loaded.tasks if t.task_id in keep]
                verified = loaded.model_copy(update={"tasks": tasks})
                output.write_text(verified.model_dump_json(indent=2) + "\n")
                typer.echo(f"Wrote {len(tasks)} verified task(s) to {output}")


def _check_line(check) -> str:
    status = "VERIFIED" if check.verified else "EXCLUDED"
    reason = f" - {check.reason}" if check.reason else ""
    return f"{check.task_id}: {status} ({check.duration_seconds}s){reason}"
