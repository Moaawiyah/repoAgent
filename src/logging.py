"""Structured metadata logging without arbitrary message/payload leakage."""

import json
import logging
from datetime import UTC, datetime


class EventFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
        }
        for key in ("event", "task_id", "kind", "status"):
            if hasattr(record, key):
                payload[key] = str(getattr(record, key))
        return json.dumps(payload)


def configure_logging(level: str) -> None:
    logger = logging.getLogger("repoagent")
    handler = logging.StreamHandler()
    handler.setFormatter(EventFormatter())
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
