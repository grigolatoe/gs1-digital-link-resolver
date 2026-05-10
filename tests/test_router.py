"""Tests for the routing engine and route matching."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from resolver.parser import parse
from resolver.router import LinkType, Route, Router


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "routes.yaml"
    p.write_text(textwrap.dedent(content))
    return p


# --- Match clauses ----------------------------------------------------------

class TestMatchClauses:
    def test_wildcard_matches_anything(self):
        r = Route(match="*", target="https://x/{gtin}")
        assert r.matches(parse("/01/09780345418913"))

    def test_empty_dict_matches_anything(self):
        r = Route(match={}, target="https://x/{gtin}")
        assert r.matches(parse("/01/09780345418913"))

    def test_primary_ai_clause(self):
        r = Route(match={"primary_ai": "01"}, target="x")
        assert r.matches(parse("/01/09780345418913"))
        assert not r.matches(parse("/8003/095555550000200"))

    def test_gtin_prefix(self):
        # GTIN-14 is left-padded with zero, so internal-range "200" prefix
        # appears at offset 1: "02000..."
        r = Route(match={"gtin_prefix": "0200"}, target="x")
        assert r.matches(parse("/01/02000000000017"))
        assert not r.matches(parse("/01/09780345418913"))

    def test_gtin_regex(self):
        r = Route(match={"gtin_regex": r"^09780.*$"}, target="x")
        assert r.matches(parse("/01/09780345418913"))
        assert not r.matches(parse("/01/09790000000004"))

    def test_has_qualifier_serial(self):
        r = Route(match={"has_qualifier": "21"}, target="x")
        assert r.matches(parse("/01/09780345418913/21/SER"))
        assert not r.matches(parse("/01/09780345418913"))

    def test_serial_in_allowlist(self):
        r = Route(match={"serial_in": ["DEMO-A", "DEMO-B"]}, target="x")
        assert r.matches(parse("/01/09780345418913/21/DEMO-A"))
        assert not r.matches(parse("/01/09780345418913/21/REAL"))

    def test_compound_match_all_must_pass(self):
        r = Route(
            match={"primary_ai": "01", "gtin_prefix": "0200", "has_qualifier": "21"},
            target="x",
        )
        assert r.matches(parse("/01/02000000000017/21/SER"))
        assert not r.matches(parse("/01/02000000000017"))               # no serial
        assert not r.matches(parse("/01/09780345418913/21/SER"))        # wrong prefix


# --- YAML loading + routing -------------------------------------------------

class TestRouterFromYaml:
    def test_first_match_wins(self, tmp_path):
        cfg = _write_yaml(tmp_path, """
            resolvers:
              - match:
                  gtin_prefix: "0978"
                target: "https://books.test/{gtin}"
              - match: "*"
                target: "https://default.test/{gtin}"
        """)
        router = Router(cfg)

        target, _ = router.resolve(parse("/01/09780345418913"))
        assert target == "https://books.test/09780345418913"

        target, _ = router.resolve(parse("/01/02000000000017"))
        assert target == "https://default.test/02000000000017"

    def test_link_type_template_substitution(self, tmp_path):
        cfg = _write_yaml(tmp_path, """
            resolvers:
              - match: "*"
                target: "https://dpp.test/p/{gtin}/{serial}"
                link_types:
                  - rel: "gs1:pip"
                    href: "https://dpp.test/p/{gtin}/{serial}"
                    title: "Passport for {gtin}"
                  - rel: "gs1:verificationService"
                    href: "https://dpp.test/api/verify/{gtin}/{serial}"
                    type: "application/json"
        """)
        router = Router(cfg)
        _, links = router.resolve(parse("/01/09780345418913/21/SER01"))
        pip = next(lt for lt in links if lt.rel == "gs1:pip")
        ver = next(lt for lt in links if lt.rel == "gs1:verificationService")
        assert pip.href == "https://dpp.test/p/09780345418913/SER01"
        assert pip.title == "Passport for 09780345418913"
        assert ver.href == "https://dpp.test/api/verify/09780345418913/SER01"
        assert ver.type == "application/json"

    def test_no_match_returns_none(self, tmp_path):
        cfg = _write_yaml(tmp_path, """
            resolvers:
              - match:
                  gtin_prefix: "978"
                target: "https://x/{gtin}"
        """)
        router = Router(cfg)
        assert router.resolve(parse("/01/02000000000017")) is None

    def test_grai_routing(self, tmp_path):
        cfg = _write_yaml(tmp_path, """
            resolvers:
              - match:
                  primary_ai: "8003"
                target: "https://assets.test/grai/{8003}"
        """)
        router = Router(cfg)
        target, _ = router.resolve(parse("/8003/095555550000200"))
        assert target == "https://assets.test/grai/095555550000200"

    def test_serial_allowlist_route(self, tmp_path):
        # Useful for demo / test products that should bypass the live DPP.
        cfg = _write_yaml(tmp_path, """
            resolvers:
              - match:
                  serial_in: ["DEMO-A", "DEMO-B"]
                target: "https://demo.test/{gtin}/{serial}"
              - match: "*"
                target: "https://prod.test/{gtin}/{serial}"
        """)
        router = Router(cfg)
        t, _ = router.resolve(parse("/01/09780345418913/21/DEMO-A"))
        assert t.startswith("https://demo.test/")
        t, _ = router.resolve(parse("/01/09780345418913/21/REAL"))
        assert t.startswith("https://prod.test/")
