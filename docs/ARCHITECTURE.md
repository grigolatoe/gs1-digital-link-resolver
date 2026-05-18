# Architecture

This document describes the internal design of the GS1 Digital Link Resolver
and the standards reasoning behind each component. It is the design-rationale
companion to the `README.md`: where the README tells operators *how to run*
the resolver, this document explains *why it is built the way it is*.

## High-level layering

The resolver is five thin layers stacked top-to-bottom:

```
   ┌─────────────────────────────────────────┐
   │  HTTP service (FastAPI, ASGI)           │  resolver/app.py
   ├─────────────────────────────────────────┤
   │  Content negotiation (Accept, q-values) │  resolver/negotiate.py
   ├─────────────────────────────────────────┤
   │  Link-set builder (RFC 9264 + GS1 voc)  │  resolver/linkset.py
   ├─────────────────────────────────────────┤
   │  Router (declarative YAML, validators)  │  resolver/router.py + validator.py
   ├─────────────────────────────────────────┤
   │  Parser (DL URI → typed identifier set) │  resolver/parser.py + ai_table.py
   └─────────────────────────────────────────┘
```

Each layer has a single responsibility, a single data type at its boundary,
and a small, easily-mocked interface. The HTTP service does not know about
GS1 application identifiers. The parser does not know about link sets. The
router does not know about Accept headers. This is deliberate — it lets
operators plug the parser into non-HTTP contexts (offline batch validation,
CLI tooling, scanner middleware) without dragging in FastAPI, and conversely
lets them keep the HTTP shell when swapping in a custom router or validator.

## Layer 1 — Parser

Source: `resolver/parser.py`, `resolver/ai_table.py`.

The parser converts a GS1 Digital Link URI into a `GS1ParseResult` dataclass:
the primary key (typically AI `01`, GTIN), qualifier AIs, attribute AIs,
query parameters, the `?linkType=` selector, and a list of unrecognised AIs
that were present in the path.

### Two URI shapes

Per GS1 DL v1.2 §4.4, a Digital Link URI may be written in two equivalent
forms:

- **Numeric AI form:** `/01/09780345418913/22/V2/10/BATCH/21/SER`
- **Alpha-coded form:** `/gtin/09780345418913/cpv/V2/lot/BATCH/ser/SER`

The parser normalises alpha-coded segments to numeric AI form *only at the
AI position* (every odd-numbered token from the path root). Values at the
value position are left verbatim. This avoids the easy bug where a serial
number that happens to spell `SER` or a lot of value `LOT` gets
misinterpreted as an alpha-coded AI.

### AI table (DL-compatible subset)

GS1 defines roughly 170 application identifiers in the General Specifications.
Only a subset is permitted in a Digital Link URI (DL-compatible AIs); the rest
are barcode-only or document-only. `resolver/ai_table.py` ships the full
DL-compatible AI table — name, fixed/variable length, category (primary key
/ qualifier / attribute), and the per-primary qualifier ordering required for
canonical URI generation.

The primary keys recognised today are:

| AI   | Identifier                            |
|------|---------------------------------------|
| `01` | GTIN (Global Trade Item Number)       |
| `8003` | GRAI (Global Returnable Asset)      |
| `8004` | GIAI (Global Individual Asset)      |
| `8006` | ITIP (Component / Part)             |
| `8010` | CPID (Component / Part)             |
| `8013` | GMN (Global Model Number)           |
| `8017` | GSRN (Service Relation, Provider)   |
| `8018` | GSRN (Service Relation, Recipient)  |
| `414`  | GLN (Physical Location)             |
| `417`  | GLN (Party)                         |

### GTIN-14 mod-10 check

Every GTIN in a Digital Link URI MUST be GTIN-14 (per DL v1.2 §3.3). Shorter
GTINs (GTIN-8, GTIN-12, GTIN-13) are left-padded with zeros. `pad_gtin_to_14()`
performs the padding; `validate_gtin14()` runs the GS1 Modulo-10 check digit
algorithm. The HTTP layer rejects a path whose primary key is `01` with a
failing check digit *before* invoking the router — this is the cheapest place
to reject corrupted scans.

### Canonical URI generation

`canonicalise(parsed)` produces the GS1 DL §4.6 canonical form: `https://id.gs1.org`
host, primary key first, qualifiers in the per-primary-key order defined by
the standard, attributes in numeric-AI order, query string dropped. This is
used by integration tests, by external callers who want to deduplicate URIs,
and (in milestone 3) by the SchemaValidator when constructing a cache key.

### What the parser deliberately does *not* do

- **Routing.** Routing is the router's job.
- **HTTP.** The parser accepts a `str`, not a `Request`.
- **Side effects.** The parser is pure — no I/O, no logging, no module-level
  state. Tests run in 0.08 s for that reason.
- **Strict AI enforcement.** Unknown AIs are flagged in `unknown_ais` but not
  rejected. The router or validator decides whether to refuse the request.

## Layer 2 — Router

Source: `resolver/router.py`.

The router takes a `GS1ParseResult` and a YAML config, walks the routes
top-to-bottom, and returns `(target_url, link_types)` for the first match.

### Match clauses

Each route declares a `match` block; all declared clauses must match for the
route to fire. Available clauses:

| Clause           | Matches when…                                                      |
|------------------|--------------------------------------------------------------------|
| `primary_ai`     | the parsed primary AI equals the given AI (e.g. `01`)              |
| `gtin_prefix`    | the primary value starts with the given prefix                     |
| `gtin_regex`     | the primary value full-matches the given regex                     |
| `has_qualifier`  | the given qualifier AI is present (e.g. `21` for serial)           |
| `serial_in`      | the serial number (AI `21`) is one of the given literals           |
| `*` or `{}`      | always matches — use for the default fallback                      |

A typical config has a series of brand- or prefix-specific routes followed by
a single `match: "*"` default that points to `id.gs1.org` so unknown
identifiers degrade to GS1's own resolver rather than 404.

### Template substitution

`target` and every `link_types[].href` / `title` may contain `{key}` placeholders.
Placeholders are filled from a flat name/value mapping built from the parse
result — numeric AI (`{01}`), alpha name (`{gtin}`), and convenience aliases
(`{serial}`, `{batch}`, `{expiry}`). Sorting keys longest-first ensures
`{serial}` is replaced before `{ser}`, etc.

### Why YAML, not a database

The router is intentionally configuration-driven and stateless. Operators
deploy the resolver as a Docker image with a single mounted YAML file. A new
brand or a new route is a YAML edit and a process restart — no migrations,
no admin UI, no state to back up.

For installations that need dynamic routing (e.g. a registry where brands
self-register and routes are computed at request time), the `Router` class
can be swapped out for an HTTP-backed or DB-backed implementation that
exposes the same `resolve(parsed) -> (target, links)` interface. This is an
extension path, not the current scope.

## Layer 3 — Link-set builder

Source: `resolver/linkset.py`.

For each resolved URI the resolver returns a *link set*: one anchor URL and
a list of relation → target links. The on-the-wire format is **RFC 9264**
(`application/linkset+json`); the same data is also published as JSON-LD
(`application/ld+json`) with a `gs1:` context binding so semantic-web tooling
can resolve relations into the GS1 Web Vocabulary IRIs.

### Relation IRIs

Operators declare relations in short form (`gs1:pip`,
`gs1:verificationService`, `gs1:digitalProductPassport`). The link-set
builder expands these to the full GS1 Web Vocabulary IRI
(`https://gs1.org/voc/pip`, etc.) before serialising. Plain IETF RFC 8288
relation names (`alternate`, `canonical`) pass through unchanged; full
http(s) IRIs in `rel:` are honoured verbatim.

This split lets configs stay short and human-readable while the response
remains fully conformant to GS1's conformance document — short-form IRIs
in the response would break consumers that match on the full IRI.

### Default link promotion

Every link-set must carry a `gs1:defaultLink` — that is what the HTTP layer
follows when the client asks for `text/html`. If the operator has not
explicitly declared one, the first declared link is promoted to default.
This means a minimal route config (one `target`, no `link_types`) still
returns a usable HTML redirect.

### `?linkType=` filter

Per GS1 DL §6.4, a client may ask for a specific relation by appending
`?linkType=gs1:pip` (or the full IRI). The builder filters the link-set
to that single relation if a match exists, and falls back to the full
link-set if no match is found — which is the conformance-document-prescribed
behaviour for "unknown link type requested".

### Validation sidecar

If a validator is wired up (see Layer 5), the validation result is attached
to the link-set as a `gs1:validationStatus` sidecar field. Consumers that
do not know about it ignore it. This is deliberately non-blocking — a soft
DPP validation failure must never break resolution, because that would turn
the resolver into a denial-of-service vector against badly-published DPPs.

## Layer 4 — Content negotiation

Source: `resolver/negotiate.py`.

The resolver advertises four media types, in this preference order:

1. `application/linkset+json` — RFC 9264, the modern default
2. `application/ld+json` — JSON-LD wrapper for semantic-web consumers
3. `application/json` — RFC 9264 shape under a plain JSON media type
4. `text/html` — 302 redirect to the default link's `href`

The Accept header is parsed with q-values; ties are broken by client order
first, then by the server's preference list above. An empty or wildcard
Accept (`*/*`) returns `application/linkset+json` — the GS1 DL conformance
document's recommended default for resolver responses.

### Why HTML is a redirect, not a render

A resolver that renders HTML inline becomes a CDN for whoever publishes the
DPP. Mixing roles invites brittle assumptions about who can change what,
where caches sit, and who is responsible for analytics. The resolver's job
is to *route*; the publisher's job is to *serve*. The 302 redirect is the
cleanest contract.

## Layer 5 — Validator

Source: `resolver/validator.py`.

The validator is a pluggable hook that runs *after* a route is chosen and
*before* the response is built. It receives the parsed URI and the resolved
target URL, and returns a `ValidationResult` (ok / profile / errors /
warnings). Three implementations ship in-tree:

| Implementation     | What it does                                                              |
|--------------------|---------------------------------------------------------------------------|
| `NoOpValidator`    | Default. Never flags anything. Zero overhead.                            |
| `SmokeValidator`   | Built-in URI-shape sanity checks: serial/lot character class, unknown AIs. |
| `SchemaValidator`  | JSON-Schema check against a CIRPASS-2 profile (e.g. textile or battery). |

Operators select a validator in the routes YAML:

```yaml
validator:
  type: schema
  schema_path: /etc/gs1-resolver/cirpass2-textile.schema.json
  profile: cirpass2-textile-2026
```

The `Validator` protocol is `runtime_checkable`, so any class with a
`validate(parsed, target_url) -> ValidationResult` method satisfies it.
This is the integration point for the CIRPASS-2 reference validator
(milestone 3 of the NGI Commons Fund grant) — an `HttpValidator` that
POSTs the resolved target to the CIRPASS-2 endpoint and surfaces the
verdict in the link-set without blocking the response.

### Why advisory, not blocking

A resolver that 404s on a soft DPP validation failure is in practice
unusable: every minor schema drift across thousands of brands becomes a
support call. The right architecture surfaces the failure (so machine
consumers and market surveillance authorities can see it) and continues
to resolve. Hard failures (corrupt URI, failing GTIN check digit, no
route match) are still hard failures — they happen at Layer 1 / 2,
before the validator ever runs.

## Standards references

| Standard / spec                                                  | Where it's enforced                          |
|------------------------------------------------------------------|----------------------------------------------|
| GS1 Digital Link Standard v1.2 — §4.4 URI shapes                 | `parser._normalise_alpha`, `_AI_PATH_RE`     |
| GS1 Digital Link Standard v1.2 — §4.6 canonicalisation           | `parser.canonicalise`                        |
| GS1 Digital Link Standard v1.2 — §6.4 `?linkType=`               | `linkset.build_linkset`                      |
| GS1 General Specifications — AI definitions (DL-compatible subset)| `ai_table.AI_TO_SPEC`                        |
| GS1 General Specifications — GTIN-14 mod-10 check                 | `parser.validate_gtin14`                     |
| GS1 Web Vocabulary — relation IRIs (`/voc/pip`, etc.)            | `linkset.SHORT_TO_VOC`, `linkset.expand_rel` |
| GS1 Resolver Conformance Document — link-set response shape     | `linkset.build_linkset`                      |
| IETF RFC 9264 — Linkset media type and link-relation type       | `linkset.build_linkset`                      |
| IETF RFC 8288 — Web Linking (bare relation tokens pass-through) | `linkset.expand_rel`                         |
| IETF RFC 7231 §5.3.2 — Accept header, q-values                  | `negotiate._parse_accept`, `select_media_type` |
| W3C JSON-LD 1.1 — `@context` for ld+json variant                | `linkset.build_jsonld`                       |
| ISO/IEC 15459 — Unique identifiers (DL underpinning)             | parser/AI table coverage                     |

## Extension points

Each layer's boundary is small enough to swap independently.

| Layer                | Replacement scenario                                                                                                       |
|----------------------|-----------------------------------------------------------------------------------------------------------------------------|
| Parser               | Add new primary AIs (e.g. AIDC identifiers for industrial inventory) by extending `ai_table.AI_TO_SPEC`.                    |
| Router               | Swap `Router` for a DB- or HTTP-backed implementation that exposes `resolve(parsed) -> (target, links)`.                    |
| Link-set builder     | Customise relation expansion by mutating `SHORT_TO_VOC` at startup; emit additional sidecar fields by post-processing the response. |
| Content negotiation  | Add a new media type by extending `OFFERS` and routing it in `app.resolve`.                                                  |
| Validator            | Implement the `Validator` protocol; wire it up via the `validator:` block in YAML or by assigning to `router.validator`.    |

The HTTP service layer (`app.py`) is intentionally thin — about 50 lines —
so a project that wants a different framework (Starlette directly, Litestar,
Flask, Django REST Framework, AWS Lambda) can port the dispatcher in an
afternoon. Everything below `app.py` is pure Python with no web-framework
dependency.

## Non-goals

A resolver is not the same artefact as a DPP platform, a label generator,
or a verifiable-credentials issuer. The resolver:

- Does **not** mint, store, or sign DPPs.
- Does **not** generate QR codes or barcodes.
- Does **not** authenticate physical product units (cryptographic
  per-unit authenticity is a separate concern — see [OrigoVero](https://www.origovero.com)
  for one approach).
- Does **not** retain logs of who scanned what — that is a privacy and a
  publisher concern, not a routing concern.

Mixing any of these into a resolver couples it to a particular DPP-platform
roadmap and limits its usefulness as open infrastructure. The intention is
that anyone — brands, national authorities, competing DPP platforms, the
CIRPASS-2 Community of Practice — can deploy this image and trust it to do
exactly one job well.
