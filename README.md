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

```bash
git clone https://github.com/grigolatoe/gs1-digital-link-resolver.git
cd gs1-digital-link-resolver
cp config/routes.example.yaml config/routes.yaml
docker build -t gs1-resolver .
docker run -p 8080:8080 -v ./config/routes.yaml:/app/config/routes.yaml gs1-resolver
```

Then scan or visit:

```
http://localhost:8080/01/09780345418913/21/ABC123
```

The resolver parses the GTIN (`09780345418913`) and serial (`ABC123`), looks up the routing rule, and redirects to the configured DPP endpoint.

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

The resolver supports a pluggable validator that runs at resolve time and reports its outcome in the link-set response under `gs1:validationStatus`. Three implementations ship in-tree:

- **`noop`** (default) — zero overhead, never flags anything
- **`smoke`** — built-in URI-shape sanity checks (serial/lot character class, unknown AIs)
- **`schema`** — JSON-Schema check against a CIRPASS-2 profile (e.g. textile or battery)

Operators can also implement the `Validator` protocol themselves. Validation outcomes are advisory — failures are surfaced in the response but never block resolution. The full CIRPASS-2 reference validator integration lands in a follow-up milestone.

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
| ✅ | Pluggable validator interface (no-op, smoke, JSON-schema) |
| ✅ | HTTP service — FastAPI, Docker image |
| ✅ | Conformance test suite (86+ tests against GS1 DL §4.4–§4.6 + RFC 9264) |
| 🔲 | CIRPASS-2 reference validator wire-up |
| 🔲 | Deployment / operator guide |

## Standards references

- [GS1 Digital Link Standard v1.2](https://www.gs1.org/standards/gs1-digital-link)
- [ISO/IEC 15459 — Unique Identifiers](https://www.iso.org/standard/54782.html)
- [ESPR — EU 2024/1781](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1781)
- [CIRPASS-2 Community of Practice](https://cirpass-2.eu)

## Contributing

Issues and PRs welcome. This project aims to serve the [CIRPASS-2 Community of Practice](https://cirpass-2.eu) — a 500+ member EU network of DPP platform providers, brands, and standards bodies — and the broader ESPR compliance ecosystem.

## Licence

Apache 2.0 — see [LICENSE](LICENSE).

Copyright 2026 Grigolato.it
