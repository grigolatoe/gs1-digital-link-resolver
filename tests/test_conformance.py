"""
GS1 Digital Link conformance vectors.

Each test reflects a specific clause of the GS1 Digital Link standard v1.2
or the GS1 General Specifications. Where a worked example appears in the
standard text, we use the same example values verbatim so a reviewer can
trace each assertion back to a published source.
"""

from __future__ import annotations

import pytest

from resolver.parser import (
    GS1ParseResult,
    canonicalise,
    pad_gtin_to_14,
    parse,
    validate_gtin14,
)


# --- §4.4 — primary key + qualifier ordering --------------------------------

class TestPrimaryAndQualifiers:
    def test_gtin_only(self):
        r = parse("/01/09780345418913")
        assert r.primary_ai == "01"
        assert r.gtin == "09780345418913"
        assert r.qualifiers == {}

    def test_gtin_with_serial(self):
        r = parse("/01/09780345418913/21/ABC123")
        assert r.primary_value == "09780345418913"
        assert r.qualifiers == {"21": "ABC123"}

    def test_gtin_full_qualifier_chain_in_canonical_order(self):
        r = parse("/01/09780345418913/22/V2/10/LOT01/21/SER001")
        assert r.qualifiers == {"22": "V2", "10": "LOT01", "21": "SER001"}

    def test_gtin_qualifier_chain_out_of_order_is_accepted(self):
        # Per GS1 DL §4.4 the standard *prefers* canonical order but the
        # parser must accept any permutation; canonicalisation re-sorts.
        r = parse("/01/09780345418913/21/SER/10/LOT/22/V2")
        assert r.qualifiers == {"22": "V2", "10": "LOT", "21": "SER"}

    def test_grai_primary(self):
        r = parse("/8003/095555550000200")
        assert r.primary_ai == "8003"
        assert r.primary_value == "095555550000200"

    def test_gln_with_extension(self):
        r = parse("/414/9520123456788/254/EXT-A")
        assert r.primary_ai == "414"
        assert r.qualifiers == {"254": "EXT-A"}

    def test_no_primary_key_raises(self):
        # 17 (expiry) is an attribute, not a primary — must refuse
        with pytest.raises(ValueError):
            parse("/17/251231")


# --- §4.5 — alpha-coded forms -----------------------------------------------

class TestAlphaCoded:
    def test_basic_alpha_form(self):
        r = parse("/gtin/09780345418913/ser/ABC123")
        assert r.primary_ai == "01"
        assert r.qualifiers["21"] == "ABC123"

    def test_alpha_is_case_insensitive(self):
        r = parse("/GTIN/09780345418913/SER/ABC123")
        assert r.gtin == "09780345418913"
        assert r.serial_number == "ABC123"

    def test_alpha_lot_and_cpv(self):
        r = parse("/gtin/09780345418913/cpv/V2/lot/LOT01/ser/SER")
        assert r.qualifiers == {"22": "V2", "10": "LOT01", "21": "SER"}

    def test_alpha_certref_does_not_collide_with_short_prefix(self):
        # 'certref' must win over a hypothetical 'cert' — long names sort first
        r = parse("/gtin/09780345418913/certref/ISO9001")
        assert r.attributes.get("723") == "ISO9001"


# --- §4.6 — canonical URI generation ----------------------------------------

class TestCanonical:
    def test_canonical_orders_qualifiers_for_gtin(self):
        r = parse("/01/09780345418913/21/SER/10/LOT/22/V2")
        canonical = canonicalise(r)
        assert canonical == "https://id.gs1.org/01/09780345418913/22/V2/10/LOT/21/SER"

    def test_canonical_strips_query_string(self):
        r = parse("/01/09780345418913?linkType=gs1:pip")
        canonical = canonicalise(r)
        assert canonical == "https://id.gs1.org/01/09780345418913"

    def test_canonical_appends_attributes_after_qualifiers(self):
        r = parse("/01/09780345418913/21/SER/17/251231")
        canonical = canonicalise(r)
        # attributes (17) come after qualifiers (21)
        assert canonical == "https://id.gs1.org/01/09780345418913/21/SER/17/251231"

    def test_canonical_uses_alternate_host(self):
        r = parse("/01/09780345418913")
        assert canonicalise(r, host="dpp.example.com").startswith("https://dpp.example.com/01/")


# --- GTIN-14 mod-10 check digit (GS1 General Specs §7.9) --------------------

class TestGtin14:
    @pytest.mark.parametrize("gtin", [
        "09780345418913",  # ISBN form
        "00012345678905",  # GTIN-12 padded
        "09506000134369",  # GS1-published example
        "00614141999996",  # GS1-published example
    ])
    def test_valid_gtin14_examples(self, gtin):
        assert validate_gtin14(gtin) is True

    def test_wrong_check_digit(self):
        assert validate_gtin14("09780345418914") is False

    def test_wrong_length(self):
        for bad in ("978034541891", "0978034541891", "097803454189130"):
            assert validate_gtin14(bad) is False

    def test_non_numeric(self):
        assert validate_gtin14("0978034541891X") is False

    def test_pad_gtin13_to_14(self):
        assert pad_gtin_to_14("9780345418913") == "09780345418913"

    def test_pad_idempotent(self):
        assert pad_gtin_to_14("09780345418913") == "09780345418913"


# --- Resolver-side malformed-input refusals ---------------------------------

class TestMalformedInput:
    def test_empty_path_raises(self):
        with pytest.raises(ValueError):
            parse("/")

    def test_unknown_ai_does_not_raise_but_is_recorded(self):
        # AI 9999 isn't in the table; we don't refuse the whole URI but
        # we do record the segment so a caller can decide whether to 400.
        r = parse("/01/09780345418913/9999/SOMETHING")
        assert r.gtin == "09780345418913"
        assert ("9999", "SOMETHING") in r.unknown_ais

    def test_ai_value_with_url_unsafe_chars_is_url_encoded_in_canonical(self):
        r = GS1ParseResult(primary_ai="01", primary_value="09780345418913")
        r.qualifiers["21"] = "AB/CD"  # contains a slash
        canonical = canonicalise(r)
        assert "AB%2FCD" in canonical


# --- Worked example from GS1 DL standard §A.1 -------------------------------

def test_gs1_dl_worked_example():
    """
    The GS1 Digital Link standard §A.1 walks through this URI:
        https://example.com/01/09506000134369/10/ABC123/21/12345?linkType=gs1:pip
    The test asserts that we agree on every parsed component.
    """
    uri = "https://example.com/01/09506000134369/10/ABC123/21/12345?linkType=gs1:pip"
    r = parse(uri)

    assert r.primary_ai == "01"
    assert r.primary_value == "09506000134369"
    assert r.qualifiers == {"10": "ABC123", "21": "12345"}
    assert r.link_type == "gs1:pip"
    assert validate_gtin14(r.gtin)
    assert canonicalise(r) == "https://id.gs1.org/01/09506000134369/10/ABC123/21/12345"
