"""
parser.py — GS1 Digital Link URI parser

Parses GS1 Digital Link URIs per GS1 Digital Link Standard v1.2 (the
ISO/IEC 18975 candidate text). Two URI shapes are accepted:

  Numeric AI form:   /01/{gtin14}/22/{cpv}/10/{lot}/21/{serial}?linkType=...
  Alpha-coded form:  /gtin/{gtin14}/cpv/{cpv}/lot/{lot}/ser/{serial}

The full DL-compatible AI table lives in `ai_table.py`. The parser only
recognises AIs that the standard permits in a DL URI; unknown numeric path
segments are kept verbatim as qualifiers but flagged via `unknown_ais` so a
caller can decide whether to refuse the request.

The parser does not enforce qualifier *ordering*; ordering is a concern of
canonical URI generation (`canonicalise()`), not of routing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, parse_qs, quote

from .ai_table import (
    AI_TO_NAME,
    AI_TO_SPEC,
    NAME_TO_AI,
    PRIMARY_AIS,
    QUALIFIER_ORDER,
    fixed_length,
    is_known,
)

# Regex: numeric AI path segment — /NN.../ followed by value (value cannot
# contain '/' — qualifiers always live in their own path segments).
_AI_PATH_RE = re.compile(r"/(\d{2,4})/([^/?#]+)")


@dataclass
class GS1ParseResult:
    """Result of parsing a GS1 Digital Link URI."""
    primary_ai: str = ""           # e.g. "01"
    primary_value: str = ""        # e.g. "09780345418913"
    qualifiers: dict[str, str] = field(default_factory=dict)
    attributes: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, list[str]] = field(default_factory=dict)
    link_type: Optional[str] = None
    unknown_ais: list[tuple[str, str]] = field(default_factory=list)

    # ---- convenience accessors --------------------------------------------
    @property
    def gtin(self) -> Optional[str]:
        return self.primary_value if self.primary_ai == "01" else None

    @property
    def serial_number(self) -> Optional[str]:
        return self.qualifiers.get("21")

    @property
    def batch_lot(self) -> Optional[str]:
        return self.qualifiers.get("10")

    @property
    def cpv(self) -> Optional[str]:
        return self.qualifiers.get("22")

    @property
    def expiry_date(self) -> Optional[str]:
        return self.attributes.get("17")

    def as_dict(self) -> dict[str, str]:
        """Flat name → value mapping for template substitution."""
        out: dict[str, str] = {}
        if self.primary_ai:
            out[AI_TO_NAME.get(self.primary_ai, self.primary_ai)] = self.primary_value
            out[self.primary_ai] = self.primary_value
        for ai, value in {**self.qualifiers, **self.attributes}.items():
            name = AI_TO_NAME.get(ai, ai)
            out[name] = value
            out[ai] = value
        # Convenience aliases used in user-supplied templates
        out.setdefault("serial", self.qualifiers.get("21", ""))
        out.setdefault("batch",  self.qualifiers.get("10", ""))
        out.setdefault("expiry", self.attributes.get("17", ""))
        return out


def parse(uri: str) -> GS1ParseResult:
    """
    Parse a GS1 Digital Link URI into its components.

    Accepts both numeric AI form (/01/...) and alpha-coded form (/gtin/...).
    Strips the scheme and host — only the path and query string are parsed.

    Raises ValueError if no recognised primary key is present in the path.
    """
    parsed = urlparse(uri)
    path = parsed.path
    query = parse_qs(parsed.query, keep_blank_values=True)

    result = GS1ParseResult(query_params=query)
    result.link_type = query.get("linkType", [None])[0]

    # Normalise alpha-coded segments to numeric AI form
    path = _normalise_alpha(path)

    segments: list[tuple[str, str]] = _AI_PATH_RE.findall(path)
    if not segments:
        raise ValueError(f"No GS1 Application Identifiers found in path: {path!r}")

    primary_set = False
    for ai, value in segments:
        if ai in PRIMARY_AIS and not primary_set:
            result.primary_ai = ai
            result.primary_value = value
            primary_set = True
            continue
        if not is_known(ai):
            result.unknown_ais.append((ai, value))
            continue
        spec = AI_TO_SPEC[ai]
        if spec.category.value == "qualifier":
            result.qualifiers[ai] = value
        else:
            result.attributes[ai] = value

    if not primary_set:
        raise ValueError(f"No recognised primary key in path: {path!r}")

    return result


def _normalise_alpha(path: str) -> str:
    """Convert alpha-coded path segments to numeric AI form (case-insensitive)."""
    # Sort alpha names by length descending so longer names ('certref') win
    # over shorter prefixes that might overlap.
    for name in sorted(NAME_TO_AI.keys(), key=len, reverse=True):
        ai = NAME_TO_AI[name]
        path = re.sub(
            rf"(?<=/){re.escape(name)}/",
            f"{ai}/",
            path,
            flags=re.IGNORECASE,
        )
    return path


# --- GTIN check digit -------------------------------------------------------

def validate_gtin14(gtin: str) -> bool:
    """
    Validate a GTIN-14 string using the GS1 Modulo-10 check digit algorithm.

    GTIN-14 is the canonical length used in GS1 Digital Link URIs — shorter
    GTINs (8/12/13) MUST be left-padded with zeros before forming a DL URI.
    """
    if not re.fullmatch(r"\d{14}", gtin):
        return False
    digits = [int(d) for d in gtin]
    weighted = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(digits[:-1]))
    check = (10 - (weighted % 10)) % 10
    return check == digits[-1]


def pad_gtin_to_14(gtin: str) -> str:
    """Left-pad GTIN-8/12/13 with zeros to GTIN-14. Idempotent on GTIN-14."""
    if not gtin.isdigit():
        return gtin
    if len(gtin) in (8, 12, 13, 14):
        return gtin.zfill(14)
    return gtin


# --- Canonical URI generation ----------------------------------------------

def canonicalise(parsed: GS1ParseResult, host: str = "id.gs1.org") -> str:
    """
    Produce a canonical GS1 Digital Link URI for `parsed`.

    Canonical form (per GS1 DL §4.6):
      - host: id.gs1.org by default
      - primary key first
      - qualifiers in the order defined for the primary key
      - attributes in numeric-AI order
      - query parameters dropped (canonical form is path-only)
    """
    if not parsed.primary_ai:
        raise ValueError("Cannot canonicalise: no primary key set")

    parts = [f"/{parsed.primary_ai}/{quote(parsed.primary_value, safe='')}"]

    order = QUALIFIER_ORDER.get(parsed.primary_ai, ())
    seen: set[str] = set()
    for ai in order:
        if ai in parsed.qualifiers:
            parts.append(f"/{ai}/{quote(parsed.qualifiers[ai], safe='')}")
            seen.add(ai)
    # Append any qualifiers not in the ordered set, sorted by AI
    for ai in sorted(parsed.qualifiers):
        if ai not in seen:
            parts.append(f"/{ai}/{quote(parsed.qualifiers[ai], safe='')}")
    # Append attributes in numeric-AI order
    for ai in sorted(parsed.attributes):
        parts.append(f"/{ai}/{quote(parsed.attributes[ai], safe='')}")

    return f"https://{host}" + "".join(parts)
