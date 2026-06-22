# Roadmap to 1.0

Forward-looking plan. For shipped work see [CHANGELOG.md](CHANGELOG.md) and the
milestone table in the [README](README.md#project-status).

## Where we are (post-0.3.0 "Hallmark")

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

- [ ] **Freeze & document the public contracts** (the core of 1.0)
  - **Config schema** — `routes.yaml` structure (match clauses, `link_types`,
    `validator` block). Add an optional `version:` field so future schema
    changes are detectable/migratable (none today).
  - **HTTP contract** — path handling, content-negotiation matrix, response
    shapes, status codes, the `gs1:validationStatus` sidecar, `/healthz`,
    `/metrics`.
  - Publish a SemVer policy: post-1.0, a breaking change to either contract is a
    major bump.
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

- [ ] **`SECURITY.md`** — vulnerability disclosure policy (GitHub-standard;
  expected for EU-funded public infrastructure). CONTRIBUTING references a
  security channel; promote it to a top-level policy.
- [ ] **Structured logging + request IDs** — for operability at scale.
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
