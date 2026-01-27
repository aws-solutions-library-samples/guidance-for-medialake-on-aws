"""
Unit tests for the identifier field mapper module.

These tests verify that:
- map_identifier() correctly creates AltIdentifier elements
- Empty/null values are skipped
- Identifier values are preserved without modification
- Namespace suffix logic works correctly (relative vs absolute namespaces)
- map_all_identifiers() uses configuration for all field names
"""

import pytest
from nodes.external_metadata_fetch.normalizers.field_mappers.map_identifiers import (
    map_all_identifiers,
    map_identifier,
    resolve_namespace,
)
from nodes.external_metadata_fetch.normalizers.mec_schema import AltIdentifier


@pytest.mark.unit
class TestMapIdentifier:
    """Tests for map_identifier function"""

    def test_creates_alt_identifier_with_valid_value(self):
        """Creates AltIdentifier with valid value and namespace."""
        result = map_identifier("RLA236635", "CUSTOMER")

        assert result is not None
        assert isinstance(result, AltIdentifier)
        assert result.namespace == "CUSTOMER"
        assert result.identifier == "RLA236635"

    def test_returns_none_for_none_value(self):
        """Returns None when value is None."""
        result = map_identifier(None, "CUSTOMER")

        assert result is None

    def test_returns_none_for_empty_string(self):
        """Returns None when value is empty string."""
        result = map_identifier("", "CUSTOMER")

        assert result is None

    def test_returns_none_for_whitespace_only(self):
        """Returns None when value is whitespace only."""
        result = map_identifier("   ", "CUSTOMER")

        assert result is None

    def test_preserves_identifier_format(self):
        """Preserves original identifier format without modification."""
        # Test various identifier formats
        test_cases = [
            ("RLA236635", "RLA236635"),
            ("EP043931170004", "EP043931170004"),
            ("L01039285", "L01039285"),
            ("SH043931170000", "SH043931170000"),
            ("RLA236635.3", "RLA236635.3"),
            ("30236635", "30236635"),
        ]

        for input_value, expected_value in test_cases:
            result = map_identifier(input_value, "TEST")
            assert result is not None
            assert result.identifier == expected_value

    def test_strips_whitespace_from_value(self):
        """Strips leading/trailing whitespace from value."""
        result = map_identifier("  RLA236635  ", "CUSTOMER")

        assert result is not None
        assert result.identifier == "RLA236635"

    def test_handles_numeric_values(self):
        """Handles numeric values by converting to string."""
        # Note: map_identifier expects string, but should handle edge cases
        result = map_identifier("12345", "CUSTOMER")

        assert result is not None
        assert result.identifier == "12345"


@pytest.mark.unit
class TestResolveNamespace:
    """Tests for resolve_namespace function"""

    def test_relative_namespace_with_dash_prefix(self):
        """Relative namespace (starts with -) appends to prefix."""
        result = resolve_namespace("-REF", "CUSTOMER")

        assert result == "CUSTOMER-REF"

    def test_relative_namespace_version(self):
        """Relative namespace for version suffix."""
        result = resolve_namespace("-VERSION", "CUSTOMER")

        assert result == "CUSTOMER-VERSION"

    def test_relative_namespace_seq(self):
        """Relative namespace for sequence suffix."""
        result = resolve_namespace("-SEQ", "CUSTOMER")

        assert result == "CUSTOMER-SEQ"

    def test_empty_suffix_uses_prefix_directly(self):
        """Empty suffix uses source prefix directly."""
        result = resolve_namespace("", "CUSTOMER")

        assert result == "CUSTOMER"

    def test_absolute_namespace_tms(self):
        """Absolute namespace (no dash) used as-is."""
        result = resolve_namespace("TMS", "CUSTOMER")

        assert result == "TMS"

    def test_absolute_namespace_other(self):
        """Other absolute namespaces used as-is."""
        result = resolve_namespace("GRACENOTE", "CUSTOMER")

        assert result == "GRACENOTE"

    def test_different_source_prefixes(self):
        """Works with different source namespace prefixes."""
        test_cases = [
            ("ACME", "-REF", "ACME-REF"),
            ("CUSTOMER", "-REF", "CUSTOMER-REF"),
            ("MEDIA", "", "MEDIA"),
            ("STUDIO", "-VERSION", "STUDIO-VERSION"),
        ]

        for prefix, suffix, expected in test_cases:
            result = resolve_namespace(suffix, prefix)
            assert result == expected


@pytest.mark.unit
class TestMapAllIdentifiers:
    """Tests for map_all_identifiers function"""

    def test_maps_all_configured_identifiers(self):
        """Maps all identifiers defined in configuration."""
        raw_metadata = {
            "primary_id": "RLA236635",
            "ref_id": "L01039285",
            "version_id": "RLA236635.3",
        }
        config = {
            "source_namespace_prefix": "CUSTOMER",
            "identifier_mappings": {
                "primary_id": "",
                "ref_id": "-REF",
                "version_id": "-VERSION",
            },
        }

        result = map_all_identifiers(raw_metadata, config)

        assert len(result) == 3

        # Check each identifier
        namespaces = {r.namespace: r.identifier for r in result}
        assert namespaces["CUSTOMER"] == "RLA236635"
        assert namespaces["CUSTOMER-REF"] == "L01039285"
        assert namespaces["CUSTOMER-VERSION"] == "RLA236635.3"

    def test_skips_empty_values(self):
        """Skips fields with empty values."""
        raw_metadata = {
            "primary_id": "RLA236635",
            "ref_id": "",
            "version_id": None,
        }
        config = {
            "source_namespace_prefix": "CUSTOMER",
            "identifier_mappings": {
                "primary_id": "",
                "ref_id": "-REF",
                "version_id": "-VERSION",
            },
        }

        result = map_all_identifiers(raw_metadata, config)

        assert len(result) == 1
        assert result[0].namespace == "CUSTOMER"
        assert result[0].identifier == "RLA236635"

    def test_skips_missing_fields(self):
        """Skips fields not present in raw metadata."""
        raw_metadata = {
            "primary_id": "RLA236635",
            # ref_id and version_id are missing
        }
        config = {
            "source_namespace_prefix": "CUSTOMER",
            "identifier_mappings": {
                "primary_id": "",
                "ref_id": "-REF",
                "version_id": "-VERSION",
            },
        }

        result = map_all_identifiers(raw_metadata, config)

        assert len(result) == 1
        assert result[0].identifier == "RLA236635"

    def test_handles_absolute_namespaces(self):
        """Handles absolute namespaces like TMS."""
        raw_metadata = {
            "primary_id": "RLA236635",
            "tms_series_id": "SH043931170000",
            "tms_episode_id": "EP043931170004",
        }
        config = {
            "source_namespace_prefix": "CUSTOMER",
            "identifier_mappings": {
                "primary_id": "",
                "tms_series_id": "TMS",
                "tms_episode_id": "TMS",
            },
        }

        result = map_all_identifiers(raw_metadata, config)

        assert len(result) == 3

        # Check TMS identifiers
        tms_ids = [r for r in result if r.namespace == "TMS"]
        assert len(tms_ids) == 2
        tms_values = {r.identifier for r in tms_ids}
        assert "SH043931170000" in tms_values
        assert "EP043931170004" in tms_values

    def test_uses_default_prefix_when_not_configured(self):
        """Uses 'SOURCE' as default prefix when not configured."""
        raw_metadata = {"primary_id": "RLA236635"}
        config = {
            "identifier_mappings": {
                "primary_id": "",
            },
        }

        result = map_all_identifiers(raw_metadata, config)

        assert len(result) == 1
        assert result[0].namespace == "SOURCE"

    def test_returns_empty_list_when_no_mappings(self):
        """Returns empty list when no identifier mappings configured."""
        raw_metadata = {"primary_id": "RLA236635"}
        config = {
            "source_namespace_prefix": "CUSTOMER",
            "identifier_mappings": {},
        }

        result = map_all_identifiers(raw_metadata, config)

        assert result == []

    def test_returns_empty_list_when_no_config(self):
        """Returns empty list when config is empty."""
        raw_metadata = {"primary_id": "RLA236635"}
        config = {}

        result = map_all_identifiers(raw_metadata, config)

        assert result == []

    def test_preserves_identifier_values_without_modification(self):
        """Preserves identifier values exactly as provided."""
        raw_metadata = {
            "id_with_dots": "RLA236635.3",
            "id_with_numbers": "30236635",
            "id_with_prefix": "EP043931170004",
        }
        config = {
            "source_namespace_prefix": "TEST",
            "identifier_mappings": {
                "id_with_dots": "-DOT",
                "id_with_numbers": "-NUM",
                "id_with_prefix": "-PRE",
            },
        }

        result = map_all_identifiers(raw_metadata, config)

        values = {r.identifier for r in result}
        assert "RLA236635.3" in values
        assert "30236635" in values
        assert "EP043931170004" in values

    def test_handles_whitespace_in_values(self):
        """Strips whitespace from identifier values."""
        raw_metadata = {
            "primary_id": "  RLA236635  ",
            "ref_id": "\tL01039285\n",
        }
        config = {
            "source_namespace_prefix": "CUSTOMER",
            "identifier_mappings": {
                "primary_id": "",
                "ref_id": "-REF",
            },
        }

        result = map_all_identifiers(raw_metadata, config)

        assert len(result) == 2
        values = {r.identifier for r in result}
        assert "RLA236635" in values
        assert "L01039285" in values

    def test_handles_numeric_field_values(self):
        """Handles numeric values by converting to string."""
        raw_metadata = {
            "sequence_id": 30236635,  # Integer value
        }
        config = {
            "source_namespace_prefix": "CUSTOMER",
            "identifier_mappings": {
                "sequence_id": "-SEQ",
            },
        }

        result = map_all_identifiers(raw_metadata, config)

        assert len(result) == 1
        assert result[0].identifier == "30236635"

    def test_comprehensive_config_example(self):
        """Tests with comprehensive configuration matching generic sample."""
        raw_metadata = {
            "customer_id": "RLA236635",
            "refid": "L01039285",
            "version_id": "RLA236635.3",
            "id_sequence": "30236635",
            "tms_series_id": "SH043931170000",
            "tms_episode_id": "EP043931170004",
            "tms_movie_id": "",  # Empty - should be skipped
            "ad_content_id": "L01039285",
        }
        config = {
            "source_namespace_prefix": "CUSTOMER",
            "identifier_mappings": {
                "customer_id": "",
                "refid": "-REF",
                "version_id": "-VERSION",
                "id_sequence": "-SEQ",
                "tms_series_id": "TMS",
                "tms_episode_id": "TMS",
                "tms_movie_id": "TMS",
                "ad_content_id": "-AD",
            },
        }

        result = map_all_identifiers(raw_metadata, config)

        # Should have 7 identifiers (tms_movie_id is empty)
        assert len(result) == 7

        # Verify namespaces
        namespaces = {r.namespace for r in result}
        assert "CUSTOMER" in namespaces
        assert "CUSTOMER-REF" in namespaces
        assert "CUSTOMER-VERSION" in namespaces
        assert "CUSTOMER-SEQ" in namespaces
        assert "TMS" in namespaces
        assert "CUSTOMER-AD" in namespaces

    def test_to_dict_serialization(self):
        """Verifies AltIdentifier to_dict works correctly."""
        raw_metadata = {"primary_id": "RLA236635"}
        config = {
            "source_namespace_prefix": "CUSTOMER",
            "identifier_mappings": {"primary_id": ""},
        }

        result = map_all_identifiers(raw_metadata, config)

        assert len(result) == 1
        dict_result = result[0].to_dict()
        assert dict_result == {
            "Namespace": "CUSTOMER",
            "Identifier": "RLA236635",
        }
