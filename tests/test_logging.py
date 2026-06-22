"""Tests for structured JSON logging."""

from __future__ import annotations

import json
import logging

from resolver.logging_config import JsonFormatter


def _record(**extra) -> logging.LogRecord:
    rec = logging.LogRecord(
        name="resolver.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request",
        args=(),
        exc_info=None,
    )
    for k, v in extra.items():
        setattr(rec, k, v)
    return rec


def test_formatter_emits_valid_json_with_core_fields():
    out = JsonFormatter().format(_record())
    obj = json.loads(out)  # must be single-line valid JSON
    assert obj["level"] == "INFO"
    assert obj["logger"] == "resolver.access"
    assert obj["msg"] == "request"
    assert "ts" in obj


def test_formatter_surfaces_access_extras():
    out = JsonFormatter().format(
        _record(request_id="abc123", method="GET", path="/01/0", status=200, duration_ms=1.23)
    )
    obj = json.loads(out)
    assert obj["request_id"] == "abc123"
    assert obj["method"] == "GET"
    assert obj["path"] == "/01/0"
    assert obj["status"] == 200
    assert obj["duration_ms"] == 1.23


def test_formatter_ignores_unknown_extras():
    """Only the documented access-log keys are surfaced, not arbitrary attrs."""
    obj = json.loads(JsonFormatter().format(_record(secret="should-not-appear")))
    assert "secret" not in obj
