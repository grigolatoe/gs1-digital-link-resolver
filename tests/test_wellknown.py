# provenance: created by claude-opus-5 on 2026-09-04T17:17:13Z
"""
Tests for the GS1 resolver description file (`/.well-known/gs1resolver`).

The document is required of a conformant resolver and SHALL validate against
https://ref.gs1.org/standards/resolver/description-file-schema — so these tests
assert the schema's constraints directly (mandatory fields, permitted values,
JSON types) rather than fetching the schema at test time, which would make the
suite depend on the network.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from resolver.router import ConfigError, Router
from resolver.wellknown import (
    SUPPORTED_PRIMARY_KEYS,
    WELL_KNOWN_PATH,
    WellKnownConfigError,
    build_well_known,
    derive_primary_keys,
    validate_well_known_config,
)

EXAMPLE_CONFIG = Path(__file__).parent.parent / "config" / "routes.example.yaml"


@pytest.fixture(scope="module")
def client() -> TestClient:
    os.environ["CONFIG_PATH"] = str(EXAMPLE_CONFIG)
    import resolver.app as app_module

    app_module.CONFIG_PATH = EXAMPLE_CONFIG
    app_module._router = None  # reset memoised router
    return TestClient(app_module.app)


def _router_for(tmp_path: Path, config: dict) -> Router:
    path = tmp_path / "routes.yaml"
    path.write_text(yaml.safe_dump(config))
    return Router(path)


# --------------------------------------------------------------------------
# Served document
# --------------------------------------------------------------------------


def test_served_at_the_reserved_path(client: TestClient) -> None:
    """The standard reserves /.well-known/gs1resolver for this document."""
    assert WELL_KNOWN_PATH == "/.well-known/gs1resolver"
    response = client.get(WELL_KNOWN_PATH)
    assert response.status_code == 200


def test_media_type_is_application_json(client: TestClient) -> None:
    response = client.get(WELL_KNOWN_PATH)
    assert response.headers["content-type"].startswith("application/json")


def test_not_swallowed_by_the_catch_all_resolver_route(client: TestClient) -> None:
    """Without an explicit route the path would parse as a GS1 URI and 400."""
    response = client.get(WELL_KNOWN_PATH)
    assert response.status_code == 200
    assert "error" not in response.json()


def test_mandatory_fields_present(client: TestClient) -> None:
    body = client.get(WELL_KNOWN_PATH).json()
    assert isinstance(body["resolverRoot"], str) and body["resolverRoot"]
    assert isinstance(body["supportedPrimaryKeys"], list)
    assert body["supportedPrimaryKeys"]


def test_supported_primary_keys_are_all_permitted_values(client: TestClient) -> None:
    body = client.get(WELL_KNOWN_PATH).json()
    for key in body["supportedPrimaryKeys"]:
        assert key in SUPPORTED_PRIMARY_KEYS


def test_derived_keys_reflect_the_example_routes(client: TestClient) -> None:
    """The example config routes GTINs and one GRAI rule (AI 8003)."""
    body = client.get(WELL_KNOWN_PATH).json()
    assert body["supportedPrimaryKeys"] == ["01", "8003"]


def test_resolver_root_defaults_to_the_request_origin(client: TestClient) -> None:
    body = client.get(WELL_KNOWN_PATH).json()
    assert body["resolverRoot"] == "http://testserver"
    assert not body["resolverRoot"].endswith("/")


def test_optional_operator_metadata_is_published(client: TestClient) -> None:
    body = client.get(WELL_KNOWN_PATH).json()
    assert body["name"] == "Example DPP Resolver"
    assert body["contact"]["fn"] == "Example Brand B.V."


def test_healthz_and_metrics_still_route(client: TestClient) -> None:
    """Adding a route above the catch-all must not shadow the existing ones."""
    assert client.get("/healthz").status_code == 200
    assert client.get("/metrics").status_code == 200


def test_resolution_still_works(client: TestClient) -> None:
    response = client.get(
        "/01/09780345418913/21/SER123",
        headers={"Accept": "application/linkset+json"},
    )
    assert response.status_code == 200


# --------------------------------------------------------------------------
# Deriving supportedPrimaryKeys
# --------------------------------------------------------------------------


def test_derive_from_primary_ai_clause(tmp_path: Path) -> None:
    router = _router_for(
        tmp_path,
        {"resolvers": [{"match": {"primary_ai": "8006"}, "target": "https://e.example/{8006}"}]},
    )
    assert derive_primary_keys(router.routes) == ["8006"]


def test_gtin_clauses_imply_ai_01(tmp_path: Path) -> None:
    router = _router_for(
        tmp_path,
        {"resolvers": [{"match": {"gtin_prefix": "0978"}, "target": "https://e.example/{gtin}"}]},
    )
    assert derive_primary_keys(router.routes) == ["01"]


def test_catch_all_is_not_reported_as_all(tmp_path: Path) -> None:
    """A fallback rule matches anything, but "all" is a deliberate claim."""
    router = _router_for(
        tmp_path,
        {"resolvers": [{"match": "*", "target": "https://id.gs1.org/01/{gtin}"}]},
    )
    assert derive_primary_keys(router.routes) == ["01"]
    assert "all" not in derive_primary_keys(router.routes)


def test_non_primary_ai_route_is_not_published(tmp_path: Path) -> None:
    """AI 10 (batch) is a qualifier, not a primary key — it must not leak in."""
    router = _router_for(
        tmp_path,
        {"resolvers": [{"match": {"primary_ai": "10"}, "target": "https://e.example/x"}]},
    )
    assert derive_primary_keys(router.routes) == ["01"]


def test_derived_keys_are_sorted_and_deduplicated(tmp_path: Path) -> None:
    router = _router_for(
        tmp_path,
        {
            "resolvers": [
                {"match": {"primary_ai": "8003"}, "target": "https://e.example/a"},
                {"match": {"gtin_prefix": "0978"}, "target": "https://e.example/b"},
                {"match": {"gtin_regex": "^02[0-9]{12}$"}, "target": "https://e.example/c"},
            ]
        },
    )
    assert derive_primary_keys(router.routes) == ["01", "8003"]


def test_explicit_keys_override_derivation() -> None:
    document = build_well_known(
        {"supported_primary_keys": ["all"]},
        routes=[],
        request_root="https://id.example.com",
    )
    assert document["supportedPrimaryKeys"] == ["all"]


# --------------------------------------------------------------------------
# Builder behaviour
# --------------------------------------------------------------------------


def test_configured_root_wins_over_request_origin() -> None:
    document = build_well_known(
        {"resolver_root": "https://id.example.com"},
        routes=[],
        request_root="http://internal:8080/",
    )
    assert document["resolverRoot"] == "https://id.example.com"


def test_trailing_slash_is_stripped_from_root() -> None:
    document = build_well_known(None, routes=[], request_root="https://id.example.com/")
    assert document["resolverRoot"] == "https://id.example.com"


def test_empty_config_still_yields_a_valid_document() -> None:
    document = build_well_known(None, routes=[], request_root="https://id.example.com")
    assert set(document) == {"resolverRoot", "supportedPrimaryKeys"}
    assert document["supportedPrimaryKeys"] == ["01"]


def test_optional_fields_map_to_standard_property_names() -> None:
    document = build_well_known(
        {
            "terms_of_use": "https://example.com/terms",
            "json_ld_context_location": "https://example.com/context.jsonld",
            "link_type_default_can_be_linkset": True,
            "extension_profile": "https://example.com/extensions",
        },
        routes=[],
        request_root="https://id.example.com",
    )
    assert document["termsOfUse"] == "https://example.com/terms"
    assert document["jsonLdContextLocation"] == "https://example.com/context.jsonld"
    assert document["linkTypeDefaultCanBeLinkset"] is True
    assert document["extensionProfile"] == "https://example.com/extensions"


def test_unset_optional_fields_are_omitted_not_null() -> None:
    document = build_well_known({"name": "R"}, routes=[], request_root="https://id.example.com")
    assert "termsOfUse" not in document
    assert "contact" not in document


def test_missing_root_is_an_error() -> None:
    with pytest.raises(WellKnownConfigError, match="resolverRoot is mandatory"):
        build_well_known(None, routes=[], request_root=None)


# --------------------------------------------------------------------------
# Config validation — fail fast at startup
# --------------------------------------------------------------------------


def test_absent_block_is_valid() -> None:
    assert validate_well_known_config(None) == {}


def test_block_must_be_a_mapping() -> None:
    with pytest.raises(WellKnownConfigError, match="must be a mapping"):
        validate_well_known_config(["name"])


def test_unknown_key_is_rejected() -> None:
    with pytest.raises(WellKnownConfigError, match="unknown 'well_known' key"):
        validate_well_known_config({"resolverRoot": "https://id.example.com"})


def test_invalid_primary_key_is_rejected() -> None:
    with pytest.raises(WellKnownConfigError, match="not a GS1 primary key"):
        validate_well_known_config({"supported_primary_keys": ["01", "99"]})


def test_empty_primary_key_list_is_rejected() -> None:
    with pytest.raises(WellKnownConfigError, match="non-empty list"):
        validate_well_known_config({"supported_primary_keys": []})


def test_wrong_type_for_optional_field_is_rejected() -> None:
    with pytest.raises(WellKnownConfigError, match="contact"):
        validate_well_known_config({"contact": "Example Brand B.V."})


def test_dockerfile_label_matches_package_version() -> None:
    """The image label is the one version pin outside Python — keep it honest.

    1.0.0 shipped with app/pyproject/package versions out of step and needed a
    follow-up fix commit; this is the guard against a repeat.
    """
    from resolver import __version__

    dockerfile = (Path(__file__).parent.parent / "Dockerfile").read_text()
    assert f'LABEL org.opencontainers.image.version="{__version__}"' in dockerfile


def test_pyproject_takes_its_version_from_the_package() -> None:
    """`resolver.__version__` must stay the single source of the version.

    Asserted as a declaration rather than by comparing installed metadata,
    which goes stale in an editable install between a bump and a reinstall.
    A contributed PR once replaced this block with a hardcoded `version`,
    which silently pinned the distribution a minor behind the package.
    """
    import tomllib

    pyproject = tomllib.loads(
        (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert "version" in pyproject["project"].get(
        "dynamic", []
    ), "[project] must declare version as dynamic, not hardcode it"
    assert "version" not in pyproject["project"]
    assert pyproject["tool"]["setuptools"]["dynamic"]["version"] == {"attr": "resolver.__version__"}


def test_bad_block_fails_the_service_at_startup(tmp_path: Path) -> None:
    """A non-conformant description file must not reach a running resolver."""
    with pytest.raises(ConfigError, match="not a GS1 primary key"):
        _router_for(
            tmp_path,
            {
                "well_known": {"supported_primary_keys": ["nonsense"]},
                "resolvers": [{"match": "*", "target": "https://e.example/{gtin}"}],
            },
        )
