"""
logging_config.py — structured (JSON) logging.

Dependency-free: a small `logging.Formatter` that emits one JSON object per log
line to stdout, so log aggregators (Loki, CloudWatch, ELK, etc.) can index the
fields directly. The access middleware in `app.py` logs one line per request
with a request id, method, path, status, and duration.
"""

from __future__ import annotations

import datetime
import json
import logging

# Extra fields the access logger attaches; surfaced as top-level JSON keys.
_EXTRA_KEYS = ("request_id", "method", "path", "status", "duration_ms")


class JsonFormatter(logging.Formatter):
    """Render a LogRecord as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.datetime.fromtimestamp(record.created, datetime.UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in _EXTRA_KEYS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Attach a JSON stdout handler to the `resolver` logger namespace.

    Scoped to `resolver.*` (propagation off) so it neither duplicates nor is
    duplicated by uvicorn's own loggers. Idempotent.
    """
    logger = logging.getLogger("resolver")
    logger.handlers = [_json_handler()]
    logger.setLevel(level)
    logger.propagate = False


def _json_handler() -> logging.Handler:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    return handler
