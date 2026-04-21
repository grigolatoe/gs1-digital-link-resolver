# GS1 Digital Link Resolver

An open-source, self-hostable resolver for GS1 Digital Link URIs — the foundational routing layer for EU Digital Product Passports (ESPR/Ecodesign Regulation).

## What this is

Every product that carries a Digital Product Passport (DPP) under the EU Ecodesign for Sustainable Products Regulation (ESPR, EU 2024/1781) must have a machine-readable data carrier — a QR code or NFC tag — that encodes a standardised URL. That URL follows the **GS1 Digital Link** standard (ISO/IEC 15459).

When a consumer, logistics operator, or market surveillance authority scans the product, a resolver maps the URL to the correct DPP endpoint. Without a resolver, the QR code goes nowhere.

This project provides that resolver as a complete, self-hostable service:

- Parses GS1 Digital Link URIs per **GS1 Digital Link standard v1.2**
- Routes resolved URIs to DPP endpoints via declarative YAML configuration
- Handles **content negotiation** — HTML for browsers, `application/ld+json` for machines (CIRPASS-2 best practice)
- Validates DPP completeness via optional **CIRPASS-2 validator** integration
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
docker run -p 8080:8080 \
  -v ./config/routes.yaml:/app/config/routes.yaml \
  ghcr.io/grigolatoe/gs1-digital-link-resolver:latest
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
| `application/ld+json` | 200 JSON-LD DPP data |
| `application/json` | 200 JSON DPP summary |
| `*/*` | 200 link set (GS1 Digital Link link resolver response) |

## CIRPASS-2 integration

When `cirpass2.enabled: true` is set in configuration, the resolver optionally validates the DPP completeness at resolve time by calling the CIRPASS-2 open-source validator. Validation failures are logged but do not block resolution (non-breaking).

## Project status

Active development. Funding application submitted to [NGI Zero Commons Fund](https://nlnet.nl/commonsfund/) (NLnet Foundation, EU-funded).

| Milestone | Status |
|---|---|
| GS1 DL v1.2 URI parser + architecture | In progress |
| Core resolver + configurable routing | Planned |
| ESPR/DPP profile + content negotiation | Planned |
| CIRPASS-2 validator integration | Planned |
| Docker image + deployment docs | Planned |

## Standards references

- [GS1 Digital Link Standard v1.2](https://www.gs1.org/standards/gs1-digital-link)
- [ISO/IEC 15459 — Unique Identifiers](https://www.iso.org/standard/54782.html)
- [ESPR — EU 2024/1781](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1781)
- [CIRPASS-2 Community of Practice](https://cirpass-2.eu)

## Contributing

Issues and PRs welcome. This project is developed in active collaboration with the [CIRPASS-2 Community of Practice](https://cirpass-2.eu) — a 500+ member EU network of DPP platform providers, brands, and standards bodies.

## Licence

Apache 2.0 — see [LICENSE](LICENSE).

Copyright 2026 Grigolato.it
