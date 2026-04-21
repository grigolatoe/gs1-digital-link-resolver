"""
app.py — HTTP resolver service

Exposes a single endpoint that accepts GS1 Digital Link URI paths,
parses them, and responds according to content negotiation rules.

Run with:
    uvicorn resolver.app:app --host 0.0.0.0 --port 8080

Or via Docker:
    docker run -p 8080:8080 -v ./config/routes.yaml:/app/config/routes.yaml \
      ghcr.io/grigolatoe/gs1-digital-link-resolver:latest
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse

from .parser import parse, validate_gtin14
from .router import Router

CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "/app/config/routes.yaml"))

app = FastAPI(
    title="GS1 Digital Link Resolver",
    description="Open resolver for EU Digital Product Passports",
    version="0.1.0",
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
    """
    Resolve a GS1 Digital Link URI path.

    Content negotiation:
    - Accept: text/html → 302 redirect to product page
    - Accept: application/ld+json → 200 JSON-LD link set
    - Accept: application/json → 200 JSON link set
    - default → 200 JSON link set (GS1 DL link resolver response format)
    """
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
    accept = request.headers.get("accept", "text/html")

    if "text/html" in accept:
        return RedirectResponse(url=target, status_code=302)

    link_set = {
        "linkset": [
            {
                "anchor": str(request.url),
                **{
                    lt.rel: [
                        {"href": lt.href, "type": lt.type, "title": lt.title}
                    ]
                    for lt in link_types
                },
            }
        ]
    }

    media_type = "application/ld+json" if "ld+json" in accept else "application/json"
    return JSONResponse(link_set, media_type=media_type)
