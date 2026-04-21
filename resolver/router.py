"""
router.py — Routing engine for GS1 Digital Link resolution

Loads routing rules from a YAML config file and resolves parsed GS1 URIs
to DPP endpoint URLs, supporting content negotiation link sets.
"""

from __future__ import annotations

import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .parser import GS1ParseResult


@dataclass
class LinkType:
    rel: str
    href: str
    type: str = "text/html"
    title: str = ""
    hreflang: Optional[str] = None

    def resolve(self, ctx: dict) -> "LinkType":
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


class Router:
    def __init__(self, config_path: str | Path):
        self._routes: list[Route] = []
        self.load(config_path)

    def load(self, path: str | Path) -> None:
        with open(path) as f:
            config = yaml.safe_load(f)
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

    def resolve(self, parsed: GS1ParseResult) -> Optional[tuple[str, list[LinkType]]]:
        """
        Find the first matching route for the parsed GS1 URI.

        Returns (target_url, link_types) or None if no route matches.
        """
        ctx = parsed.as_dict()
        ctx.update({
            "gtin":   parsed.primary_value if parsed.primary_ai == "01" else "",
            "serial": parsed.qualifiers.get("21", ""),
            "batch":  parsed.qualifiers.get("10", ""),
            "expiry": parsed.qualifiers.get("17", ""),
        })

        for route in self._routes:
            if self._matches(route.match, parsed):
                target = _fill(route.target, ctx)
                links = [lt.resolve(ctx) for lt in route.link_types]
                return target, links
        return None

    def _matches(self, match: dict, parsed: GS1ParseResult) -> bool:
        if match == "*" or match == {}:
            return True
        if "gtin_prefix" in match:
            if not parsed.primary_value.startswith(match["gtin_prefix"]):
                return False
        if "gtin_regex" in match:
            if not re.fullmatch(match["gtin_regex"], parsed.primary_value):
                return False
        if "primary_ai" in match:
            if parsed.primary_ai != str(match["primary_ai"]):
                return False
        return True


def _fill(template: str, ctx: dict) -> str:
    """Replace {key} placeholders in template with ctx values."""
    for key, value in ctx.items():
        template = template.replace(f"{{{key}}}", value or "")
    return template
