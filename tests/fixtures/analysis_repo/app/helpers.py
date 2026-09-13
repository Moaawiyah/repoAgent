"""Small helpers demonstrating import kinds."""

import json
import os

import requests


def dump(payload: dict[str, int]) -> str:
    """Serialize a payload to JSON text."""
    return json.dumps(payload)


def environment(name: str) -> str | None:
    """Read an environment variable."""
    return os.environ.get(name)


def fetch(url: str) -> int:
    """Perform an external HTTP request; never executed by tests."""
    return len(requests.get(url).text)
