"""Tests for GS1 Digital Link URI parser."""

import pytest
from resolver.parser import parse, validate_gtin14


def test_parse_numeric_ai_gtin_serial():
    result = parse("/01/09780345418913/21/ABC123")
    assert result.primary_ai == "01"
    assert result.primary_value == "09780345418913"
    assert result.qualifiers["21"] == "ABC123"
    assert result.gtin == "09780345418913"
    assert result.serial_number == "ABC123"


def test_parse_alpha_coded():
    result = parse("/gtin/09780345418913/ser/ABC123")
    assert result.primary_ai == "01"
    assert result.primary_value == "09780345418913"
    assert result.serial_number == "ABC123"


def test_parse_with_expiry_and_batch():
    result = parse("/01/09780345418913/17/251231/10/BATCH01/21/SER001")
    assert result.expiry_date == "251231"
    assert result.batch_lot == "BATCH01"
    assert result.serial_number == "SER001"


def test_parse_full_uri():
    result = parse("https://resolver.example.com/01/09780345418913/21/ABC123?linkType=gs1:pip")
    assert result.gtin == "09780345418913"
    assert result.link_type == "gs1:pip"


def test_parse_no_ai_raises():
    with pytest.raises(ValueError):
        parse("/invalid/path")


def test_validate_gtin14_valid():
    assert validate_gtin14("09780345418913") is True


def test_validate_gtin14_wrong_check_digit():
    assert validate_gtin14("09780345418914") is False


def test_validate_gtin14_wrong_length():
    assert validate_gtin14("978034541891") is False


def test_validate_gtin14_non_numeric():
    assert validate_gtin14("0978034541891X") is False
