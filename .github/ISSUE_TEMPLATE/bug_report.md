---
name: Bug report
about: Something works incorrectly — wrong response, wrong status, crash, regression
title: "[bug] "
labels: ["bug"]
---

## What happened

<!-- One sentence describing the observed behaviour. -->

## Reproduction

Minimal steps to reproduce. If the bug is in the parser or router, please
include the exact URI or YAML config that triggers it.

```bash
# example
docker run -p 8080:8080 -v ./config/routes.yaml:/app/config/routes.yaml \
  ghcr.io/grigolatoe/gs1-digital-link-resolver:latest

curl -i http://localhost:8080/01/09780345418913/21/ABC123
```

## Expected behaviour

What you expected the resolver to do. If the expectation is based on a
specific section of the GS1 Digital Link standard, RFC 9264, or another
spec, please cite it (section number is enough).

## Actual behaviour

What you observed. HTTP status, response body, log lines — anything that
helps narrow down the layer.

## Environment

- Resolver version (tag or commit SHA): 
- Deployment (Docker image, local Python, k8s): 
- Python version (if running locally): 
- Operating system: 

## Additional context

Logs, screenshots, related issues, anything else.
