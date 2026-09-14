"""Run labeled investigation cases using a configured real provider.

Labels remain in this evaluator and are never passed to the agent.
"""

import argparse
from pathlib import Path

from pydantic import TypeAdapter

from repoagent import RepoAgent, Settings
from repoagent.evaluation.investigation import (
    InvestigationTask,
    run_investigation_benchmark,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    tasks = TypeAdapter(list[InvestigationTask]).validate_json(args.cases.read_text())
    settings = Settings(_env_file=args.env_file, data_dir=args.data_dir)
    client = RepoAgent(settings=settings)

    def investigate(task: InvestigationTask):
        client.index(task.repository)
        return client.investigate(task.repository, task.issue, top_k=args.top_k)

    result = run_investigation_benchmark(investigate, tasks)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
