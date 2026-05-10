"""
router.py — Routing engine for GS1 Digital Link resolution

Loads routing rules from a YAML config file and resolves parsed GS1 URIs
to DPP endpoint URLs plus a list of typed links suitable for an RFC 9264
link-set response.

Match clauses (any combination, all must match):

  primary_ai:    "01"          — only this primary key applies
  gtin_prefix:   "978"         — primary value (any primary, but typically
                                  GTIN) starts with this prefix
  gtin_regex:    "^...$"       — full match against the primary value
  has_qualifier: "21"          — at least this qualifier AI is present
  serial_in:    ["A", "B"]     — serial number is one of these literals

A match shorthand of "*" (or {}) acts as a default fallback rule.

Templates may reference any of: primary AI numeric ({01}), primary alpha
({gtin}), qualifier AIs/aliases, attribute AIs/aliases, plus convenience
aliases {serial}, {batch}, {expiry}.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .parser import GS1ParseResult
from .validator import NoOpValidator, Validator, load_validator


@dataclass
class LinkType:
    rel: str
    href: str
    type: str = "text/html"
    title: str = ""
    hreflang: Optional[str] = None

    def resolve(self, ctx: dict[str, str]) -> "LinkType":
        return LinkType(
            rel=self.rel,
            href=_fill(self.href, ctx),
            type=self.type,
            title=_fill(self.title, ctx),
            hreflang=self.hreflang,
        )


@dataclass
class Route:
    match: dict
    target: str
    link_types: list[LinkType] = field(default_factory=list)

    def matches(self, parsed: GS1ParseResult) -> bool:
        if self.match in ("*", {}, None):
            return True
        m = self.match
        if "primary_ai" in m:
            if parsed.primary_ai != str(m["primary_ai"]):
                return False
        if "gtin_prefix" in m:
            if not parsed.primary_value.startswith(str(m["gtin_prefix"])):
                return False
        if "gtin_regex" in m:
            if not re.fullmatch(m["gtin_regex"], parsed.primary_value):
                return False
        if "has_qualifier" in m:
            if str(m["has_qualifier"]) not in parsed.qualifiers:
                return False
        if "serial_in" in m:
            serial = parsed.qualifiers.get("21")
            if serial is None or serial not in m["serial_in"]:
                return False
        return True


class Router:
    def __init__(self, config_path: str | Path | None = None):
        self._routes: list[Route] = []
        self.validator: Validator = NoOpValidator()
        if config_path is not None:
            self.load(config_path)

    def load(self, path: str | Path) -> None:
        with open(path) as f:
            config = yaml.safe_load(f) or {}
        self._routes = []
        for rule in config.get("resolvers", []):
            link_types = [
                LinkType(
                    rel=lt["rel"],
                    href=lt["href"],
                    type=lt.get("type", "text/html"),
                    title=lt.get("title", ""),
                    hreflang=lt.get("hreflang"),
                )
                for lt in rule.get("link_types", [])
            ]
            self._routes.append(Route(
                match=rule.get("match", {}),
                target=rule["target"],
                link_types=link_types,
            ))
        self.validator = load_validator(config.get("validator"))

    def resolve(self, parsed: GS1ParseResult) -> Optional[tuple[str, list[LinkType]]]:
        """
        Find the first matching route for the parsed GS1 URI.

        Returns (target_url, link_types) or None if no route matches.
        Templates in target and link href/title are filled with values from
        the parsed URI (numeric AI, alpha name, and convenience aliases).
        """
        ctx = parsed.as_dict()
        for route in self._routes:
            if route.matches(parsed):
                target = _fill(route.target, ctx)
                links = [lt.resolve(ctx) for lt in route.link_types]
                return target, links
        return None


def _fill(template: str, ctx: dict[str, str]) -> str:
    """Replace {key} placeholders in template with ctx values."""
    if not template:
        return template
    # Sort keys longest-first so 'serial' is replaced before 'ser', etc.
    for key in sorted(ctx.keys(), key=len, reverse=True):
        template = template.replace(f"{{{key}}}", ctx[key] or "")
    return template
