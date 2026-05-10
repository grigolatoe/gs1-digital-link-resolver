"""
negotiate.py — Accept-header content negotiation for the resolver

The resolver advertises four media types, in this preference order:

  1. application/linkset+json   — RFC 9264 link-set, the modern default
  2. application/ld+json        — JSON-LD wrapper for semantic-web consumers
  3. application/json           — RFC 9264 shape for plain-JSON consumers
  4. text/html                  — 302 redirect to the default link

This module parses an Accept header (with q-values) and picks the highest-
ranked match. If the client sends a wildcard or no Accept header, the default
is `application/linkset+json` per GS1 DL conformance guidance.
"""

from __future__ import annotations

OFFERS = (
    "application/linkset+json",
    "application/ld+json",
    "application/json",
    "text/html",
)

DEFAULT = "application/linkset+json"


def _parse_accept(accept: str) -> list[tuple[str, float]]:
    """Return [(media_type, q), ...] sorted by descending q."""
    if not accept:
        return []
    parts: list[tuple[str, float]] = []
    for entry in accept.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ";" in entry:
            mt, *params = (p.strip() for p in entry.split(";"))
            q = 1.0
            for p in params:
                if p.startswith("q="):
                    try:
                        q = float(p[2:])
                    except ValueError:
                        q = 0.0
            parts.append((mt, q))
        else:
            parts.append((entry, 1.0))
    parts.sort(key=lambda x: x[1], reverse=True)
    return parts


def _matches(offer: str, pattern: str) -> bool:
    if pattern == "*/*":
        return True
    if pattern.endswith("/*"):
        return offer.split("/", 1)[0] == pattern.split("/", 1)[0]
    return offer == pattern


def select_media_type(accept: str) -> str:
    """
    Choose the best server-offered media type for a given Accept header.

    Falls back to `application/linkset+json` when nothing matches or when
    the header is empty/wildcard, which is the GS1 DL recommended default
    for resolver responses.
    """
    parsed = _parse_accept(accept)
    if not parsed:
        return DEFAULT

    # Walk client preferences in q-order; for each, return the first server
    # offer that matches. If the client lists multiple types at the same q,
    # respect the client's stated order.
    for pattern, q in parsed:
        if q <= 0:
            continue
        for offer in OFFERS:
            if _matches(offer, pattern):
                return offer

    return DEFAULT
