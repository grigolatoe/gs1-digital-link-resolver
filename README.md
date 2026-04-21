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
  - match:
      gtin_prefix: "978"          # match by GTIN prefix
    target: "https://dpp.example.com/passport/{gtin}/{serial}"
    link_types:
      - rel: "gs1:pip"
        href: "https://dpp.example.com/passport/{gtin}/{serial}"
        type: "text/html"
        title: "Product Information Page"
      - rel: "gs1:verificationService"
        href: "https://dpp.example.com/api/verify/{gtin}/{serial}"
        type: "application/json"

  - match:
      gtin_prefix: "200"          # internal/private GTINs
    target: "https://internal.example.com/dpp/{gtin}"

  - match: "*"                    # default fallback
    target: "https://id.gs1.org/01/{gtin}"
```

## Content negotiation

| Accept header | Response |
|---|---|
| `text/html` (default) | 302 redirect to product page |
| `application/ld+json` | 200 JSON-LD link set |
| `application/json` | 200 JSON link set |
| `*/*` | 200 JSON link set (GS1 Digital Link link resolver response format) |

## CIRPASS-2 integration *(planned)*

A future milestone will add optional DPP completeness validation via the CIRPASS-2 open-source validator. When enabled, the resolver will verify DPP data at resolve time and log validation results without blocking resolution.

## Project status

Early development — initial URI parser, routing engine, and HTTP service are implemented as a working scaffold. A funding application has been submitted to [NGI Zero Commons Fund](https://nlnet.nl/commonsfund/) (NLnet Foundation, EU-funded).

**Roadmap:**

| | Milestone |
|---|---|
| ✅ | GS1 DL v1.2 URI parser — numeric AI and alpha-coded forms, GTIN-14 validation |
| ✅ | Routing engine — declarative YAML config, prefix/regex matching, link types |
| ✅ | HTTP service — FastAPI, content negotiation, Docker image |
| 🔲 | Full ESPR/DPP profile — complete AI coverage, GS1 conformance test suite |
| 🔲 | CIRPASS-2 validator integration |
| 🔲 | Deployment documentation and operator guide |

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
