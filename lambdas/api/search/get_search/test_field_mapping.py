"""
Unit tests for field mapping function.

Tests the map_sort_field_to_opensearch_path function to ensure
frontend field names are correctly mapped to OpenSearch field paths.
"""

import pytest


def map_sort_field_to_opensearch_path(field_name: str) -> str:
    """
    Map frontend field names to OpenSearch field paths.

    This is a copy of the function for testing purposes.
    """
    field_mapping = {
        "createdAt": "DigitalSourceAsset.CreateDate",
        "name": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name.keyword",
        "size": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size",
        "type": "DigitalSourceAsset.Type.keyword",
        "format": "DigitalSourceAsset.MainRepresentation.Format.keyword",
    }

    # Return mapped field or original if already in OpenSearch format
    return field_mapping.get(field_name, field_name)


class TestFieldMapping:
    """Test suite for field mapping function"""

    def test_createdAt_maps_to_create_date(self):
        """Test that 'createdAt' maps to the correct OpenSearch field"""
        result = map_sort_field_to_opensearch_path("createdAt")
        assert result == "DigitalSourceAsset.CreateDate"

    def test_name_maps_to_keyword_field(self):
        """Test that 'name' maps to the keyword field for exact sorting"""
        result = map_sort_field_to_opensearch_path("name")
        assert (
            result
            == "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name.keyword"
        )

    def test_size_maps_to_numeric_field(self):
        """Test that 'size' maps to the numeric size field"""
        result = map_sort_field_to_opensearch_path("size")
        assert (
            result
            == "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size"
        )

    def test_type_maps_to_keyword_field(self):
        """Test that 'type' maps to the keyword type field"""
        result = map_sort_field_to_opensearch_path("type")
        assert result == "DigitalSourceAsset.Type.keyword"

    def test_format_maps_to_keyword_field(self):
        """Test that 'format' maps to the keyword format field"""
        result = map_sort_field_to_opensearch_path("format")
        assert result == "DigitalSourceAsset.MainRepresentation.Format.keyword"

    def test_opensearch_path_returned_as_is(self):
        """Test that an OpenSearch path is returned unchanged"""
        opensearch_path = "DigitalSourceAsset.CreateDate"
        result = map_sort_field_to_opensearch_path(opensearch_path)
        assert result == opensearch_path

    def test_unknown_field_returned_as_is(self):
        """Test that an unknown field name is returned unchanged"""
        unknown_field = "unknownField"
        result = map_sort_field_to_opensearch_path(unknown_field)
        assert result == unknown_field

    def test_all_frontend_fields_have_mappings(self):
        """Test that all expected frontend fields have mappings"""
        frontend_fields = ["createdAt", "name", "size", "type", "format"]

        for field in frontend_fields:
            result = map_sort_field_to_opensearch_path(field)
            # Verify that the result is different from the input (i.e., it was mapped)
            assert (
                result != field
            ), f"Field '{field}' should be mapped to an OpenSearch path"
            # Verify that the result starts with 'DigitalSourceAsset'
            assert result.startswith(
                "DigitalSourceAsset"
            ), f"Mapped field '{result}' should start with 'DigitalSourceAsset'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
