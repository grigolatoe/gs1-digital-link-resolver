# Deployment & operator guide

How to run the GS1 Digital Link Resolver in production. The resolver is a
single, **stateless** HTTP service: it parses GS1 Digital Link URIs and returns
RFC 9264 link-sets from declarative YAML configuration. It holds no database
and no per-request state, so it scales horizontally by simply running more
replicas behind a load balancer.

- [Architecture at a glance](#architecture-at-a-glance)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Running behind a reverse proxy (TLS)](#running-behind-a-reverse-proxy-tls)
- [Docker Compose](#docker-compose)
- [Kubernetes](#kubernetes)
- [Health checks & observability](#health-checks--observability)
- [Scaling & performance](#scaling--performance)
- [Security](#security)
- [Upgrades & rollback](#upgrades--rollback)
- [Troubleshooting](#troubleshooting)

## Architecture at a glance

| Property | Value |
|---|---|
| Process | `uvicorn resolver.app:app` (ASGI / FastAPI) |
| Port | `8080` (container) |
| State | **None** — config is read once at startup; no DB, no disk writes |
| Health endpoint | `GET /healthz` → `{"status":"ok"}` |
| Resolve endpoint | `GET /{gs1-dl-path}` → 200 link-set / 302 (HTML) / 400 / 404 |
| Config source | `routes.yaml`, located via `CONFIG_PATH` |
| Footprint | tens of MB RAM; CPU-bound on parsing only; sub-millisecond per resolve |

Because the service is stateless and config is loaded at startup, **deployment is
"pull image, mount config, run"** and a config change means "redeploy / restart",
not a live reload.

## Quick start

```bash
docker run -p 8080:8080 \
  -v ./config/routes.yaml:/app/config/routes.yaml \
  ghcr.io/grigolatoe/gs1-digital-link-resolver:0.3.0
```

Verify it's up:

```bash
curl -fsS http://localhost:8080/healthz          # {"status":"ok"}
curl -fsS http://localhost:8080/01/09780345418913/21/ABC123 | jq .
```

Pin a specific version tag in production (e.g. `:0.3.0`), not `:latest`, so
rollouts are deliberate. Every tag is PGP-signed — see
[SIGNING.md](../SIGNING.md) to verify the image before deploying.

## Configuration

### Locating the config

| Env var | Default | Purpose |
|---|---|---|
| `CONFIG_PATH` | `/app/config/routes.yaml` | Absolute path to the routing config |

Mount your `routes.yaml` over the bundled example, or set `CONFIG_PATH` to a
different location. Start from
[`config/routes.example.yaml`](../config/routes.example.yaml).

### Routing rules

Routes are matched top-to-bottom, first match wins. Match clauses: `gtin_prefix`,
`gtin_regex`, `primary_ai`, `has_qualifier`, `serial_in`, and `*` (fallback).
Always end with a `*` fallback so no scan dead-ends. See the example config for
annotated rules and the GTIN-14 left-padding note.

### Validator (optional)

The `validator:` block attaches an advisory DPP check to every resolve, surfaced
as `gs1:validationStatus` in the link-set. Types: `noop` (default), `smoke`
(built-in, no deps), `schema` (fetch + JSON-Schema), `http` (delegate to an
external service). The `schema` and `http` validators need the optional
dependencies — if you enable them, build/run with the extra installed:

```dockerfile
# In a derived image, or adjust the base image build:
RUN pip install --no-cache-dir 'gs1-digital-link-resolver[validators]'
```

Validation is **always advisory** — it never blocks resolution. See the main
[README](../README.md#dpp-validator-hook) and
[`profiles/README.md`](../profiles/README.md).

## Running behind a reverse proxy (TLS)

The resolver speaks plain HTTP on `:8080`. **Terminate TLS at a reverse proxy** —
resolvers are public infrastructure and DPP URLs are HTTPS by spec.

### Caddy

```caddy
resolver.example.com {
    reverse_proxy localhost:8080
}
```

Caddy provisions and renews certificates automatically.

### nginx

```nginx
server {
    listen 443 ssl;
    server_name resolver.example.com;

    ssl_certificate     /etc/letsencrypt/live/resolver.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/resolver.example.com/privkey.pem;

    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_set_header   Host $host;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
```

The link-set `anchor` echoes the request URL, so forwarding `Host` /
`X-Forwarded-Proto` keeps the anchors correct.

## Docker Compose

```yaml
services:
  resolver:
    image: ghcr.io/grigolatoe/gs1-digital-link-resolver:0.3.0
    restart: unless-stopped
    volumes:
      - ./routes.yaml:/app/config/routes.yaml:ro
    ports:
      - "8080:8080"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/healthz').status==200 else 1)"]
      interval: 30s
      timeout: 3s
      retries: 3
```

## Kubernetes

The stateless design maps cleanly onto a `Deployment` + `Service`. Use
`/healthz` for both probes and a `ConfigMap` for `routes.yaml`.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gs1-resolver
spec:
  replicas: 3
  selector:
    matchLabels: { app: gs1-resolver }
  template:
    metadata:
      labels: { app: gs1-resolver }
    spec:
      containers:
        - name: resolver
          image: ghcr.io/grigolatoe/gs1-digital-link-resolver:0.3.0
          ports:
            - containerPort: 8080
          volumeMounts:
            - { name: config, mountPath: /app/config }
          readinessProbe:
            httpGet: { path: /healthz, port: 8080 }
            initialDelaySeconds: 2
          livenessProbe:
            httpGet: { path: /healthz, port: 8080 }
            periodSeconds: 15
          resources:
            requests: { cpu: 50m, memory: 64Mi }
            limits:   { cpu: 500m, memory: 256Mi }
      volumes:
        - name: config
          configMap: { name: gs1-resolver-routes }
```

Roll out config changes with `kubectl rollout restart deployment/gs1-resolver`
(config is read at startup).

## Health checks & observability

- **Liveness/readiness:** `GET /healthz` returns `200 {"status":"ok"}` and never
  touches config or downstreams — safe to poll frequently.
- **Logs:** uvicorn writes access/error logs to stdout/stderr; collect with your
  platform's log driver.
- **Metrics:** `GET /metrics` exposes Prometheus text-format metrics (no extra
  dependency):
  - `gs1_resolver_requests_total{outcome="resolved|redirect|not_found|bad_request"}`
  - `gs1_resolver_validations_total{ok="true|false"}` (omitted when the validator is no-op)
  - `gs1_resolver_resolve_duration_seconds_{sum,count}` — a summary; average
    latency = `rate(..._sum) / rate(..._count)`
  - `gs1_resolver_build_info{version="..."}`

  Counters are process-local: scrape each replica and aggregate at the
  Prometheus server (the standard multi-target pattern). Example scrape config:

  ```yaml
  scrape_configs:
    - job_name: gs1-resolver
      static_configs:
        - targets: ["resolver:8080"]
  ```

## Scaling & performance

- **Stateless → replicate freely.** Run N replicas behind any L7/L4 load
  balancer; no session affinity, no shared store.
- **CPU-bound, not IO-bound** — a resolve is URI parsing + an in-memory route
  lookup, sub-millisecond, unless a `schema`/`http` validator is enabled (which
  adds an outbound fetch — size `timeout` and replica count accordingly).
- **Config is in memory** — no per-request disk or network IO in the default
  (`noop`/`smoke`) configuration.

## Security

- **No auth by design.** A resolver is public routing infrastructure; access
  control belongs at the DPP endpoint it points to, not here.
- **Egress (validators).** The `schema`/`http` validators make outbound requests
  to the target DPP / a validation service. In locked-down networks, allowlist
  those destinations and keep `timeout` tight; failures degrade to advisory
  warnings and never block resolution.
- **Container hardening.** The image is single-purpose; run it read-only with a
  non-root user and a mounted read-only config (`:ro`). Set CPU/memory limits to
  bound abuse.
- **TLS.** Terminate at the proxy; never expose `:8080` directly to the internet.

## Upgrades & rollback

- **Pin tags.** Deploy `:X.Y.Z`, never `:latest`, in production.
- **Verify before deploy.** Check the PGP signature + image digest per
  [SIGNING.md](../SIGNING.md).
- **Rollback** = redeploy the previous pinned tag. Because the service is
  stateless, rollback is instant and side-effect-free.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `400 Invalid GTIN-14 check digit` | The GTIN failed mod-10 validation — check the carrier-encoded value |
| `400` on a path | Malformed GS1 DL URI (bad AI ordering / unknown structure) |
| `404 No route found` | No matching rule and no `*` fallback — add a fallback route |
| `gs1:validationStatus` absent | Validator is `noop` (default) — set a `validator:` block to opt in |
| `schema`/`http` validator silently no-ops | `validators` extra not installed in the image |
| Anchors show the wrong host/scheme | Reverse proxy not forwarding `Host` / `X-Forwarded-Proto` |
| Config change not taking effect | Config loads at startup — restart / redeploy the service |
