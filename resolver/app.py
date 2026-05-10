"""
app.py — HTTP resolver service

Exposes a single endpoint that accepts GS1 Digital Link URI paths,
parses them, and responds according to content negotiation rules:

  Accept: text/html                  → 302 to the default link's href
  Accept: application/linkset+json   → 200 RFC 9264 link-set
  Accept: application/ld+json        → 200 JSON-LD link-set
  Accept: application/json           → 200 link-set (RFC 9264 shape)
  Accept: */*  (or anything else)    → 200 link-set (RFC 9264 shape)

Per GS1 DL §6.4 the `?linkType=` query parameter narrows the response to a
single relation when supplied.

Run with:
    uvicorn resolver.app:app --host 0.0.0.0 --port 8080

Or via Docker:
    docker run -p 8080:8080 -v ./config/routes.yaml:/app/config/routes.yaml \
      ghcr.io/grigolatoe/gs1-digital-link-resolver:latest
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse

from .linkset import build_jsonld, build_linkset, default_link_href
from .negotiate import select_media_type
from .parser import parse, validate_gtin14
from .router import Router

CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "/app/config/routes.yaml"))

app = FastAPI(
    title="GS1 Digital Link Resolver",
    description="Open-source resolver for EU Digital Product Passports",
    version="0.2.0",
    license_info={"name": "Apache 2.0", "url": "https://www.apache.org/licenses/LICENSE-2.0"},
)

_router: Router | None = None


def get_router() -> Router:
    global _router
    if _router is None:
        _router = Router(CONFIG_PATH)
    return _router


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/{path:path}")
async def resolve(path: str, request: Request) -> Response:
    full_path = "/" + path
    query_string = str(request.url.query)
    uri = full_path + (f"?{query_string}" if query_string else "")

    try:
        parsed = parse(uri)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    if parsed.gtin and not validate_gtin14(parsed.gtin):
        return JSONResponse(
            {"error": f"Invalid GTIN-14 check digit: {parsed.gtin}"},
            status_code=400,
        )

    result = get_router().resolve(parsed)
    if result is None:
        return JSONResponse({"error": "No route found for this identifier"}, status_code=404)

    target, link_types = result
    requested_lt = parsed.link_type
    accept = request.headers.get("accept", "")
    chosen = select_media_type(accept)

    router = get_router()
    validation = router.validator.validate(parsed, target).as_dict()
    # Drop validation entirely when the validator is a no-op so we don't
    # clutter responses for operators who haven't opted in.
    validation_payload = validation if validation.get("profile") else None

    anchor = str(request.url)
    linkset = build_linkset(
        anchor=anchor,
        links=link_types,
        requested_link_type=requested_lt,
        validation=validation_payload,
    )

    if chosen == "text/html":
        href = default_link_href(linkset) or target
        return RedirectResponse(url=href, status_code=302)

    if chosen == "application/ld+json":
        return JSONResponse(build_jsonld(linkset), media_type="application/ld+json")
    return JSONResponse(linkset, media_type=chosen)
