# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] — 2026-06-22

### Added

- **Container image published** to `ghcr.io/grigolatoe/gs1-digital-link-resolver`
  at tags `0.2.0` and `latest`, both pointing at the v0.2.0 source. OCI image
  labels (`org.opencontainers.image.source`, `description`, `licenses`,
  `version`) link the package back to this repository on the GitHub UI.
- **PGP-signed release manifest** — `SIGNING.md` documents the verification
  procedure; `SIGNATURES-v0.2.0.txt` + `SIGNATURES-v0.2.0.txt.asc` are
  attached to the v0.2.0 GitHub Release. The signing key is
  `47DE71F021C986123851E8AD65A8E29C92A63D38` (Ed25519), the same key
  attached to the NGI Zero Commons Fund application.
- **HTTP integration tests** (`tests/test_app_integration.py`) — nine
  end-to-end tests exercising the FastAPI app against the shipped example
  config: content-negotiation matrix (`application/linkset+json`,
  `application/ld+json`, HTML 302), `?linkType=` filtering, GTIN mod-10
  boundary, wildcard fallback to `id.gs1.org`, malformed-path refusal, and
  `gs1:validationStatus` sidecar surfacing. Total: 95/95 tests pass.

### Fixed

- **Canonical URI now pads a GTIN primary key to GTIN-14** (GS1 DL §4.6).
  `canonicalise()` previously emitted the GTIN exactly as supplied, so a
  GTIN-13 input produced a 13-digit canonical URI. It now left-pads via the
  existing `pad_gtin_to_14()` helper (idempotent on 14-digit GTINs; non-GTIN
  primaries such as GRAI are unaffected). Two conformance vectors added.
  Total: 97/97 tests pass.

## [0.2.0] — "Gift" — 2026-05-18

Substantial expansion from the initial scaffold: full GS1 Digital Link v1.2
compliance, RFC 9264 link-set responses, pluggable DPP validator interface,
and the open-source infrastructure (CI, contributor onboarding, architecture
documentation) needed for community use.

### Added

- **Parser** — full DL-compatible GS1 Application Identifier table in
  `resolver/ai_table.py`: name, fixed/variable length, category
  (primary / qualifier / attribute), and per-primary qualifier ordering for
  canonical URI generation. Primary keys: GTIN (`01`), GRAI (`8003`), GIAI
  (`8004`), ITIP (`8006`), CPID (`8010`), GMN (`8013`), GSRN-Provider (`8017`),
  GSRN-Recipient (`8018`), GLN (`414`, `417`).
- **Parser** — alpha-coded URI form (`/gtin/.../ser/...`) is normalised to
  numeric AI form at the AI position only, so a serial of value `SER` or a
  lot of value `LOT` is no longer misread as an alpha-coded AI.
- **Parser** — GTIN-14 GS1 Modulo-10 check-digit validation, GTIN-8/12/13
  left-pad helper, canonical URI generation per GS1 DL §4.6.
- **Link-set builder** — RFC 9264 `application/linkset+json` responses with
  GS1 Web Vocabulary relation IRIs (`https://gs1.org/voc/...`), short-form
  expansion (`gs1:pip` → full IRI), JSON-LD wrapper for `application/ld+json`
  consumers, automatic default-link promotion when none is declared, and
  GS1 DL §6.4 `?linkType=` filter handling.
- **Router** — declarative YAML route configuration with match clauses
  `primary_ai`, `gtin_prefix`, `gtin_regex`, `has_qualifier`, `serial_in`,
  and `*`/fallback. Template substitution with longest-key-first replacement
  to disambiguate `{serial}` from `{ser}`.
- **Content negotiation** — full Accept-header parsing with q-values
  (RFC 7231 §5.3.2); four media types offered (`application/linkset+json`
  default, `application/ld+json`, `application/json`, `text/html` 302).
- **Validator** — pluggable `Validator` protocol with three in-tree
  implementations: `NoOpValidator` (default, zero overhead), `SmokeValidator`
  (URI-shape sanity checks), `SchemaValidator` (JSON-Schema against a
  CIRPASS-2 profile). Configured via the `validator:` YAML block. Failures
  are advisory only — never block resolution. Surfaced in the link-set as
  a `gs1:validationStatus` sidecar.
- **Conformance test suite** — 86 tests covering GS1 DL §4.4–§4.6, RFC 9264
  link-set shape, content negotiation q-value ordering, validator protocol
  contract, and routing match clauses. Runs in under 0.1 s.
- **CI** — GitHub Actions workflow (`.github/workflows/ci.yml`) running on
  push to main and on pull requests: `pytest` matrix against Python 3.11
  and 3.12, `ruff check`, `ruff format --check`, and a Docker build that
  starts the container and polls `/healthz` as a smoke test.
- **Ruff** — baseline format + import-sort across `resolver/` and `tests/`;
  `[tool.ruff]` config in `pyproject.toml` (line-length 100, target py311,
  rules E/F/I/B/UP/W).
- **Architecture documentation** — `docs/ARCHITECTURE.md` covers the
  five-layer design (parser, router, link-set builder, content negotiation,
  validator) with standards citations per layer (GS1 DL v1.2 §4.4/§4.6/§6.4,
  GS1 General Specifications, GS1 Web Vocabulary, RFC 9264, RFC 8288,
  RFC 7231 §5.3.2, ISO/IEC 15459, JSON-LD 1.1), an extension-points table,
  and an explicit non-goals section.
- **Contributor onboarding** — `CONTRIBUTING.md` (dev setup, PR checklist,
  AI-table extension guide, validator extension guide, security-report
  channel, scope guardrails), `CODE_OF_CONDUCT.md` (Contributor Covenant
  2.1 by reference), GitHub issue templates (bug report, feature request)
  with standards-citation prompts, an issue-template config disabling blank
  issues, and a pull-request template requiring summary / type / standards
  reference / test plan.

### Fixed

- `pyproject.toml` `build-backend` corrected from `setuptools.backends.legacy:build`
  (non-existent module) to `setuptools.build_meta`. Explicit
  `[tool.setuptools.packages.find]` added so flat-layout autodiscovery picks
  `resolver/` and excludes `config/`, `tests/`, `docs/`. Allows
  `pip install -e ".[dev]"` to succeed in CI.

### Changed

- FastAPI app version bumped to `0.2.0` (was previously written in code
  ahead of the package version; this release aligns them).

## [0.1.0] — 2026-04-21

Initial scaffold.

### Added

- GS1 Digital Link URI parser (numeric AI form, basic AI coverage), routing
  engine over YAML, FastAPI HTTP service, Dockerfile, Apache 2.0 licence,
  `README.md` with project context and quick-start, `.gitignore`.

[Unreleased]: https://github.com/grigolatoe/gs1-digital-link-resolver/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/grigolatoe/gs1-digital-link-resolver/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/grigolatoe/gs1-digital-link-resolver/releases/tag/v0.1.0
