"""
Unit tests for specific sort field mappings in the query builder.

These tests verify that frontend-friendly field names are correctly mapped
to OpenSearch field paths for sorting.

**Feature: assets-page-bugs, Task 2.4**
**Validates: Requirements 9.3, 9.4, 9.5, 9.6**
"""

import pytest

from lambdas.api.search.get_search.index import map_sort_field_to_opensearch_path


@pytest.mark.unit
class TestSortFieldMappings:
    """Unit tests for sort field name to OpenSearch path mappings."""

    def test_created_at_maps_to_create_date_field(self):
        """
        Test that "createdAt" maps to the correct OpenSearch CreateDate field.

        **Validates: Requirement 9.4**

        The frontend uses "createdAt" as a user-friendly field name, which
        should map to the OpenSearch date field for sorting by creation date.
        """
        # Act
        opensearch_field = map_sort_field_to_opensearch_path("createdAt")

        # Assert
        assert (
            opensearch_field == "DigitalSourceAsset.CreateDate"
        ), "createdAt should map to DigitalSourceAsset.CreateDate"

    def test_name_maps_to_keyword_field(self):
        """
        Test that "name" maps to the keyword field for exact sorting.

        **Validates: Requirement 9.3**

        The frontend uses "name" for sorting by asset name. This should map
        to the keyword version of the ObjectKey.Name field to ensure proper
        alphabetical sorting (keyword fields are not analyzed).
        """
        # Act
        opensearch_field = map_sort_field_to_opensearch_path("name")

        # Assert
        expected_field = "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name.keyword"
        assert (
            opensearch_field == expected_field
        ), f"name should map to keyword field: {expected_field}"

    def test_size_maps_to_numeric_field(self):
        """
        Test that "size" maps to the numeric FileInfo.Size field.

        **Validates: Requirement 9.5**

        The frontend uses "size" for sorting by file size. This should map
        to the numeric Size field to enable proper numeric sorting.
        """
        # Act
        opensearch_field = map_sort_field_to_opensearch_path("size")

        # Assert
        expected_field = "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size"
        assert (
            opensearch_field == expected_field
        ), f"size should map to numeric Size field: {expected_field}"

    def test_type_maps_to_keyword_field(self):
        """
        Test that "type" maps to the keyword Type field.

        **Validates: Requirement 9.6**

        The frontend uses "type" for sorting by asset type. This should map
        to the keyword version of the Type field for exact matching and sorting.
        """
        # Act
        opensearch_field = map_sort_field_to_opensearch_path("type")

        # Assert
        expected_field = "DigitalSourceAsset.Type.keyword"
        assert (
            opensearch_field == expected_field
        ), f"type should map to keyword Type field: {expected_field}"

    def test_format_maps_to_keyword_field(self):
        """
        Test that "format" maps to the keyword Format field.

        **Validates: Requirement 9.6**

        The frontend uses "format" for sorting by file format. This should map
        to the keyword version of the Format field.
        """
        # Act
        opensearch_field = map_sort_field_to_opensearch_path("format")

        # Assert
        expected_field = "DigitalSourceAsset.MainRepresentation.Format.keyword"
        assert (
            opensearch_field == expected_field
        ), f"format should map to keyword Format field: {expected_field}"

    def test_opensearch_field_path_returns_unchanged(self):
        """
        Test that OpenSearch field paths are returned unchanged.

        When a field name is already in OpenSearch format (contains dots and
        matches a known path), it should be returned as-is without mapping.
        """
        # Arrange
        opensearch_path = "DigitalSourceAsset.CreateDate"

        # Act
        result = map_sort_field_to_opensearch_path(opensearch_path)

        # Assert
        assert (
            result == opensearch_path
        ), "OpenSearch field paths should be returned unchanged"

    def test_all_frontend_fields_have_mappings(self):
        """
        Test that all frontend-friendly field names have valid mappings.

        This ensures completeness of the field mapping function.
        """
        # Arrange
        frontend_fields = ["createdAt", "name", "size", "type", "format"]

        # Act & Assert
        for field in frontend_fields:
            opensearch_field = map_sort_field_to_opensearch_path(field)
            assert (
                opensearch_field is not None
            ), f"Field '{field}' should have a mapping"
            assert (
                "DigitalSourceAsset" in opensearch_field
            ), f"Mapped field '{opensearch_field}' should be in DigitalSourceAsset namespace"

    def test_keyword_fields_use_keyword_suffix(self):
        """
        Test that text fields use .keyword suffix for exact sorting.

        Text fields that need exact sorting (name, type, format) should use
        the .keyword suffix to avoid analyzed text sorting issues.
        """
        # Arrange
        text_fields = ["name", "type", "format"]

        # Act & Assert
        for field in text_fields:
            opensearch_field = map_sort_field_to_opensearch_path(field)
            assert opensearch_field.endswith(
                ".keyword"
            ), f"Text field '{field}' should map to a .keyword field for exact sorting"

    def test_numeric_and_date_fields_no_keyword_suffix(self):
        """
        Test that numeric and date fields do not use .keyword suffix.

        Numeric and date fields should not have the .keyword suffix as they
        are already stored in a sortable format.
        """
        # Arrange
        non_text_fields = {
            "createdAt": "DigitalSourceAsset.CreateDate",
            "size": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size",
        }

        # Act & Assert
        for field, expected_path in non_text_fields.items():
            opensearch_field = map_sort_field_to_opensearch_path(field)
            assert not opensearch_field.endswith(
                ".keyword"
            ), f"Non-text field '{field}' should not have .keyword suffix"
            assert (
                opensearch_field == expected_path
            ), f"Field '{field}' should map to '{expected_path}'"

    def test_unknown_field_returns_original(self):
        """
        Test that unknown field names are returned unchanged.

        If a field name is not in the mapping dictionary and not a known
        OpenSearch path, it should be returned as-is (validation will catch
        invalid fields separately).
        """
        # Arrange
        unknown_field = "unknownField"

        # Act
        result = map_sort_field_to_opensearch_path(unknown_field)

        # Assert
        assert (
            result == unknown_field
        ), "Unknown field names should be returned unchanged"
