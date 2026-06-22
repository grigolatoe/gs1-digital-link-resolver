# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] — "Hallmark" — 2026-06-22

First **stable** release. From this version the **configuration schema** and the
**HTTP contract** are stable under Semantic Versioning — see
[docs/stability.md](docs/stability.md). This is the first published release since
0.2.0; the `0.2.1` and `0.3.0` tags were development waypoints (never published
as images) and are consolidated here. Delivers NGI Zero Commons Fund Milestones 3
(DPP validator wire-up) and 4 (deployment docs). Test suite 95 → 129.

### Added

- **Four DPP validators, fully implemented** — `noop`, `smoke`, `schema`
  (fetches the target DPP via `httpx` and validates it against a JSON Schema with
  `jsonschema`, surfacing *every* violation), and `http` (delegates to an
  external validator `endpoint`). All advisory: any fetch/transport/parse failure
  or missing optional dependency degrades to a soft warning and never blocks
  resolution. Behind the `validators` optional extra
  (`pip install '.[validators]'`) so the core package stays slim.
- **Illustrative DPP profile** (`profiles/illustrative-dpp.schema.json`, shipped
  in the image) — minimal, **non-normative**, so the `schema` validator runs out
  of the box. No canonical machine-readable CIRPASS-2 profile exists to bundle
  (CIRPASS-2 ships data models, not schemas; the closest standard, UNTP, is
  pre-stable and copyleft-licensed), so operators bring their own / point at UNTP.
- **Prometheus `/metrics` endpoint** — dependency-free text exposition:
  `gs1_resolver_requests_total{outcome}`, `gs1_resolver_validations_total{ok}`, a
  resolve-latency summary, and `gs1_resolver_build_info{version}`.
- **Structured JSON logging + request IDs** — one JSON access line per request
  (`request_id`, `method`, `path`, `status`, `duration_ms`); `X-Request-ID`
  generated/propagated; verbosity via `LOG_LEVEL`.
- **Versioned config schema** — optional `version:` field
  (`CONFIG_SCHEMA_VERSION = 1`); unsupported majors fail fast at startup.
- **Fail-fast config validation** — `Router` validates `routes.yaml` shape at
  load time and raises `ConfigError` with an actionable message; the service
  refuses to start on a malformed config.
- **Input bound (DoS guard)** — URIs longer than `MAX_URI_LENGTH` (2048) are
  rejected with a 400 before parsing.
- **Operator documentation** — deployment & operator guide
  ([docs/deployment.md](docs/deployment.md)), stability/SemVer contract
  ([docs/stability.md](docs/stability.md)), `ROADMAP.md`, and `SECURITY.md`
  (vulnerability disclosure policy).
- **Expanded HTTP integration tests** against the shipped example config
  (content negotiation, `?linkType=` filtering, GTIN boundary, validator sidecar,
  metrics, request-id propagation).

### Fixed

- **Canonical URI pads a GTIN primary key to GTIN-14** (GS1 DL §4.6) — a GTIN-13
  input previously produced a 13-digit canonical URI; it is now left-padded.

### Changed

- Docs corrected: no canonical "CIRPASS-2 textile/battery" profile ships
  (CIRPASS-2 publishes data models, not schemas, and does not cover batteries);
  the validator docs reflect the four implemented types and bring-your-own/UNTP.

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
