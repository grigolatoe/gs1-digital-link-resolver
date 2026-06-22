# Stability & versioning

This resolver follows [Semantic Versioning](https://semver.org/). From **1.0.0**
onward, the two contracts below are stable: a breaking change to either requires
a **major** version bump. This page is the reference for what adopters can rely
on.

> **Pre-1.0 note.** Until 1.0.0 these contracts are settled in practice but not
> yet under the SemVer guarantee — minor 0.x releases may still adjust them. The
> `0.3.x` shape described here is what 1.0 will ratify.

## The two stable contracts

### 1. Configuration schema (`routes.yaml`)

Versioned via the top-level `version:` field (integer; optional, defaults to the
resolver's current schema major — **1**). The resolver refuses to start if
`version` names a major it does not support.

Stable surface:

| Key | Type | Notes |
|---|---|---|
| `version` | int | Config schema major. |
| `resolvers` | list (non-empty) | Matched top-to-bottom, first match wins. |
| `resolvers[].target` | string (required) | Template; `{...}` placeholders filled from the parsed URI. |
| `resolvers[].match` | `"*"` or mapping | Clauses: `primary_ai`, `gtin_prefix`, `gtin_regex`, `has_qualifier`, `serial_in`. Omitted / `"*"` / `{}` = fallback. |
| `resolvers[].link_types[]` | list of mappings | Each needs `rel` + `href`; optional `type`, `title`, `hreflang`. |
| `validator` | mapping | `type: noop\|smoke\|schema\|http` (+ type-specific keys). |

**Covered by SemVer:** existing keys keep their meaning; a malformed config
fails fast at startup with a `ConfigError`. New **optional** keys and new match
clauses / validator types may be added in **minor** releases. Removing or
renaming a key, or changing match precedence, is a **major** change.

### 2. HTTP contract

| Endpoint | Behaviour |
|---|---|
| `GET /{gs1-dl-path}` | Parse + resolve. Content negotiation below. |
| `GET /healthz` | `200 {"status":"ok"}`. |
| `GET /metrics` | Prometheus text exposition (`text/plain; version=0.0.4`). |

Content negotiation on the resolve endpoint (stable):

| `Accept` | Response |
|---|---|
| `application/linkset+json` (or `*/*`, empty, unknown) | `200` RFC 9264 link-set |
| `application/ld+json` | `200` JSON-LD link-set |
| `application/json` | `200` link-set (RFC 9264 shape) |
| `text/html` | `302` to the default link's href |

Status codes: `200` resolved · `302` HTML redirect · `400` malformed URI / bad
GTIN-14 check digit / over-length input · `404` no matching route.

Stable response details: RFC 9264 link-set shape, GS1 Web Vocabulary relation
IRIs, the `?linkType=` filter (GS1 DL §6.4), and the advisory
`gs1:validationStatus` sidecar (present only when a non-`noop` validator is
configured).

**Covered by SemVer:** the paths, status codes, negotiation matrix, and
documented response fields above. Adding a new optional response field, a new
media type, or a new metric series is a **minor** change. Removing/renaming a
field, changing a status code, or altering negotiation precedence is a **major**
change.

## Explicitly *not* part of the contract

These may change at any time without a major bump:

- Exact wording of error `message` strings.
- Log line format/content (until structured logging lands; see
  [ROADMAP.md](../ROADMAP.md)).
- Internal module layout, function signatures, and private helpers in
  `resolver/` (this is a service, not a published library API).
- The bundled **illustrative** profile (`profiles/illustrative-dpp.schema.json`)
  — non-normative; see [profiles/README.md](../profiles/README.md).
- `MAX_URI_LENGTH` and other resource bounds (safety limits, may be tuned).
