---
name: Feature request
about: Propose a new capability or extension
title: "[feat] "
labels: ["enhancement"]
---

## What problem are you trying to solve

The concrete problem this feature would address. A real-world scenario
beats an abstract description.

## Proposed solution

Your suggestion. If it touches a specific layer (parser, router,
link-set builder, content negotiation, validator), please say which —
the architecture is documented in [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md).

## Standards context

If the feature reflects a GS1 or IETF specification requirement, please
cite the section. Features grounded in a spec move faster than features
grounded in a single deployment.

## Alternatives considered

Other approaches you thought about and why you didn't pick them. Useful
even when short — it tells reviewers what's already been ruled out.

## Scope check

A few items that, if your feature touches them, mean we should discuss
before any code lands:

- [ ] Adds a new runtime dependency
- [ ] Introduces a database, admin UI, or per-request mutable state
- [ ] Mints, stores, or signs Digital Product Passports
- [ ] Renders HTML DPP content inline (rather than redirecting)

If none are checked, this is in scope.
