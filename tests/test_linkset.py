"""Tests for RFC 9264 link-set construction and content negotiation."""

from __future__ import annotations

import pytest

from resolver.linkset import (
    GS1_VOC,
    SHORT_TO_VOC,
    build_jsonld,
    build_linkset,
    default_link_href,
    expand_rel,
)
from resolver.negotiate import select_media_type
from resolver.router import LinkType


def _link(rel: str, href: str, ctype: str = "text/html", title: str = "") -> LinkType:
    return LinkType(rel=rel, href=href, type=ctype, title=title)


class TestExpandRel:
    def test_short_form_expands_to_voc(self):
        assert expand_rel("gs1:pip") == GS1_VOC + "pip"

    def test_unknown_short_form_still_uses_voc_namespace(self):
        assert expand_rel("gs1:somethingNew") == GS1_VOC + "somethingNew"

    def test_full_iri_passthrough(self):
        assert expand_rel("https://example.org/rel/foo") == "https://example.org/rel/foo"

    def test_bare_token_passthrough(self):
        # RFC 8288 well-known names (e.g. "next", "prev") stay as-is
        assert expand_rel("next") == "next"


class TestLinkSet:
    def test_minimal_linkset_when_no_links(self):
        ls = build_linkset(anchor="https://x.test/01/0", links=[])
        assert ls == {"linkset": [{"anchor": "https://x.test/01/0"}]}

    def test_relations_use_full_voc_iri(self):
        ls = build_linkset(
            anchor="https://x.test/01/0",
            links=[_link("gs1:pip", "https://dpp.test/p/1")],
        )
        entry = ls["linkset"][0]
        assert SHORT_TO_VOC["gs1:pip"] in entry
        assert entry[SHORT_TO_VOC["gs1:pip"]][0]["href"] == "https://dpp.test/p/1"

    def test_default_link_is_promoted_when_absent(self):
        ls = build_linkset(
            anchor="https://x.test/01/0",
            links=[_link("gs1:pip", "https://dpp.test/p/1")],
        )
        href = default_link_href(ls)
        assert href == "https://dpp.test/p/1"

    def test_explicit_default_link_is_kept(self):
        ls = build_linkset(
            anchor="https://x.test/01/0",
            links=[
                _link("gs1:pip", "https://dpp.test/p/1"),
                _link("gs1:defaultLink", "https://dpp.test/landing"),
            ],
        )
        href = default_link_href(ls)
        assert href == "https://dpp.test/landing"

    def test_link_type_filter_narrows_response(self):
        ls = build_linkset(
            anchor="https://x.test/01/0",
            links=[
                _link("gs1:pip", "https://dpp.test/p"),
                _link("gs1:verificationService", "https://dpp.test/verify", ctype="application/json"),
            ],
            requested_link_type="gs1:verificationService",
        )
        entry = ls["linkset"][0]
        assert SHORT_TO_VOC["gs1:verificationService"] in entry
        assert SHORT_TO_VOC["gs1:pip"] not in entry

    def test_link_type_filter_no_match_falls_back_to_full_set(self):
        ls = build_linkset(
            anchor="https://x.test/01/0",
            links=[_link("gs1:pip", "https://dpp.test/p")],
            requested_link_type="gs1:somethingMissing",
        )
        # No match → return all links unfiltered
        assert SHORT_TO_VOC["gs1:pip"] in ls["linkset"][0]


class TestJsonLdWrapper:
    def test_jsonld_wraps_with_context(self):
        ls = build_linkset(
            anchor="https://x.test/01/0",
            links=[_link("gs1:pip", "https://dpp.test/p")],
        )
        jl = build_jsonld(ls)
        assert "@context" in jl
        contexts = jl["@context"]
        assert "https://www.w3.org/ns/linkset.jsonld" in contexts
        gs1_binding = next(c for c in contexts if isinstance(c, dict))
        assert gs1_binding["gs1"] == GS1_VOC


class TestNegotiation:
    def test_empty_accept_returns_default_linkset(self):
        assert select_media_type("") == "application/linkset+json"

    def test_wildcard_returns_default(self):
        assert select_media_type("*/*") == "application/linkset+json"

    def test_html_picks_html(self):
        assert select_media_type("text/html") == "text/html"

    def test_explicit_jsonld(self):
        assert select_media_type("application/ld+json") == "application/ld+json"

    def test_explicit_linkset_json(self):
        assert select_media_type("application/linkset+json") == "application/linkset+json"

    def test_q_value_ordering(self):
        # Client prefers HTML, falls back to linkset+json
        assert select_media_type("text/html;q=0.9, application/linkset+json;q=0.5") == "text/html"

    def test_q_zero_disqualifies(self):
        # Client refuses HTML; should pick linkset+json from wildcard
        assert select_media_type("text/html;q=0, */*;q=0.5") == "application/linkset+json"

    def test_browser_default_accept(self):
        # Modern browser default
        accept = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        assert select_media_type(accept) == "text/html"

    def test_machine_consumer_accept(self):
        accept = "application/json"
        # application/json is in our offer list; we return it as-is
        assert select_media_type(accept) == "application/json"
