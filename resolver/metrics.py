"""
metrics.py — minimal, dependency-free Prometheus metrics.

The resolver deliberately avoids a hard dependency on `prometheus_client` to
keep the core package slim (the same principle that keeps `httpx`/`jsonschema`
optional). This module hand-rolls the small slice of the Prometheus text
exposition format the resolver actually needs:

  - a labelled counter for resolve outcomes
  - a labelled counter for validator outcomes
  - a sum + count pair for resolve latency (a Prometheus "summary" shape, so
    `rate(_sum) / rate(_count)` gives average latency)
  - a build-info gauge carrying the version label

State is process-local. For a single-process deployment a normal scrape works
out of the box; multi-process / multi-replica setups aggregate at the
Prometheus server (or via a proxy exporter), as the deployment guide notes.
"""

from __future__ import annotations

import threading

_lock = threading.Lock()

# outcome -> count   (outcome ∈ resolved | redirect | not_found | bad_request)
_requests: dict[str, int] = {}
# "true" | "false" -> count
_validations: dict[str, int] = {}
_latency_sum_seconds = 0.0
_latency_count = 0
_version = "unknown"


def set_version(version: str) -> None:
    """Record the build version exposed via gs1_resolver_build_info."""
    global _version
    _version = version


def record_request(outcome: str, duration_seconds: float) -> None:
    """Count one resolve by outcome and add its latency to the summary."""
    global _latency_sum_seconds, _latency_count
    with _lock:
        _requests[outcome] = _requests.get(outcome, 0) + 1
        _latency_sum_seconds += duration_seconds
        _latency_count += 1


def record_validation(ok: bool) -> None:
    """Count one (non-no-op) validator outcome."""
    key = "true" if ok else "false"
    with _lock:
        _validations[key] = _validations.get(key, 0) + 1


def _escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def render() -> str:
    """Render the current metrics in the Prometheus text exposition format."""
    with _lock:
        requests = dict(_requests)
        validations = dict(_validations)
        latency_sum = _latency_sum_seconds
        latency_count = _latency_count
        version = _version

    lines: list[str] = []

    lines.append("# HELP gs1_resolver_build_info Resolver build information.")
    lines.append("# TYPE gs1_resolver_build_info gauge")
    lines.append(f'gs1_resolver_build_info{{version="{_escape_label_value(version)}"}} 1')

    lines.append("# HELP gs1_resolver_requests_total Total resolve requests by outcome.")
    lines.append("# TYPE gs1_resolver_requests_total counter")
    for outcome in sorted(requests):
        lines.append(
            f'gs1_resolver_requests_total{{outcome="{_escape_label_value(outcome)}"}} '
            f"{requests[outcome]}"
        )

    lines.append("# HELP gs1_resolver_validations_total Validator outcomes (excludes no-op).")
    lines.append("# TYPE gs1_resolver_validations_total counter")
    for ok in sorted(validations):
        lines.append(f'gs1_resolver_validations_total{{ok="{ok}"}} {validations[ok]}')

    lines.append("# HELP gs1_resolver_resolve_duration_seconds Resolve latency summary.")
    lines.append("# TYPE gs1_resolver_resolve_duration_seconds summary")
    lines.append(f"gs1_resolver_resolve_duration_seconds_sum {latency_sum}")
    lines.append(f"gs1_resolver_resolve_duration_seconds_count {latency_count}")

    return "\n".join(lines) + "\n"


CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
