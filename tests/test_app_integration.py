"""
HTTP integration tests for the resolver service.

These run the full FastAPI app against the shipped example config and
exercise the content-negotiation matrix that the README documents:

  Accept: application/linkset+json  -> 200 RFC 9264 link-set
  Accept: application/ld+json       -> 200 JSON-LD link-set
  Accept: text/html                 -> 302 to the default link's href
  ?linkType=gs1:foo                 -> link-set narrowed to that relation

Plus the boundary behaviours:

  - GTIN-14 with bad mod-10 check digit -> 400
  - GTIN that matches only the wildcard fallback -> resolves to the global registry
  - Path with no GS1 AIs at all -> 400
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

EXAMPLE_CONFIG = Path(__file__).parent.parent / "config" / "routes.example.yaml"


@pytest.fixture(scope="module")
def client() -> TestClient:
    # CONFIG_PATH is read at app-module import time, so set the env var
    # before the first import AND patch the already-loaded module so a
    # previously-cached value can't bleed in from unit tests run earlier.
    os.environ["CONFIG_PATH"] = str(EXAMPLE_CONFIG)
    import resolver.app as app_module

    app_module.CONFIG_PATH = EXAMPLE_CONFIG
    app_module._router = None  # reset memoised router
    return TestClient(app_module.app)


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_resolve_returns_rfc9264_linkset(client: TestClient) -> None:
    """GS1 DL §A.1 shape: /01/{gtin}/21/{serial} -> RFC 9264 link-set."""
    response = client.get(
        "/01/09780345418913/21/SER123",
        headers={"Accept": "application/linkset+json"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/linkset+json")

    body = response.json()
    assert "linkset" in body
    assert len(body["linkset"]) == 1
    entry = body["linkset"][0]

    # anchor must reflect the inbound URL (per RFC 9264 §4.2.4.2)
    assert "anchor" in entry
    assert "/01/09780345418913/21/SER123" in entry["anchor"]

    # Relations are expanded to GS1 Web Vocabulary IRIs
    assert "https://gs1.org/voc/pip" in entry
    assert "https://gs1.org/voc/verificationService" in entry
    assert "https://gs1.org/voc/digitalProductPassport" in entry

    # When no defaultLink is declared, the first declared link is promoted
    assert "https://gs1.org/voc/defaultLink" in entry

    # Template substitution wired {gtin} and {serial} into the href
    pip = entry["https://gs1.org/voc/pip"][0]
    assert pip["href"] == "https://dpp.example.com/passport/09780345418913/SER123"
    assert pip["type"] == "text/html"
    assert pip["title"] == "Digital Product Passport"


def test_resolve_jsonld(client: TestClient) -> None:
    """Accept: application/ld+json -> JSON-LD wrap with GS1 vocab @context."""
    response = client.get(
        "/01/09780345418913/21/SER123",
        headers={"Accept": "application/ld+json"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/ld+json")

    body = response.json()
    assert "@context" in body
    ctx = body["@context"]
    assert isinstance(ctx, list)
    # Binds the gs1: prefix so relation IRIs resolve under JSON-LD processing
    assert any(isinstance(item, dict) and item.get("gs1") == "https://gs1.org/voc/" for item in ctx)
    # And carries the linkset.jsonld context per RFC 9264
    assert any(item == "https://www.w3.org/ns/linkset.jsonld" for item in ctx)
    # Underlying link-set payload is still there
    assert "linkset" in body


def test_resolve_html_redirects_302(client: TestClient) -> None:
    """Accept: text/html -> 302 to the resolved default-link href."""
    response = client.get(
        "/01/09780345418913/21/SER123",
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "https://dpp.example.com/passport/09780345418913/SER123"


def test_link_type_query_filters_relation(client: TestClient) -> None:
    """?linkType=gs1:verificationService narrows the link-set to that one rel."""
    response = client.get(
        "/01/09780345418913/21/SER123",
        params={"linkType": "gs1:verificationService"},
        headers={"Accept": "application/linkset+json"},
    )
    assert response.status_code == 200
    entry = response.json()["linkset"][0]
    assert "https://gs1.org/voc/verificationService" in entry
    # pip and dpp relations are filtered out
    assert "https://gs1.org/voc/pip" not in entry
    assert "https://gs1.org/voc/digitalProductPassport" not in entry


def test_invalid_gtin_check_digit_returns_400(client: TestClient) -> None:
    """A GTIN-14 with the wrong mod-10 check digit is rejected at the edge."""
    # 09780345418913 is a valid GTIN-14; flipping the final digit makes it invalid
    response = client.get("/01/09780345418914")
    assert response.status_code == 400
    assert "Invalid GTIN-14" in response.json()["error"]


def test_unmatched_gtin_falls_back_to_global_resolver(client: TestClient) -> None:
    """
    A well-formed GTIN that doesn't match any branded route must fall through
    to the wildcard route. The example config forwards those to the GS1 global
    resolver — a real-world pattern that lets operators ship without owning
    every GTIN range.
    """
    # 00012345678905 has a valid mod-10 check digit (GTIN-12 padded) but
    # prefix "0001" does not match the example config's "0978" route.
    response = client.get(
        "/01/00012345678905",
        headers={"Accept": "application/linkset+json"},
    )
    assert response.status_code == 200
    entry = response.json()["linkset"][0]
    pip = entry["https://gs1.org/voc/pip"][0]
    assert pip["href"] == "https://id.gs1.org/01/00012345678905"
    assert pip["title"] == "GS1 Global Registry"


def test_malformed_path_returns_400(client: TestClient) -> None:
    """A path with no GS1 Application Identifiers at all is rejected."""
    response = client.get("/not/a/gs1/path")
    assert response.status_code == 400


def test_validation_status_surfaced_when_smoke_validator_active(
    client: TestClient,
) -> None:
    """
    The example config enables the smoke validator. Its output must appear
    as `gs1:validationStatus` alongside the link-set entry (advisory, never
    blocks resolution).
    """
    response = client.get(
        "/01/09780345418913/21/SER123",
        headers={"Accept": "application/linkset+json"},
    )
    entry = response.json()["linkset"][0]
    assert "gs1:validationStatus" in entry
    assert entry["gs1:validationStatus"]["profile"] == "smoke-builtin-v1"
    assert entry["gs1:validationStatus"]["ok"] is True
