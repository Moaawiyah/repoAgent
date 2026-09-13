"""SQLite connection ownership and versioned schema initialization."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from repoagent.domain.errors import UnsupportedSchema

SCHEMA_VERSION = 1


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path, timeout=10, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        yield connection
    finally:
        connection.close()


def initialize(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in {0, SCHEMA_VERSION}:
                raise UnsupportedSchema(
                    f"Unsupported database schema version: {version}"
                )
            if version == 0:
                tables = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
                if tables:
                    raise UnsupportedSchema(
                        "Unversioned nonempty database is unsupported"
                    )
                connection.execute(
                    "CREATE TABLE tasks (id TEXT PRIMARY KEY, record TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE events (task_id TEXT NOT NULL REFERENCES tasks(id), "
                    "sequence INTEGER NOT NULL CHECK(sequence > 0), "
                    "record TEXT NOT NULL, PRIMARY KEY(task_id, sequence))"
                )
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
