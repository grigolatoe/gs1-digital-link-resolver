"""
linkset.py — GS1 Digital Link link-set response format

Implements the link-set response format defined by GS1 in the GS1 Digital
Link Resolver Conformance Document (and aligned with IETF RFC 9264
"Linkset: Media Types and a Link Relation Type for Link Sets"). The same
data is serialised either as `application/linkset+json` (RFC 9264) or
`application/ld+json` (JSON-LD) on demand.

Two structural notes:

  1. Relation IRIs use the GS1 Web Vocabulary namespace
     (https://gs1.org/voc/...). Short forms like "gs1:pip" used in
     configuration are expanded to the full IRI in the response.

  2. Every link-set carries a default link (`https://gs1.org/voc/defaultLink`).
     If the operator has not declared one explicitly, the first declared
     link is promoted to default.
"""

from __future__ import annotations

from typing import Any

from .router import LinkType

GS1_VOC = "https://gs1.org/voc/"
GS1_VOC_PREFIX = "gs1:"

# Built-in short-form expansions for the most common link types
SHORT_TO_VOC: dict[str, str] = {
    "gs1:pip":                  GS1_VOC + "pip",
    "gs1:productInfo":          GS1_VOC + "productInfo",
    "gs1:defaultLink":          GS1_VOC + "defaultLink",
    "gs1:certificationInfo":    GS1_VOC + "certificationInfo",
    "gs1:epil":                 GS1_VOC + "epil",  # extended-packaging info link
    "gs1:hasRetailers":         GS1_VOC + "hasRetailers",
    "gs1:productSupportLink":   GS1_VOC + "productSupportLink",
    "gs1:recipeInfo":           GS1_VOC + "recipeInfo",
    "gs1:safetyDataSheet":      GS1_VOC + "safetyDataSheet",
    "gs1:safetyInfo":           GS1_VOC + "safetyInfo",
    "gs1:serviceInfo":          GS1_VOC + "serviceInfo",
    "gs1:smartLabel":           GS1_VOC + "smartLabel",
    "gs1:sustainabilityInfo":   GS1_VOC + "sustainabilityInfo",
    "gs1:traceability":         GS1_VOC + "traceability",
    "gs1:tutorial":             GS1_VOC + "tutorial",
    "gs1:verificationService":  GS1_VOC + "verificationService",
    # ESPR / DPP-specific (proposed extensions, used by CIRPASS-2 CoP)
    "gs1:digitalProductPassport": GS1_VOC + "digitalProductPassport",
}


def expand_rel(rel: str) -> str:
    """Expand short-form `gs1:foo` to the full GS1 Web Vocabulary IRI."""
    if rel.startswith("http://") or rel.startswith("https://"):
        return rel
    if rel in SHORT_TO_VOC:
        return SHORT_TO_VOC[rel]
    if rel.startswith(GS1_VOC_PREFIX):
        return GS1_VOC + rel[len(GS1_VOC_PREFIX):]
    return rel  # leave bare relation tokens (rfc8288 well-known names) alone


def build_linkset(
    *,
    anchor: str,
    links: list[LinkType],
    requested_link_type: str | None = None,
) -> dict[str, Any]:
    """
    Build an RFC 9264 link-set object for the resolver response.

    If `requested_link_type` is provided (via the `?linkType=` query parameter
    per GS1 DL §6.4), the link-set is filtered to that single relation if a
    matching link exists; otherwise all links are returned.
    """
    if not links:
        return {"linkset": [{"anchor": anchor}]}

    expanded: list[tuple[str, LinkType]] = [(expand_rel(lt.rel), lt) for lt in links]

    # Promote a default link if none is explicitly declared
    has_default = any(rel == SHORT_TO_VOC["gs1:defaultLink"] for rel, _ in expanded)
    if not has_default and expanded:
        first_rel, first_lt = expanded[0]
        expanded.append((SHORT_TO_VOC["gs1:defaultLink"], first_lt))

    # Apply linkType filter if requested
    if requested_link_type:
        wanted = expand_rel(requested_link_type)
        filtered = [(r, lt) for r, lt in expanded if r == wanted]
        if filtered:
            expanded = filtered

    grouped: dict[str, list[dict[str, Any]]] = {}
    for rel, lt in expanded:
        entry: dict[str, Any] = {"href": lt.href}
        if lt.type:
            entry["type"] = lt.type
        if lt.title:
            entry["title"] = lt.title
        if lt.hreflang:
            entry["hreflang"] = [lt.hreflang] if isinstance(lt.hreflang, str) else list(lt.hreflang)
        grouped.setdefault(rel, []).append(entry)

    return {
        "linkset": [
            {"anchor": anchor, **grouped}
        ]
    }


def build_jsonld(linkset: dict[str, Any]) -> dict[str, Any]:
    """
    Wrap an RFC 9264 link-set with a JSON-LD context for `application/ld+json`
    consumers. The context binds the GS1 vocabulary prefix so that the
    relation IRIs resolve correctly under JSON-LD processing.
    """
    return {
        "@context": [
            "https://www.w3.org/ns/linkset.jsonld",
            {"gs1": GS1_VOC},
        ],
        **linkset,
    }


def default_link_href(linkset: dict[str, Any]) -> str | None:
    """Extract the default link's href from a link-set, if present."""
    if not linkset.get("linkset"):
        return None
    entry = linkset["linkset"][0]
    default_rel = SHORT_TO_VOC["gs1:defaultLink"]
    links = entry.get(default_rel)
    if links and links[0].get("href"):
        return links[0]["href"]
    return None
