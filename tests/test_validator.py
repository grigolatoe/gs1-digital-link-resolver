"""Tests for the pluggable DPP validator interface."""

from __future__ import annotations

import textwrap

import pytest

from resolver.linkset import build_linkset
from resolver.parser import parse
from resolver.router import LinkType, Router
from resolver.validator import (
    HttpValidator,
    NoOpValidator,
    SmokeValidator,
    ValidationResult,
    Validator,
    load_validator,
)


class TestProtocol:
    def test_noop_satisfies_protocol(self):
        assert isinstance(NoOpValidator(), Validator)

    def test_smoke_satisfies_protocol(self):
        assert isinstance(SmokeValidator(), Validator)

    def test_http_satisfies_protocol(self):
        assert isinstance(HttpValidator(endpoint="https://v.test/validate"), Validator)


class TestNoOp:
    def test_noop_passes_everything(self):
        v = NoOpValidator()
        result = v.validate(parse("/01/09780345418913/21/SER01"), "https://x.test/p")
        assert result.ok
        assert result.profile == ""
        assert result.errors == []
        assert result.warnings == []


class TestSmoke:
    def test_smoke_passes_clean_uri(self):
        v = SmokeValidator()
        result = v.validate(parse("/01/09780345418913/21/SER01"), "https://x.test")
        assert result.ok
        assert result.warnings == []

    def test_smoke_warns_on_unusual_serial(self):
        v = SmokeValidator()
        # contains '!' which is outside the recommended GS1 charset
        result = v.validate(parse("/01/09780345418913/21/HEY!"), "https://x.test")
        assert result.ok  # warnings don't make it not-ok
        assert any("Serial" in w for w in result.warnings)

    def test_smoke_warns_on_long_lot(self):
        v = SmokeValidator()
        long_lot = "A" * 25  # exceeds the 20-char recommended cap
        result = v.validate(parse(f"/01/09780345418913/10/{long_lot}"), "https://x.test")
        assert any("Batch" in w for w in result.warnings)

    def test_smoke_warns_on_unknown_ais(self):
        v = SmokeValidator()
        result = v.validate(parse("/01/09780345418913/9999/X"), "https://x.test")
        assert any("9999" in w for w in result.warnings)


class TestHttp:
    """HttpValidator delegates to an external endpoint and is advisory-only."""

    PARSED = staticmethod(lambda: parse("/01/09780345418913/21/SER01"))

    def test_maps_passing_verdict(self, monkeypatch):
        import httpx

        def fake_post(url, json, timeout):
            assert json["primary"] == {"ai": "01", "value": "09780345418913"}
            assert json["target_url"] == "https://dpp.test/p"
            return httpx.Response(
                200,
                json={"ok": True, "profile": "cirpass2-textile-2026"},
                request=httpx.Request("POST", url),
            )

        monkeypatch.setattr(httpx, "post", fake_post)
        v = HttpValidator(endpoint="https://v.test/validate")
        result = v.validate(self.PARSED(), "https://dpp.test/p")
        assert result.ok is True
        assert result.profile == "cirpass2-textile-2026"
        assert result.errors == []

    def test_maps_failing_verdict(self, monkeypatch):
        import httpx

        def fake_post(url, json, timeout):
            return httpx.Response(
                200,
                json={"ok": False, "errors": ["missing fibreComposition"], "warnings": ["w1"]},
                request=httpx.Request("POST", url),
            )

        monkeypatch.setattr(httpx, "post", fake_post)
        v = HttpValidator(endpoint="https://v.test/validate")
        result = v.validate(self.PARSED(), "https://dpp.test/p")
        assert result.ok is False
        assert result.errors == ["missing fibreComposition"]
        assert result.warnings == ["w1"]
        # falls back to the configured profile when the endpoint omits one
        assert result.profile == "cirpass2-http"

    def test_unreachable_endpoint_is_advisory(self, monkeypatch):
        import httpx

        def fake_post(url, json, timeout):
            raise httpx.ConnectError("no route to host")

        monkeypatch.setattr(httpx, "post", fake_post)
        v = HttpValidator(endpoint="https://v.test/validate")
        result = v.validate(self.PARSED(), "https://dpp.test/p")
        assert result.ok is True  # never blocks resolution
        assert any("unavailable" in w for w in result.warnings)

    def test_non_2xx_is_advisory(self, monkeypatch):
        import httpx

        def fake_post(url, json, timeout):
            return httpx.Response(503, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", fake_post)
        v = HttpValidator(endpoint="https://v.test/validate")
        result = v.validate(self.PARSED(), "https://dpp.test/p")
        assert result.ok is True
        assert any("unavailable" in w for w in result.warnings)

    def test_unparseable_body_is_advisory(self, monkeypatch):
        import httpx

        def fake_post(url, json, timeout):
            return httpx.Response(200, content=b"not json", request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", fake_post)
        v = HttpValidator(endpoint="https://v.test/validate")
        result = v.validate(self.PARSED(), "https://dpp.test/p")
        assert result.ok is True
        assert any("unavailable" in w for w in result.warnings)


class TestLoader:
    def test_no_config_returns_noop(self):
        assert isinstance(load_validator(None), NoOpValidator)
        assert isinstance(load_validator({}), NoOpValidator)

    def test_smoke_config(self):
        v = load_validator({"type": "smoke", "profile": "custom-smoke"})
        assert isinstance(v, SmokeValidator)
        assert v.profile == "custom-smoke"

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown validator type"):
            load_validator({"type": "magicvalidator"})

    def test_schema_without_path_raises(self):
        with pytest.raises(ValueError, match="schema_path"):
            load_validator({"type": "schema"})

    def test_http_config(self):
        v = load_validator(
            {"type": "http", "endpoint": "https://v.test/validate", "timeout": 2.5}
        )
        assert isinstance(v, HttpValidator)
        assert v.endpoint == "https://v.test/validate"
        assert v.timeout == 2.5

    def test_http_without_endpoint_raises(self):
        with pytest.raises(ValueError, match="endpoint"):
            load_validator({"type": "http"})


class TestRouterIntegration:
    def test_default_router_has_noop_validator(self):
        r = Router()
        assert isinstance(r.validator, NoOpValidator)

    def test_router_loads_smoke_from_yaml(self, tmp_path):
        cfg = tmp_path / "routes.yaml"
        cfg.write_text(
            textwrap.dedent("""
            validator:
              type: smoke
              profile: integration-smoke
            resolvers:
              - match: "*"
                target: "https://x.test/{gtin}"
        """)
        )
        router = Router(cfg)
        assert isinstance(router.validator, SmokeValidator)
        assert router.validator.profile == "integration-smoke"


class TestLinkSetIntegration:
    def test_validation_appears_as_sidecar(self):
        ls = build_linkset(
            anchor="https://x.test/01/0",
            links=[LinkType(rel="gs1:pip", href="https://dpp.test/p")],
            validation={"ok": True, "profile": "smoke-builtin-v1", "errors": [], "warnings": []},
        )
        entry = ls["linkset"][0]
        assert "gs1:validationStatus" in entry
        assert entry["gs1:validationStatus"]["profile"] == "smoke-builtin-v1"

    def test_no_validation_no_sidecar(self):
        ls = build_linkset(
            anchor="https://x.test/01/0",
            links=[LinkType(rel="gs1:pip", href="https://dpp.test/p")],
            validation=None,
        )
        assert "gs1:validationStatus" not in ls["linkset"][0]


def test_validation_result_as_dict_round_trips():
    result = ValidationResult(
        ok=False,
        profile="cirpass2-textile-2026",
        errors=["missing fibreComposition"],
        warnings=["recyclability score not declared"],
    )
    d = result.as_dict()
    assert d == {
        "ok": False,
        "profile": "cirpass2-textile-2026",
        "errors": ["missing fibreComposition"],
        "warnings": ["recyclability score not declared"],
    }
