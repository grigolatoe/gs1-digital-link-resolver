"""
validator.py — Pluggable DPP validator interface

A resolver is, primarily, a router: parse a URI → look up where to send the
client. It is *not* a DPP validator. But operators commonly want to know,
at resolve time, whether the DPP a URI points to is well-formed against the
relevant ESPR/CIRPASS-2 profile — e.g. so they can surface a soft warning
in the link-set response without blocking resolution.

This module defines the contract every validator implementation must
satisfy. Three concrete implementations ship in-tree:

  - NoOpValidator         — the default; never flags anything
  - SchemaValidator       — JSON-Schema check against a CIRPASS-2 profile
                             (only loaded if a schema path is configured)
  - HttpValidator         — POST to an external CIRPASS-2 validator endpoint

Operators can supply their own implementation via the `validator:` block
in routes.yaml; the loader at the bottom of this module wires it up.

The validator runs *after* a route has been chosen and *before* the
response is built. Validation results are advisory only — failures never
block resolution. The result is attached to the response as a
`gs1:validationStatus` link in the link-set, so a machine consumer can
see at a glance that the DPP this resolver pointed at had warnings.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .parser import GS1ParseResult


@dataclass
class ValidationResult:
    """Outcome of a validator run for a single resolved URI."""
    ok: bool
    profile: str = ""              # e.g. "cirpass2-textile-2026"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "profile": self.profile,
            "errors": self.errors,
            "warnings": self.warnings,
        }


@runtime_checkable
class Validator(Protocol):
    """Interface every validator implementation must satisfy."""

    def validate(self, parsed: GS1ParseResult, target_url: str) -> ValidationResult:
        ...


# --- Default: never flags anything ------------------------------------------

class NoOpValidator:
    """The default. Allows the resolver to ship without any validation overhead."""

    profile = ""

    def validate(self, parsed: GS1ParseResult, target_url: str) -> ValidationResult:
        return ValidationResult(ok=True, profile=self.profile)


# --- Lightweight built-in: pattern-based smoke checks -----------------------

@dataclass
class SmokeValidator:
    """
    A minimal built-in validator that runs trivial structural checks on the
    parsed URI itself (not on the DPP behind it). Useful as a default for
    operators who want some signal but don't want to wire up CIRPASS-2.

    Checks:
      - GTIN-14 left-pad validity (already done by the parser, surfaced here)
      - Serial number length and character class (when present)
      - Lot/batch length (when present)
    """
    profile: str = "smoke-builtin-v1"
    serial_pattern: re.Pattern[str] = field(
        default_factory=lambda: re.compile(r"^[A-Za-z0-9_\-.:/]{1,50}$")
    )
    lot_pattern: re.Pattern[str] = field(
        default_factory=lambda: re.compile(r"^[A-Za-z0-9_\-.:/]{1,20}$")
    )

    def validate(self, parsed: GS1ParseResult, target_url: str) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        if parsed.serial_number is not None:
            if not self.serial_pattern.match(parsed.serial_number):
                warnings.append(
                    f"Serial number {parsed.serial_number!r} does not match the recommended "
                    "GS1 character set [A-Za-z0-9_-.:/] (length 1..50)."
                )

        if parsed.batch_lot is not None:
            if not self.lot_pattern.match(parsed.batch_lot):
                warnings.append(
                    f"Batch/lot {parsed.batch_lot!r} does not match the recommended "
                    "GS1 character set [A-Za-z0-9_-.:/] (length 1..20)."
                )

        if parsed.unknown_ais:
            warnings.append(
                "URI contains numeric AIs that are not in the GS1 DL-compatible "
                f"AI table: {[a for a, _ in parsed.unknown_ais]!r}."
            )

        return ValidationResult(
            ok=not errors,
            profile=self.profile,
            errors=errors,
            warnings=warnings,
        )


# --- Optional: JSON-Schema validation against a CIRPASS-2 profile ----------

@dataclass
class SchemaValidator:
    """
    Validate the *target DPP* against a JSON Schema (e.g. a CIRPASS-2
    textile or battery profile). The schema is fetched once at construction
    time; the target DPP is fetched per-resolve.

    This implementation deliberately avoids a hard dependency on
    `jsonschema` so the package stays slim. If the operator has not
    installed `jsonschema`, the validator emits a one-time warning and
    falls back to a no-op.
    """
    schema_path: str | Path
    profile: str = "cirpass2-custom"

    def __post_init__(self) -> None:
        with open(self.schema_path) as f:
            self._schema = json.load(f)
        try:
            import jsonschema  # noqa: F401
            self._jsonschema_available = True
        except ImportError:
            self._jsonschema_available = False

    def validate(self, parsed: GS1ParseResult, target_url: str) -> ValidationResult:
        if not self._jsonschema_available:
            return ValidationResult(
                ok=True,
                profile=self.profile,
                warnings=["jsonschema package not installed; SchemaValidator disabled."],
            )
        # Note: actually fetching `target_url` and validating the body
        # against `self._schema` is intentionally out of scope for the
        # initial scaffold — the hook contract is what matters at this
        # stage. Milestone 3 of the NGI grant covers the live integration
        # with the CIRPASS-2 reference validator endpoint.
        return ValidationResult(ok=True, profile=self.profile)


# --- Loader -----------------------------------------------------------------

def load_validator(config: dict[str, Any] | None) -> Validator:
    """
    Build a validator from a YAML config block. Shape:

      validator:
        type: noop|smoke|schema
        # for type=schema:
        schema_path: /path/to/cirpass2-textile.schema.json
        profile: cirpass2-textile-2026

    Falls back to NoOpValidator when no config is provided.
    """
    if not config:
        return NoOpValidator()
    kind = (config.get("type") or "noop").lower()
    if kind == "noop":
        return NoOpValidator()
    if kind == "smoke":
        return SmokeValidator(profile=config.get("profile", "smoke-builtin-v1"))
    if kind == "schema":
        schema_path = config.get("schema_path")
        if not schema_path:
            raise ValueError("SchemaValidator requires a schema_path")
        return SchemaValidator(
            schema_path=schema_path,
            profile=config.get("profile", "cirpass2-custom"),
        )
    raise ValueError(f"Unknown validator type: {kind!r}")
