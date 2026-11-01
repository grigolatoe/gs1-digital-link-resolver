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

Optional per route:

  forward_query: ["qk", "nk"]  — query parameters copied from the incoming
                                  URI onto the target and every link href, so
                                  a carrier key printed after the "?" (a
                                  verification token, a campaign tag) reaches
                                  the DPP endpoint. Only the names listed are
                                  forwarded; anything else is dropped, as before.

Templates may reference any of: primary AI numeric ({01}), primary alpha
({gtin}), qualifier AIs/aliases, attribute AIs/aliases, plus convenience
aliases {serial}, {batch}, {expiry}.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml

from .parser import GS1ParseResult
from .validator import NoOpValidator, Validator, load_validator
from .wellknown import WellKnownConfigError, validate_well_known_config

# The config schema is versioned and stable under SemVer (see docs/stability.md).
# A breaking change to the schema bumps this major. `version:` is optional in
# routes.yaml; when omitted the current major is assumed.
CONFIG_SCHEMA_VERSION = 1


class ConfigError(ValueError):
    """Raised when routes.yaml is structurally invalid — fail fast at startup."""


def _validate_config(config: object) -> dict:
    """Validate the parsed routes.yaml shape, raising ConfigError with an
    actionable message. The resolver must refuse to start on a broken config
    rather than fail confusingly at request time."""
    if not isinstance(config, dict):
        raise ConfigError("config root must be a mapping (a YAML object)")

    version = config.get("version")
    if version is not None:
        try:
            major = int(version)
        except (TypeError, ValueError):
            raise ConfigError(f"config 'version' must be an integer, got {version!r}") from None
        if major != CONFIG_SCHEMA_VERSION:
            raise ConfigError(
                f"unsupported config version {major}; this resolver supports "
                f"schema version {CONFIG_SCHEMA_VERSION}"
            )

    resolvers = config.get("resolvers")
    if resolvers is None:
        raise ConfigError("config must define a 'resolvers' list")
    if not isinstance(resolvers, list) or not resolvers:
        raise ConfigError("'resolvers' must be a non-empty list")

    for i, rule in enumerate(resolvers):
        where = f"resolvers[{i}]"
        if not isinstance(rule, dict):
            raise ConfigError(f"{where} must be a mapping")
        if "target" not in rule or not isinstance(rule["target"], str) or not rule["target"]:
            raise ConfigError(f"{where} must have a non-empty string 'target'")

        match = rule.get("match", {})
        if match not in ("*", {}, None) and not isinstance(match, dict):
            raise ConfigError(f"{where}.match must be '*' or a mapping of clauses")

        fq = rule.get("forward_query")
        if fq is not None and (
            not isinstance(fq, list) or not all(isinstance(n, str) and n for n in fq)
        ):
            raise ConfigError(f"{where}.forward_query must be a list of non-empty strings")

        for j, lt in enumerate(rule.get("link_types", []) or []):
            ltwhere = f"{where}.link_types[{j}]"
            if not isinstance(lt, dict):
                raise ConfigError(f"{ltwhere} must be a mapping")
            for required in ("rel", "href"):
                if required not in lt or not isinstance(lt[required], str) or not lt[required]:
                    raise ConfigError(f"{ltwhere} must have a non-empty string '{required}'")

    # A malformed description file would be served as non-conformant JSON at
    # /.well-known/gs1resolver, so it fails the service at startup like any
    # other broken config rather than surfacing at request time.
    try:
        validate_well_known_config(config.get("well_known"))
    except WellKnownConfigError as e:
        raise ConfigError(str(e)) from None

    return config


@dataclass
class LinkType:
    rel: str
    href: str
    type: str = "text/html"
    title: str = ""
    hreflang: str | None = None

    def resolve(
        self, ctx: dict[str, str], forward: list[tuple[str, str]] | None = None
    ) -> LinkType:
        return LinkType(
            rel=self.rel,
            href=_append_query(_fill(self.href, ctx), forward),
            type=self.type,
            title=_fill(self.title, ctx),
            hreflang=self.hreflang,
        )


@dataclass
class Route:
    match: dict
    target: str
    link_types: list[LinkType] = field(default_factory=list)
    forward_query: list[str] = field(default_factory=list)

    def forwarded(self, parsed: GS1ParseResult) -> list[tuple[str, str]]:
        """The (name, value) pairs of the incoming query this route forwards,
        in the order the route lists the names."""
        return [
            (name, value)
            for name in self.forward_query
            for value in parsed.query_params.get(name, [])
        ]

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
        self.well_known: dict = {}
        if config_path is not None:
            self.load(config_path)

    @property
    def routes(self) -> list[Route]:
        """The loaded routes, in match order (read-only view)."""
        return list(self._routes)

    def load(self, path: str | Path) -> None:
        with open(path) as f:
            config = yaml.safe_load(f) or {}
        _validate_config(config)
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
            self._routes.append(
                Route(
                    match=rule.get("match", {}),
                    target=rule["target"],
                    link_types=link_types,
                    forward_query=list(rule.get("forward_query") or []),
                )
            )
        self.validator = load_validator(config.get("validator"))
        self.well_known = validate_well_known_config(config.get("well_known"))

    def resolve(self, parsed: GS1ParseResult) -> tuple[str, list[LinkType]] | None:
        """
        Find the first matching route for the parsed GS1 URI.

        Returns (target_url, link_types) or None if no route matches.
        Templates in target and link href/title are filled with values from
        the parsed URI (numeric AI, alpha name, and convenience aliases).
        """
        ctx = parsed.as_dict()
        for route in self._routes:
            if route.matches(parsed):
                forward = route.forwarded(parsed)
                target = _append_query(_fill(route.target, ctx), forward)
                links = [lt.resolve(ctx, forward) for lt in route.link_types]
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


def _append_query(url: str, pairs: list[tuple[str, str]] | None) -> str:
    """Append forwarded query pairs to url, keeping any query it already has."""
    if not pairs or not url:
        return url
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True) + list(pairs)
    return urlunsplit(parts._replace(query=urlencode(query)))
