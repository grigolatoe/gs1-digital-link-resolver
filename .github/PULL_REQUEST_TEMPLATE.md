<!--
Thanks for sending a PR. A few things make review faster:
  - One change per PR (no mixed refactor + feature)
  - Tests included for behaviour change
  - CI green (pytest, ruff check, ruff format --check, docker smoke)
See CONTRIBUTING.md for the full checklist.
-->

## Summary

<!-- One or two sentences: what does this PR do, and why is it needed? -->

## Type of change

- [ ] Bug fix (non-breaking, restores correct behaviour)
- [ ] New feature (non-breaking, adds capability)
- [ ] Breaking change (existing behaviour or response shape changes)
- [ ] Documentation only
- [ ] Refactor / internal cleanup (no behaviour change)

## Standards reference

<!--
If the change reflects a GS1 or IETF spec requirement, cite the section
here. If not, skip this block. Examples:
  - GS1 DL v1.2 §4.6 canonicalisation
  - IETF RFC 9264 §4.2 link-set anchor handling
-->

## Test plan

- [ ] Existing tests still pass (`pytest -q`)
- [ ] New tests added for the changed behaviour
- [ ] Lints clean (`ruff check`, `ruff format --check`)

## Related issue

<!-- Closes #123, or "n/a" -->
