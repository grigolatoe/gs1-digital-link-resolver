"""
parser.py — GS1 Digital Link URI parser

Parses GS1 Digital Link URIs per GS1 Digital Link Standard v1.2 / ISO 22742.

Reference: https://www.gs1.org/standards/gs1-digital-link

Supported forms:
  Uncompressed: /01/{gtin14}/21/{serial}?linkType=...
  Alpha-coded:  /gtin/{gtin14}/ser/{serial}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, parse_qs

# GS1 Application Identifier → field name (DPP-relevant subset)
_AI_TO_NAME: dict[str, str] = {
    "00": "sscc",
    "01": "gtin",
    "10": "batch_lot",
    "17": "expiry_date",
    "21": "serial_number",
    "22": "cpv",
    "235": "tpx",
    "414": "gln",
    "710": "nhrn_de",
    "711": "nhrn_fr",
    "712": "nhrn_es",
    "713": "nhrn_br",
    "714": "nhrn_pt",
    "723": "cert_ref",
    "8001": "roll_products",
    "8002": "cmid",
    "8003": "grai",
    "8004": "giai",
    "8006": "itip",
    "8007": "iban",
    "8008": "prod_time",
    "8010": "cpid",
    "8011": "cpid_serial",
    "8013": "gmn",
    "8017": "gsrn_provider",
    "8018": "gsrn_recipient",
    "8020": "ref",
    "8200": "product_url",
}

# Alpha-coded short names → AI (GS1 DL v1.2 §4.5)
_NAME_TO_AI: dict[str, str] = {
    "sscc":    "00",
    "gtin":    "01",
    "lot":     "10",
    "exp":     "17",
    "ser":     "21",
    "cpv":     "22",
    "tpx":     "235",
    "gln":     "414",
    "certref": "723",
    "grai":    "8003",
    "giai":    "8004",
    "itip":    "8006",
    "cpid":    "8010",
    "gmn":     "8013",
}

# Primary keys and their qualifier ordering (GS1 DL v1.2 §4.4)
_PRIMARY_KEYS = {"00", "01", "253", "255", "414", "8003", "8004", "8006", "8010", "8013", "8017", "8018"}

# Regex: numeric AI path segment — /NN.../ followed by value
_AI_PATH_RE = re.compile(r"/(\d{2,4})/([^/]*)")


@dataclass
class GS1ParseResult:
    """Result of parsing a GS1 Digital Link URI."""
    primary_ai: str = ""           # e.g. "01"
    primary_value: str = ""        # e.g. "09780345418913"
    qualifiers: dict[str, str] = field(default_factory=dict)   # AI → value
    query_params: dict[str, list[str]] = field(default_factory=dict)
    link_type: Optional[str] = None

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
    def expiry_date(self) -> Optional[str]:
        return self.qualifiers.get("17")

    def as_dict(self) -> dict:
        result = {_AI_TO_NAME.get(self.primary_ai, self.primary_ai): self.primary_value}
        for ai, value in self.qualifiers.items():
            result[_AI_TO_NAME.get(ai, ai)] = value
        return result


def parse(uri: str) -> GS1ParseResult:
    """
    Parse a GS1 Digital Link URI into its components.

    Accepts both numeric AI form (/01/...) and alpha-coded form (/gtin/...).
    Strips the scheme and host — only the path and query string are parsed.

    Raises ValueError if no primary key is found in the path.
    """
    parsed = urlparse(uri)
    path = parsed.path
    query = parse_qs(parsed.query)

    result = GS1ParseResult(query_params=query)
    result.link_type = query.get("linkType", [None])[0]

    # Normalise alpha-coded segments to numeric AI form
    path = _normalise_alpha(path)

    # Extract all AI/value pairs from path
    segments: list[tuple[str, str]] = _AI_PATH_RE.findall(path)
    if not segments:
        raise ValueError(f"No GS1 Application Identifiers found in path: {path!r}")

    primary_set = False
    for ai, value in segments:
        if ai in _PRIMARY_KEYS and not primary_set:
            result.primary_ai = ai
            result.primary_value = value
            primary_set = True
        else:
            result.qualifiers[ai] = value

    if not primary_set:
        raise ValueError(f"No recognised primary key in path: {path!r}")

    return result


def _normalise_alpha(path: str) -> str:
    """Convert alpha-coded path segments to numeric AI form."""
    for name, ai in _NAME_TO_AI.items():
        path = re.sub(
            rf"(?<=/){re.escape(name)}/",
            f"{ai}/",
            path,
            flags=re.IGNORECASE,
        )
    return path


def validate_gtin14(gtin: str) -> bool:
    """
    Validate a GTIN-14 string using the GS1 Modulo-10 check digit algorithm.

    Returns True if the GTIN is exactly 14 digits and the check digit is correct.
    """
    if not re.fullmatch(r"\d{14}", gtin):
        return False
    digits = [int(d) for d in gtin]
    total = sum(
        d * (3 if i % 2 == 0 else 1)
        for i, d in enumerate(digits[:-1])
    )
    check = (10 - (total % 10)) % 10
    return check == digits[-1]
