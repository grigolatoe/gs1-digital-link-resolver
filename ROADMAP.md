# Roadmap

Forward-looking plan. **1.0.0 has shipped** — every blocker below is done and
the contracts are frozen under SemVer. What remains is post-1.0 polish and
deferred work. For shipped detail see [CHANGELOG.md](CHANGELOG.md).

## Where we are (1.0.0 "Hallmark")

The resolver is **functionally complete** for GS1 Digital Link v1.2 routing:
parser + full AI table, declarative YAML routing, RFC 9264 link-sets, content
negotiation, four DPP validators (noop/smoke/schema/http), `/healthz`,
Prometheus `/metrics`, signed Docker releases, and a deployment guide. The four
NGI Zero Commons Fund milestones (parser, core resolver, validator wire-up,
deployment docs) are delivered.

## What 1.0 *means* here

1.0 is primarily a **stability commitment**, not new features. Adopters — the
CIRPASS-2 Community of Practice and other DPP platforms — need to trust that
upgrading within 1.x won't break their deployment. So the bar for 1.0 is: the
two public contracts are frozen and documented under SemVer, and the service is
hardened for untrusted public traffic.

## 1.0 blockers (Must)

> **Status: shipped in 1.0.0.** Every 1.0 blocker below is done and the
> contracts are frozen under SemVer. Retained here as the record of what 1.0
> ratified.

- [x] **Freeze & document the public contracts** (the core of 1.0) — *done*
  - **Config schema** — versioned via an optional `version:` field
    (`CONFIG_SCHEMA_VERSION = 1`); unsupported majors fail fast at startup.
  - **HTTP contract** — paths, content-negotiation matrix, status codes,
    `gs1:validationStatus`, `/healthz`, `/metrics` documented.
  - SemVer policy published in [docs/stability.md](docs/stability.md): post-1.0
    a breaking change to either contract is a major bump.
- [x] **Fail-fast config validation at startup.** `Router` now validates the
  `routes.yaml` shape and raises `ConfigError` with an actionable message; the
  service refuses to start on a broken config. *(done — `_validate_config`)*
- [x] **Bound untrusted input (DoS guard).** The parser rejects URIs longer than
  `MAX_URI_LENGTH` (2048) with a 400 before parsing. *(done)*
- [x] **Compression decision (GS1 DL §7).** Decided: **scoped out of 1.0** and
  documented as a non-goal (see [ARCHITECTURE.md](docs/ARCHITECTURE.md#non-goals))
  — the compression scheme is substantial and uncompressed URIs are the common
  case for ESPR DPP carriers. May be revisited in 1.x.

## 1.0 polish (Should)

- [x] **`SECURITY.md`** — vulnerability disclosure policy at the repo root
  (supported versions, private reporting, PGP-encrypted option, scope). *(done)*
- [x] **Structured logging + request IDs** — JSON access logs (request_id,
  method, path, status, duration_ms) + `X-Request-ID` propagation, `LOG_LEVEL`
  configurable. *(done)*
- [ ] **CIRPASS-2 CoP release announcement** (NGI M4 deliverable) — external,
  maintainer-posted.

## Deferred to 1.x (explicitly NOT 1.0 blockers)

- **Bundled normative DPP profile** — blocked on a stable, openly-licensed
  standard. Tracking UNTP (UNECE) toward a post-review stable release (v0.7.0
  public review closes 2026-07-13); its current source licence (GPL-3.0) also
  precludes vendoring into this Apache-2.0 project. The `schema`/`http`
  validators already work with any operator-supplied schema, so this does not
  gate 1.0.
- **Compressed DL URI support** — if scoped out of 1.0 above.
- **Native tracing (OpenTelemetry)** — `/metrics` covers the 1.0 observability bar.

## Non-goals (by design, not roadmap items)

- **Authentication / authorization** — resolvers are public routing
  infrastructure; access control belongs at the DPP endpoint.
- **Hosting the DPP data itself** — this routes to DPP endpoints; it does not
  store passports.
- **Supply-chain / raw-material traceability** — out of scope; this is a routing
  layer over finished-product GS1 DL URIs.
