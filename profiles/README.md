# DPP validation profiles

JSON Schemas for the resolver's `schema` validator (`validator.type: schema`,
`schema_path: ...`). The validator fetches the target DPP document and checks
it against the configured schema, surfacing any violations in the link-set
response under `gs1:validationStatus` — advisory only, never blocking.

## What ships here

- **`illustrative-dpp.schema.json`** — a deliberately minimal, **non-normative**
  example profile. It exists so the `schema` validator has something to run out
  of the box and so the docs have a concrete reference. **Do not rely on it for
  compliance.**

## Why no bundled "CIRPASS-2 textile/battery" profile

There is, as of this writing (June 2026), **no canonical, machine-readable
CIRPASS-2 JSON Schema to bundle**:

- **CIRPASS-2** (2024–2027; textiles, electronics, tyres, construction — *not*
  batteries) is a pilots-and-standardisation project. It publishes **data models
  and architecture documents**, not downloadable JSON Schemas.
- The closest emerging machine-readable standard is the **UN Transparency
  Protocol (UNTP)** by UNECE — JSON Schema `v0.7.0`, in a public review period
  closing **13 July 2026**, "suitable for pre-production pilot implementations".
  Its source repository is **GPL-3.0**, which is incompatible with vendoring into
  this Apache-2.0 project, so we **reference it rather than copy it**.

## Bring your own

Point the validator at any JSON Schema you control or trust:

```yaml
validator:
  type: schema
  schema_path: /app/profiles/your-profile.schema.json
  profile: my-espr-textile-2026
```

To validate against UNTP, download its schema from
<https://untp.unece.org/artefacts/schema/v0.7.0/dpp/> (review its licence and
version first) and reference the local copy, or use the `http` validator to
delegate to an external validation service.
