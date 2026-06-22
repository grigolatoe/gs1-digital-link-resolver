# GS1 Digital Link Resolver

An open-source, self-hostable resolver for GS1 Digital Link URIs — the foundational routing layer for EU Digital Product Passports (ESPR/Ecodesign Regulation).

## What this is

Every product that carries a Digital Product Passport (DPP) under the EU Ecodesign for Sustainable Products Regulation (ESPR, EU 2024/1781) must have a machine-readable data carrier — a QR code or NFC tag — that encodes a standardised URL. That URL follows the **GS1 Digital Link** standard (ISO/IEC 15459).

When a consumer, logistics operator, or market surveillance authority scans the product, a resolver maps the URL to the correct DPP endpoint. Without a resolver, the QR code goes nowhere.

This project provides that resolver as a complete, self-hostable service:

- Parses GS1 Digital Link URIs per **GS1 Digital Link standard v1.2**
- Routes resolved URIs to DPP endpoints via declarative YAML configuration
- Handles **content negotiation** — HTML for browsers, `application/ld+json` for machines
- Ships as a **single Docker image**, deployable in under 10 minutes

**Licence:** Apache 2.0 — use freely in any context, commercial or otherwise.

## Why this exists

Despite GS1 Digital Link being the mandatory URL scheme for every ESPR-compliant DPP, there is no mature open-source resolver. Every DPP platform — from individual brands to national authorities — must build this layer privately or depend on a commercial vendor.

This project removes that barrier.

## Supported GS1 Application Identifiers

| AI | Name | Example |
|----|------|---------|
| 01 | GTIN (primary key) | `/01/09780345418913` |
| 10 | Batch / Lot | `/10/BATCH2024` |
| 17 | Expiry Date | `/17/251231` |
| 21 | Serial Number | `/21/ABC123` |
| 22 | Consumer Product Variant | `/22/V2` |
| 235 | Third-Party Extended Packaging ID | `/235/TPX001` |

## Quick start

The release image ships on the GitHub Container Registry:

```bash
docker run -p 8080:8080 \
  ghcr.io/grigolatoe/gs1-digital-link-resolver:0.3.0
```

That binds the resolver on `localhost:8080` with the example config bundled
into the image. To bring your own routes, mount over `/app/config/routes.yaml`:

```bash
docker run -p 8080:8080 \
  -v ./config/routes.yaml:/app/config/routes.yaml \
  ghcr.io/grigolatoe/gs1-digital-link-resolver:0.3.0
```

Then visit:

```
http://localhost:8080/01/09780345418913/21/ABC123
```

The resolver parses the GTIN (`09780345418913`) and serial (`ABC123`), looks up the routing rule, and returns an RFC 9264 link-set (or redirects to the default link if the client asked for HTML).

### Build from source instead

```bash
git clone https://github.com/grigolatoe/gs1-digital-link-resolver.git
cd gs1-digital-link-resolver
cp config/routes.example.yaml config/routes.yaml
docker build -t gs1-resolver .
docker run -p 8080:8080 -v ./config/routes.yaml:/app/config/routes.yaml gs1-resolver
```

### Verify the published image

Every release is signed with a PGP key under the maintainer's direct
control (the same key attached to the NLnet NGI Zero Commons Fund
application). See **[SIGNING.md](SIGNING.md)** for the verification
procedure; the short version is:

```bash
gpg --keyserver hkps://keys.openpgp.org --recv-keys 47DE71F021C986123851E8AD65A8E29C92A63D38
gh release download v0.3.0 --repo grigolatoe/gs1-digital-link-resolver --pattern 'SIGNATURES-*'
gpg --verify SIGNATURES-v0.3.0.txt.asc SIGNATURES-v0.3.0.txt
docker pull ghcr.io/grigolatoe/gs1-digital-link-resolver:0.3.0
# The digest reported by docker must match the one in SIGNATURES-v0.3.0.txt.
```

## Configuration

```yaml
# config/routes.yaml
resolvers:
  # Note: GTIN-14 in DL URIs is left-padded with zero, so a "books"
  # company prefix of 978 appears in DL URIs as "0978..." — match accordingly.
  - match:
      gtin_prefix: "0978"
    target: "https://dpp.example.com/passport/{gtin}/{serial}"
    link_types:
      - rel: "gs1:pip"
        href: "https://dpp.example.com/passport/{gtin}/{serial}"
        type: "text/html"
        title: "Product Information Page"
      - rel: "gs1:verificationService"
        href: "https://dpp.example.com/api/verify/{gtin}/{serial}"
        type: "application/json"
      - rel: "gs1:digitalProductPassport"
        href: "https://dpp.example.com/dpp/{gtin}/{serial}.json"
        type: "application/ld+json"

  - match:
      primary_ai: "8003"          # GRAI for returnable assets
    target: "https://assets.example.com/grai/{8003}"

  - match: "*"                    # default fallback
    target: "https://id.gs1.org/01/{gtin}"
```

## Content negotiation

| Accept header | Response |
|---|---|
| `application/linkset+json` (default) | 200 RFC 9264 link-set with GS1 Web Vocabulary relation IRIs |
| `application/ld+json` | 200 JSON-LD link-set with `gs1:` context binding |
| `application/json` | 200 link-set in RFC 9264 shape |
| `text/html` | 302 redirect to the link-set's default link |
| `*/*` (or empty) | 200 RFC 9264 link-set |

The `?linkType=` query parameter (per GS1 DL §6.4) narrows the response to a single relation when provided. Q-values are honoured.

## DPP validator hook

The resolver supports a pluggable validator that runs at resolve time and reports its outcome in the link-set response under `gs1:validationStatus`. Four implementations ship in-tree:

- **`noop`** (default) — zero overhead, never flags anything
- **`smoke`** — built-in URI-shape sanity checks (serial/lot character class, unknown AIs)
- **`schema`** — fetches the target DPP and validates it against a JSON Schema *you* supply, surfacing every violation
- **`http`** — delegate to an external DPP validator service: POSTs the resolved URI + target DPP URL to a configured `endpoint` and maps the verdict back

The `schema` and `http` validators need the optional extra (`pip install '.[validators]'`, which adds `httpx` + `jsonschema`); without it they degrade gracefully to a no-op. Configure via the `validator:` block in `routes.yaml`:

```yaml
validator:
  type: schema
  schema_path: /app/profiles/illustrative-dpp.schema.json   # bring your own
  profile: illustrative-dpp
```

**Profiles — bring your own.** There is, as of mid-2026, no canonical machine-readable CIRPASS-2 profile to bundle: CIRPASS-2 publishes data models and architecture docs, not JSON Schemas, and the closest emerging machine-readable standard — the [UN Transparency Protocol (UNTP)](https://untp.unece.org) — is still in pre-stable public review under a copyleft licence. So this repo ships only a small **illustrative, non-normative** profile (`profiles/illustrative-dpp.schema.json`) to exercise the validator; point `schema_path` at your own ESPR/UNTP-aligned schema for real compliance checks. See [`profiles/README.md`](profiles/README.md).

Operators can also implement the `Validator` protocol themselves. Validation outcomes are advisory — failures are surfaced in the response but never block resolution; any validator-side error (unreachable endpoint, unparseable body, missing optional dependency) degrades to a soft warning.

## Project status

Active development. A funding application has been submitted to [NGI Zero Commons Fund](https://nlnet.nl/commonsfund/) (NLnet Foundation, EU-funded).

**Roadmap:**

| | Milestone |
|---|---|
| ✅ | GS1 DL v1.2 URI parser — numeric AI and alpha-coded forms, full DL-compatible AI table |
| ✅ | GTIN-14 mod-10 validation, canonical URI generation |
| ✅ | Routing engine — declarative YAML, prefix/regex/primary-AI/has-qualifier/serial-allowlist clauses |
| ✅ | RFC 9264 link-set responses with GS1 Web Vocabulary IRIs |
| ✅ | Content negotiation with q-value handling |
| ✅ | Pluggable validator interface (no-op, smoke, schema, http) |
| ✅ | HTTP service — FastAPI, Docker image |
| ✅ | Conformance test suite (110 tests against GS1 DL §4.4–§4.6 + RFC 9264) |
| ✅ | DPP validator wire-up — `schema` (live fetch + JSON-Schema) and `http` (external delegate) |
| ✅ | Deployment / operator guide — [`docs/deployment.md`](docs/deployment.md) |
| ✅ | Prometheus `/metrics` endpoint (requests, validations, latency, build info) |
| 🔲 | Bundled normative DPP profile — pending a stable, openly-licensed standard (tracking UNTP) |

## Standards references

- [GS1 Digital Link Standard v1.2](https://www.gs1.org/standards/gs1-digital-link)
- [ISO/IEC 15459 — Unique Identifiers](https://www.iso.org/standard/54782.html)
- [ESPR — EU 2024/1781](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1781)
- [CIRPASS-2 Community of Practice](https://cirpass-2.eu)

## Contributing

Issues and PRs welcome. This project aims to serve the [CIRPASS-2 Community of Practice](https://cirpass-2.eu) — a 500+ member EU network of DPP platform providers, brands, and standards bodies — and the broader ESPR compliance ecosystem.

## Who built this

This resolver is maintained by **[Grigolato.IT](https://www.grigolato.it)** (Almere, Netherlands, KvK 97060658) — the company behind **[OrigoVero](https://www.origovero.com)**, the Digital Product Passport platform with per-unit authenticity, multi-actor on-chain custody, and dual-factor QR + NFC verification.

OrigoVero uses this resolver in production to serve GS1 Digital Link URIs across multiple EU regulatory streams (wine, batteries, textiles, toys, packaging, construction). The resolver is released independently under Apache 2.0 so any DPP platform, brand, or compliance authority can run it without commercial dependency.

- OrigoVero: <https://www.origovero.com>
- CIRPASS-2 Community of Practice member (Grigolato.IT, since March 2026)
- This resolver and its codebase are independent open source under Apache 2.0.

## Licence

Apache 2.0 — see [LICENSE](LICENSE).

Copyright 2026 Grigolato.it
