# Contributing

Thanks for your interest in the GS1 Digital Link Resolver. This project aims
to be reliable open infrastructure for the EU Digital Product Passport
ecosystem — that depends on careful, well-tested changes. Contributions of
all sizes are welcome, from typo fixes to new validator implementations.

## Ground rules

- **Be specific.** Bug reports and feature requests with reproduction steps,
  versions, and the relevant standard reference are far more useful than
  abstract requests. Issue templates are provided to make this easier.
- **Apache 2.0.** By contributing you agree your changes are licensed under
  the project's Apache 2.0 licence. Sign-off is not required; copyright
  remains with the contributor unless you state otherwise.
- **Be kind.** See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Disagreement is
  fine. Personal attacks aren't.

## Development setup

```bash
git clone https://github.com/grigolatoe/gs1-digital-link-resolver.git
cd gs1-digital-link-resolver

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run the test suite — should be green, fast (~0.1 s)
pytest -q

# Run the lints used in CI
ruff check resolver tests
ruff format --check resolver tests
```

Python 3.11 or 3.12 is required. The CI matrix tests both. We aim to keep
the runtime dependency set small (FastAPI, uvicorn, PyYAML); please open an
issue before adding a new dependency so we can discuss whether it earns its
weight.

## Pull request checklist

Before opening a PR, please:

1. **One change per PR.** Mixing a refactor with a feature makes review slow
   and rollback painful. Split them.
2. **Tests.** Every PR with behaviour change adds or updates a test. Aim for
   the test that would have caught the bug or proved the feature works in
   isolation, not an end-to-end smoke test.
3. **Standards citations.** If the change reflects a GS1 or IETF spec
   requirement, include the section number in the test name or the code
   comment so reviewers can verify against the source.
4. **Lints clean.** `ruff check` and `ruff format --check` both pass.
5. **CI green.** GitHub Actions runs the same checks; a red CI is a hard
   stop.

A short PR description that links to the relevant issue (if any) and
explains *why* the change is needed beats a long one that explains *what*
the change does — the diff already shows the what.

## How to add support for a new GS1 Application Identifier

The DL-compatible AI table lives in `resolver/ai_table.py`. To add a new AI:

1. Add the entry to `AI_TO_SPEC` with the correct length, category
   (`primary`, `qualifier`, or `attribute`), and the alpha name from the
   GS1 General Specifications.
2. If the AI is a *primary key*, add it to `PRIMARY_AIS` and define its
   qualifier ordering in `QUALIFIER_ORDER`.
3. Add a parser test in `tests/test_parser.py` covering at least one valid
   URI and one invalid one.
4. Add a conformance test in `tests/test_conformance.py` if the AI is
   exercised by a GS1 DL standard example.

Please cite the GS1 General Specifications section in the test name. The
table is small and stable; growing it carelessly is the easiest way to
break interoperability.

## How to add a new validator implementation

The `Validator` protocol is documented in `docs/ARCHITECTURE.md` (Layer 5).
In short:

1. Implement `validate(parsed: GS1ParseResult, target_url: str) -> ValidationResult`.
2. Make the class importable from `resolver.validator` if you want it
   built-in; otherwise distribute it as a separate package and load via the
   `validator:` block.
3. Add the `type:` token to the loader in `validator.load_validator`.
4. Tests: cover at least the success path, one failure-with-warnings path,
   and the "no jsonschema installed" graceful-degrade path if relevant.

Validators must be **advisory only** — a failure must never block resolution
or change the HTTP status. The link-set's `gs1:validationStatus` sidecar is
the contract.

## Reporting security issues

Please do **not** open a public issue for a security report. Email
[security@grigolato.it](mailto:security@grigolato.it) with details and we
will respond as soon as we can. We coordinate disclosure with the reporter
and credit you in the release notes unless you ask us not to.

## What is *not* in scope

This is a resolver, not a DPP platform. Please avoid PRs that:

- Mint, store, or sign Digital Product Passports.
- Render HTML DPP pages inline (the resolver redirects; the publisher renders).
- Generate or verify physical-product-authenticity proofs (out of scope —
  see the project's non-goals in `docs/ARCHITECTURE.md`).
- Add a database, an admin UI, or per-request mutable state.

If you have a use case that requires any of the above, please open a
discussion first — there may be a clean extension point, or it may belong
in a separate companion project.

## Releasing (maintainers)

Releases are cut from `main` once CI is green:

```bash
# Bump version in pyproject.toml
# Update CHANGELOG.md (when introduced)
git tag -a v0.x.y -m "v0.x.y — short summary"
git push origin v0.x.y
```

A GitHub release is created from the tag with the relevant section of the
changelog as the release notes. The Docker image is pushed to
`ghcr.io/grigolatoe/gs1-digital-link-resolver:v0.x.y` and
`:latest`.

## Questions

If something here is unclear, open an issue with the `question` label or
start a discussion. The project is small and approachable; we'd rather
answer one question well than have you guess.
