"""
ai_table.py — GS1 Application Identifier table for GS1 Digital Link

Source: GS1 General Specifications + GS1 Digital Link Standard v1.2 (Table 4.4
"Permitted Application Identifiers in GS1 Digital Link URIs", and Table 4.6
"Convenience alphanumeric short names for AIs").

Only AIs that are valid in a GS1 Digital Link URI are listed here. AIs that
GS1 General Specifications define but explicitly forbid in a DL URI (e.g. AI 02
when not in a logistic-unit context) are intentionally omitted.

Three categories matter to a resolver:

  PRIMARY  — the routing key (one per URI). e.g. 01 (GTIN), 8003 (GRAI), 414 (GLN).
  QUALIFIER — refines the primary key (zero or more per URI, in a fixed order
              that depends on the primary). e.g. 22 (CPV), 10 (lot), 21 (serial).
  ATTRIBUTE — additional product/lot data, never used for routing but carried in
              the URI. e.g. 17 (expiry), 7003 (expiry-time), 4321 (dangerous-goods).
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple


class AICategory(Enum):
    PRIMARY = "primary"
    QUALIFIER = "qualifier"
    ATTRIBUTE = "attribute"


class AISpec(NamedTuple):
    ai: str            # numeric AI, e.g. "01"
    name: str          # canonical short name, e.g. "gtin"
    title: str         # human-readable title
    category: AICategory
    fixed_length: int | None = None  # None = variable length


# --- Primary keys (GS1 DL §4.4) ---------------------------------------------
PRIMARIES: list[AISpec] = [
    AISpec("00",   "sscc",         "Serial Shipping Container Code", AICategory.PRIMARY, 18),
    AISpec("01",   "gtin",         "Global Trade Item Number",        AICategory.PRIMARY, 14),
    AISpec("253",  "gdti",         "Global Document Type Identifier", AICategory.PRIMARY),
    AISpec("255",  "gcn",          "Global Coupon Number",            AICategory.PRIMARY),
    AISpec("401",  "ginc",         "Global Identification Number for Consignment", AICategory.PRIMARY),
    AISpec("402",  "gsin",         "Global Shipment Identification Number", AICategory.PRIMARY, 17),
    AISpec("414",  "gln",          "Global Location Number",          AICategory.PRIMARY, 13),
    AISpec("417",  "party",        "Party GLN",                       AICategory.PRIMARY, 13),
    AISpec("8003", "grai",         "Global Returnable Asset Identifier", AICategory.PRIMARY),
    AISpec("8004", "giai",         "Global Individual Asset Identifier",  AICategory.PRIMARY),
    AISpec("8006", "itip",         "Individual Trade Item Piece",     AICategory.PRIMARY, 18),
    AISpec("8010", "cpid",         "Component / Part Identifier",     AICategory.PRIMARY),
    AISpec("8013", "gmn",          "Global Model Number",             AICategory.PRIMARY),
    AISpec("8017", "gsrnp",        "GSRN — provider",                 AICategory.PRIMARY, 18),
    AISpec("8018", "gsrn",         "GSRN — recipient",                AICategory.PRIMARY, 18),
]

# --- Qualifiers (GS1 DL §4.4) -----------------------------------------------
# Per the standard, the order in the URI must follow the qualifier order
# defined for the primary key. We don't enforce ordering at parse time
# (the parser accepts any order and records all qualifiers); ordering matters
# for *canonical* URI generation, handled in canonicalise().
QUALIFIERS: list[AISpec] = [
    AISpec("22",   "cpv",          "Consumer Product Variant",        AICategory.QUALIFIER),
    AISpec("10",   "lot",          "Batch / Lot",                     AICategory.QUALIFIER),
    AISpec("21",   "ser",          "Serial Number",                   AICategory.QUALIFIER),
    AISpec("235",  "tpx",          "Third-Party Controlled Serial",   AICategory.QUALIFIER),
    AISpec("254",  "glnx",         "GLN Extension",                   AICategory.QUALIFIER),
    AISpec("8011", "cpsn",         "CPID Serial Number",              AICategory.QUALIFIER),
]

# --- Data attributes (carried, not routed on) -------------------------------
ATTRIBUTES: list[AISpec] = [
    AISpec("17",   "exp",          "Expiry / Best-Before Date",       AICategory.ATTRIBUTE, 6),
    AISpec("11",   "prodt",        "Production Date",                 AICategory.ATTRIBUTE, 6),
    AISpec("12",   "duedt",        "Due Date",                        AICategory.ATTRIBUTE, 6),
    AISpec("13",   "packdt",       "Packaging Date",                  AICategory.ATTRIBUTE, 6),
    AISpec("15",   "bestdt",       "Best-Before Date",                AICategory.ATTRIBUTE, 6),
    AISpec("16",   "selldt",       "Sell-By Date",                    AICategory.ATTRIBUTE, 6),
    AISpec("240",  "addid",        "Additional Item ID",              AICategory.ATTRIBUTE),
    AISpec("241",  "cuno",         "Customer Part Number",            AICategory.ATTRIBUTE),
    AISpec("242",  "mtono",        "Made-to-Order Variation",         AICategory.ATTRIBUTE),
    AISpec("243",  "pcn",          "Packaging Component Number",      AICategory.ATTRIBUTE),
    AISpec("250",  "secondaryser", "Secondary Serial Number",         AICategory.ATTRIBUTE),
    AISpec("251",  "refno",        "Reference to Source Entity",      AICategory.ATTRIBUTE),
    AISpec("400",  "orderno",      "Customer Purchase Order Number",  AICategory.ATTRIBUTE),
    AISpec("403",  "routing",      "Routing Code",                    AICategory.ATTRIBUTE),
    AISpec("4300", "shipto_name",  "Ship-To Name",                    AICategory.ATTRIBUTE),
    AISpec("4321", "dangerousgoods", "Dangerous-Goods Flag",          AICategory.ATTRIBUTE, 1),
    AISpec("710",  "nhrn_de",      "National Healthcare RN — Germany",   AICategory.ATTRIBUTE),
    AISpec("711",  "nhrn_fr",      "National Healthcare RN — France",    AICategory.ATTRIBUTE),
    AISpec("712",  "nhrn_es",      "National Healthcare RN — Spain",     AICategory.ATTRIBUTE),
    AISpec("713",  "nhrn_br",      "National Healthcare RN — Brazil",    AICategory.ATTRIBUTE),
    AISpec("714",  "nhrn_pt",      "National Healthcare RN — Portugal",  AICategory.ATTRIBUTE),
    AISpec("715",  "nhrn_us",      "National Healthcare RN — USA NDC",   AICategory.ATTRIBUTE),
    AISpec("723",  "certref",      "Certification Reference",         AICategory.ATTRIBUTE),
    AISpec("7003", "expt",         "Expiry Date and Time",            AICategory.ATTRIBUTE, 10),
    AISpec("7020", "refurblot",    "Refurbishment Lot ID",            AICategory.ATTRIBUTE),
    AISpec("7021", "funclot",      "Functional Status Lot ID",        AICategory.ATTRIBUTE),
    AISpec("7022", "revlot",       "Revision Status Lot ID",          AICategory.ATTRIBUTE),
    AISpec("7040", "uic_ext",      "GS1 UIC with Extension",          AICategory.ATTRIBUTE, 4),
    AISpec("8001", "rolls",        "Roll Products dimensions",        AICategory.ATTRIBUTE, 14),
    AISpec("8002", "cmid",         "Cellular Mobile Telephone ID",    AICategory.ATTRIBUTE),
    AISpec("8005", "price",        "Price Per Unit of Measure",       AICategory.ATTRIBUTE, 6),
    AISpec("8007", "iban",         "IBAN",                            AICategory.ATTRIBUTE),
    AISpec("8008", "prodtime",     "Production Date & Time",          AICategory.ATTRIBUTE),
    AISpec("8019", "srin",         "Service Relation Instance Number", AICategory.ATTRIBUTE),
    AISpec("8020", "refno_pay",    "Payment Slip Reference Number",   AICategory.ATTRIBUTE),
    AISpec("8110", "couponcode_us","US Coupon Code",                  AICategory.ATTRIBUTE),
    AISpec("8200", "producturl",   "Extended Packaging Product URL",  AICategory.ATTRIBUTE),
    AISpec("90",   "internal",     "Internal — Mutually Agreed",      AICategory.ATTRIBUTE),
]

# Convenience indexes ---------------------------------------------------------
ALL_AIS: list[AISpec] = PRIMARIES + QUALIFIERS + ATTRIBUTES

AI_TO_SPEC: dict[str, AISpec] = {a.ai: a for a in ALL_AIS}
NAME_TO_AI: dict[str, str] = {a.name: a.ai for a in ALL_AIS}
AI_TO_NAME: dict[str, str] = {a.ai: a.name for a in ALL_AIS}

PRIMARY_AIS: set[str] = {a.ai for a in PRIMARIES}
QUALIFIER_AIS: set[str] = {a.ai for a in QUALIFIERS}
ATTRIBUTE_AIS: set[str] = {a.ai for a in ATTRIBUTES}


# --- Qualifier ordering per primary key (GS1 DL §4.4) -----------------------
# Used for canonical URI generation. Unordered qualifiers are appended after
# the ordered ones in numeric AI sort order.
QUALIFIER_ORDER: dict[str, tuple[str, ...]] = {
    "01":   ("22", "10", "21"),     # GTIN: cpv → lot → ser
    "8006": ("22", "10", "21"),     # ITIP: same as GTIN
    "414":  ("254",),               # GLN: glnx
    "8003": ("21",),                # GRAI: ser
    "8010": ("8011",),              # CPID: cpsn
    "417":  ("254",),               # Party GLN: glnx
}


def category_of(ai: str) -> AICategory | None:
    spec = AI_TO_SPEC.get(ai)
    return spec.category if spec else None


def is_known(ai: str) -> bool:
    return ai in AI_TO_SPEC


def fixed_length(ai: str) -> int | None:
    spec = AI_TO_SPEC.get(ai)
    return spec.fixed_length if spec else None
