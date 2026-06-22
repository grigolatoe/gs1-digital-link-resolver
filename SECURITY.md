# Security Policy

## Supported versions

This project is pre-1.0 and under active development. Security fixes are applied
to the **latest released version** (currently the `0.3.x` line) and `main`.
Older tags are not patched — please upgrade to the latest release.

| Version | Supported |
|---------|-----------|
| latest release (`0.3.x`) | ✅ |
| `main` | ✅ |
| older tags | ❌ |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security reports.**

Email **[security@grigolato.it](mailto:security@grigolato.it)** with:

- a description of the issue and its impact,
- steps to reproduce (a minimal GS1 Digital Link URI or `routes.yaml` snippet is
  ideal), and
- the affected version / commit.

You may encrypt your report to the maintainer's PGP key
`47DE71F021C986123851E8AD65A8E29C92A63D38` (the same key used to sign releases;
see [SIGNING.md](SIGNING.md) for how to fetch it).

You can also use GitHub's **"Report a vulnerability"** (private advisory) flow on
the repository's *Security* tab.

## What to expect

- **Acknowledgement** within a few business days.
- We **coordinate disclosure** with you and aim to ship a fix before any public
  details are released.
- We **credit you** in the release notes unless you prefer to remain anonymous.

## Scope

This is a **stateless routing service** that parses GS1 Digital Link URIs and
returns link-sets from declarative configuration. Relevant classes of issue
include, for example:

- parser issues leading to crashes, hangs, or excessive resource use on crafted
  input (note: input is already bounded by `MAX_URI_LENGTH`);
- a route/template substitution flaw that emits an unintended target;
- a validator (`schema`/`http`) interaction that could be abused (e.g. SSRF via a
  misconfigured endpoint) — note these are operator-configured and advisory.

Out of scope (by design — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#non-goals)):

- the resolver has **no authentication layer** (access control belongs at the DPP
  endpoint), so "there is no auth" is not a vulnerability;
- the security of the DPP endpoints a resolver points to;
- denial of service from traffic volume against your own deployment (capacity is
  an operator concern — see [docs/deployment.md](docs/deployment.md)).
