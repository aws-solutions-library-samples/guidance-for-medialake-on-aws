"""
Unit tests for the placeholder MetadataNormalizer.

These tests verify that the placeholder normalizer correctly:
- Stores raw metadata in custom_fields
- Extracts basic fields (title, description) if present
- Always populates source_attribution
"""

from datetime import datetime

import pytest

# Import from nodes (pytest.ini adds lambdas/ to pythonpath)
from nodes.external_metadata_fetch.normalizer import (
    MetadataNormalizer,
    NormalizedMetadata,
    SourceAttribution,
)


@pytest.mark.unit
class TestSourceAttribution:
    """Tests for SourceAttribution dataclass"""

    def test_to_dict_all_fields(self):
        """Returns dict with all fields when source_record_id is present."""
        # Arrange
        attribution = SourceAttribution(
            source_system="generic_rest_api:oauth2",
            fetch_timestamp="2024-01-15T10:30:00+00:00",
            correlation_id="ABC123",
            source_record_id="ext-12345",
        )

        # Act
        result = attribution.to_dict()

        # Assert
        assert result == {
            "source_system": "generic_rest_api:oauth2",
            "fetch_timestamp": "2024-01-15T10:30:00+00:00",
            "correlation_id": "ABC123",
            "source_record_id": "ext-12345",
        }

    def test_to_dict_without_source_record_id(self):
        """Returns dict without source_record_id when it's None."""
        # Arrange
        attribution = SourceAttribution(
            source_system="api_key_adapter",
            fetch_timestamp="2024-01-15T10:30:00+00:00",
            correlation_id="DEF456",
            source_record_id=None,
        )

        # Act
        result = attribution.to_dict()

        # Assert
        assert result == {
            "source_system": "api_key_adapter",
            "fetch_timestamp": "2024-01-15T10:30:00+00:00",
            "correlation_id": "DEF456",
        }
        assert "source_record_id" not in result


@pytest.mark.unit
class TestNormalizedMetadata:
    """Tests for NormalizedMetadata dataclass"""

    def test_to_dict_all_fields(self):
        """Returns dict with all populated fields."""
        # Arrange
        attribution = SourceAttribution(
            source_system="test_system",
            fetch_timestamp="2024-01-15T10:30:00+00:00",
            correlation_id="TEST123",
        )
        metadata = NormalizedMetadata(
            title="Test Title",
            description="Test Description",
            custom_fields={"extra": "value"},
            source_attribution=attribution,
        )

        # Act
        result = metadata.to_dict()

        # Assert
        assert result["title"] == "Test Title"
        assert result["description"] == "Test Description"
        assert result["custom_fields"] == {"extra": "value"}
        assert result["source_attribution"]["source_system"] == "test_system"

    def test_to_dict_excludes_none_values(self):
        """Excludes None values from dict output."""
        # Arrange
        attribution = SourceAttribution(
            source_system="test_system",
            fetch_timestamp="2024-01-15T10:30:00+00:00",
            correlation_id="TEST123",
        )
        metadata = NormalizedMetadata(
            title=None,
            description="Only description",
            custom_fields={},
            source_attribution=attribution,
        )

        # Act
        result = metadata.to_dict()

        # Assert
        assert "title" not in result
        assert result["description"] == "Only description"
        assert "custom_fields" not in result  # Empty dict excluded

    def test_to_dict_empty_metadata(self):
        """Returns minimal dict when only source_attribution is set."""
        # Arrange
        attribution = SourceAttribution(
            source_system="test_system",
            fetch_timestamp="2024-01-15T10:30:00+00:00",
            correlation_id="TEST123",
        )
        metadata = NormalizedMetadata(source_attribution=attribution)

        # Act
        result = metadata.to_dict()

        # Assert
        assert "title" not in result
        assert "description" not in result
        assert "custom_fields" not in result
        assert "source_attribution" in result


@pytest.mark.unit
class TestMetadataNormalizer:
    """Tests for MetadataNormalizer class"""

    def test_normalize_extracts_title(self):
        """Extracts title from raw metadata."""
        # Arrange
        normalizer = MetadataNormalizer()
        raw_metadata = {"title": "My Asset Title", "other": "data"}

        # Act
        result = normalizer.normalize(raw_metadata, "test_system", "ABC123")

        # Assert
        assert result.title == "My Asset Title"

    def test_normalize_extracts_title_from_name_field(self):
        """Extracts title from 'name' field when 'title' not present."""
        # Arrange
        normalizer = MetadataNormalizer()
        raw_metadata = {"name": "Asset Name", "other": "data"}

        # Act
        result = normalizer.normalize(raw_metadata, "test_system", "ABC123")

        # Assert
        assert result.title == "Asset Name"

    def test_normalize_extracts_description(self):
        """Extracts description from raw metadata."""
        # Arrange
        normalizer = MetadataNormalizer()
        raw_metadata = {"description": "Full description text", "other": "data"}

        # Act
        result = normalizer.normalize(raw_metadata, "test_system", "ABC123")

        # Assert
        assert result.description == "Full description text"

    def test_normalize_extracts_description_from_synopsis(self):
        """Extracts description from 'synopsis' field when 'description' not present."""
        # Arrange
        normalizer = MetadataNormalizer()
        raw_metadata = {"synopsis": "Asset synopsis", "other": "data"}

        # Act
        result = normalizer.normalize(raw_metadata, "test_system", "ABC123")

        # Assert
        assert result.description == "Asset synopsis"

    def test_normalize_stores_all_raw_metadata_in_custom_fields(self):
        """Stores ALL raw metadata in custom_fields (placeholder behavior)."""
        # Arrange
        normalizer = MetadataNormalizer()
        raw_metadata = {
            "title": "My Title",
            "description": "My Description",
            "customField1": "value1",
            "customField2": 123,
            "nested": {"key": "value"},
        }

        # Act
        result = normalizer.normalize(raw_metadata, "test_system", "ABC123")

        # Assert
        assert result.custom_fields == raw_metadata
        assert result.custom_fields["title"] == "My Title"
        assert result.custom_fields["customField1"] == "value1"
        assert result.custom_fields["nested"] == {"key": "value"}

    def test_normalize_always_populates_source_attribution(self):
        """Always populates source_attribution with required fields."""
        # Arrange
        normalizer = MetadataNormalizer()
        raw_metadata = {"title": "Test"}

        # Act
        result = normalizer.normalize(raw_metadata, "my_source_system", "CORR123")

        # Assert
        assert result.source_attribution is not None
        assert result.source_attribution.source_system == "my_source_system"
        assert result.source_attribution.correlation_id == "CORR123"
        assert result.source_attribution.fetch_timestamp is not None
        # Verify timestamp is valid ISO format
        datetime.fromisoformat(result.source_attribution.fetch_timestamp)

    def test_normalize_extracts_source_record_id(self):
        """Extracts source_record_id from 'id' field in raw metadata."""
        # Arrange
        normalizer = MetadataNormalizer()
        raw_metadata = {"id": "ext-12345", "title": "Test"}

        # Act
        result = normalizer.normalize(raw_metadata, "test_system", "ABC123")

        # Assert
        assert result.source_attribution.source_record_id == "ext-12345"

    def test_normalize_extracts_source_record_id_from_assetId(self):
        """Extracts source_record_id from 'assetId' field."""
        # Arrange
        normalizer = MetadataNormalizer()
        raw_metadata = {"assetId": "asset-789", "title": "Test"}

        # Act
        result = normalizer.normalize(raw_metadata, "test_system", "ABC123")

        # Assert
        assert result.source_attribution.source_record_id == "asset-789"

    def test_normalize_handles_empty_metadata(self):
        """Handles empty raw metadata gracefully."""
        # Arrange
        normalizer = MetadataNormalizer()
        raw_metadata = {}

        # Act
        result = normalizer.normalize(raw_metadata, "test_system", "ABC123")

        # Assert
        assert result.title is None
        assert result.description is None
        assert result.custom_fields == {}
        assert result.source_attribution is not None
        assert result.source_attribution.source_record_id is None

    def test_normalize_converts_non_string_title_to_string(self):
        """Converts non-string title values to string."""
        # Arrange
        normalizer = MetadataNormalizer()
        raw_metadata = {"title": 12345}

        # Act
        result = normalizer.normalize(raw_metadata, "test_system", "ABC123")

        # Assert
        assert result.title == "12345"

    def test_normalize_handles_none_field_values(self):
        """Handles None values in raw metadata fields."""
        # Arrange
        normalizer = MetadataNormalizer()
        raw_metadata = {"title": None, "description": None, "id": None}

        # Act
        result = normalizer.normalize(raw_metadata, "test_system", "ABC123")

        # Assert
        assert result.title is None
        assert result.description is None
        assert result.source_attribution.source_record_id is None


@pytest.mark.unit
class TestMetadataNormalizerWithSourceType:
    """Tests for MetadataNormalizer with source_type configuration."""

    def test_normalize_with_generic_xml_source_type(self):
        """Uses generic_xml normalizer when source_type is specified."""
        # Arrange
        config = {
            "source_namespace_prefix": "ACME",
            "primary_id_field": "content_id",
            "ref_id_field": "ref_id",
            "title_field": "title",
            "title_brief_field": "title_brief",
        }
        normalizer = MetadataNormalizer(source_type="generic_xml", config=config)
        raw_metadata = {
            "content_id": "TEST123",
            "title": "Test Episode Title",
            "title_brief": "Test Ep",
        }

        # Act
        result = normalizer.normalize(raw_metadata, "test_system", "CORR123")

        # Assert - result should be a dict (not NormalizedMetadata)
        assert isinstance(result, dict)
        assert "BasicMetadata" in result
        assert result["BasicMetadata"]["ContentId"] == "TEST123"
        assert "SourceAttribution" in result
        # Note: generic_xml normalizer uses source_namespace_prefix as source_system
        # and extracts correlation_id from raw_metadata (ref_id or primary_id)
        assert result["SourceAttribution"]["CorrelationId"] == "TEST123"
        assert result["SourceAttribution"]["SourceSystem"] == "acme"

    def test_normalize_with_inline_config(self):
        """Uses inline configuration for field mappings."""
        # Arrange
        config = {
            "source_namespace_prefix": "CUSTOMER",
            "primary_id_field": "asset_id",
            "ref_id_field": "reference_id",
            "identifier_mappings": {
                "asset_id": "",
                "reference_id": "-REF",
            },
        }
        normalizer = MetadataNormalizer(source_type="generic_xml", config=config)
        raw_metadata = {
            "asset_id": "ASSET001",
            "reference_id": "REF001",
            "title": "Sample Content",
        }

        # Act
        result = normalizer.normalize(raw_metadata, "test_system", "CORR123")

        # Assert
        assert isinstance(result, dict)
        assert result["BasicMetadata"]["ContentId"] == "ASSET001"
        # Check identifiers are mapped with correct namespaces
        alt_ids = result["BasicMetadata"]["AltIdentifiers"]
        namespaces = [aid["Namespace"] for aid in alt_ids]
        assert "CUSTOMER" in namespaces
        assert "CUSTOMER-REF" in namespaces

    def test_backward_compatibility_without_source_type(self):
        """Uses placeholder behavior when source_type is not specified."""
        # Arrange
        normalizer = MetadataNormalizer()  # No source_type
        raw_metadata = {"title": "Test Title", "custom_field": "value"}

        # Act
        result = normalizer.normalize(raw_metadata, "test_system", "ABC123")

        # Assert - result should be NormalizedMetadata (placeholder behavior)
        assert isinstance(result, NormalizedMetadata)
        assert result.title == "Test Title"
        assert result.custom_fields == raw_metadata

    def test_normalize_raises_error_for_unknown_source_type(self):
        """Raises ValueError for unknown source type."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            MetadataNormalizer(source_type="unknown_type", config={})

        assert "Unknown source type" in str(exc_info.value)
        assert "unknown_type" in str(exc_info.value)

    def test_normalize_with_empty_config(self):
        """Uses default configuration when config is empty."""
        # Arrange
        normalizer = MetadataNormalizer(source_type="generic_xml", config={})
        raw_metadata = {
            "id": "DEFAULT123",
            "title": "Default Config Test",
        }

        # Act
        result = normalizer.normalize(raw_metadata, "test_system", "CORR123")

        # Assert
        assert isinstance(result, dict)
        # Default primary_id_field is "id"
        assert result["BasicMetadata"]["ContentId"] == "DEFAULT123"

    def test_normalize_with_validation_errors(self):
        """Raises RuntimeError when normalization fails with validation errors."""
        # Arrange
        normalizer = MetadataNormalizer(source_type="generic_xml", config={})
        # Empty metadata triggers validation errors in generic_xml normalizer
        raw_metadata = {}

        # Act & Assert - empty metadata raises RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            normalizer.normalize(raw_metadata, "test_system", "CORR123")

        assert "Metadata normalization failed" in str(exc_info.value)

    def test_normalize_preserves_source_attribution_override(self):
        """Source attribution values come from config and raw_metadata for generic_xml."""
        # Arrange
        config = {
            "source_namespace_prefix": "ACME",
            "primary_id_field": "id",
        }
        normalizer = MetadataNormalizer(source_type="generic_xml", config=config)
        raw_metadata = {"id": "TEST123", "title": "Test"}

        # Act
        result = normalizer.normalize(
            raw_metadata,
            source_system="override_system",
            correlation_id="override_corr_id",
        )

        # Assert - generic_xml normalizer uses source_namespace_prefix as source_system
        # and extracts correlation_id from raw_metadata, ignoring the parameters
        assert result["SourceAttribution"]["SourceSystem"] == "acme"
        assert result["SourceAttribution"]["CorrelationId"] == "TEST123"
        assert result["SourceAttribution"]["SourceType"] == "generic_xml"
        # Verify nested basic_metadata uses CamelCase
        assert result["BasicMetadata"]["ContentId"] == "TEST123"


@pytest.mark.unit
class TestConfigLoader:
    """Tests for S3 configuration loading functionality."""

    def test_resolve_normalizer_config_with_inline_only(self):
        """Returns inline config when no S3 path is provided."""
        from nodes.external_metadata_fetch.normalizers import resolve_normalizer_config

        # Arrange
        node_config = {
            "source_type": "generic_xml",
            "config": {
                "source_namespace_prefix": "INLINE",
                "primary_id_field": "inline_id",
            },
        }

        # Act
        result = resolve_normalizer_config(node_config)

        # Assert
        assert result["source_namespace_prefix"] == "INLINE"
        assert result["primary_id_field"] == "inline_id"

    def test_resolve_normalizer_config_with_empty_config(self):
        """Returns empty dict when no config is provided."""
        from nodes.external_metadata_fetch.normalizers import resolve_normalizer_config

        # Arrange
        node_config = {"source_type": "generic_xml"}

        # Act
        result = resolve_normalizer_config(node_config)

        # Assert
        assert result == {}

    def test_resolve_normalizer_config_raises_error_without_bucket_env(self):
        """Raises ValueError when S3 path is provided but bucket env var is not set."""
        import os

        from nodes.external_metadata_fetch.normalizers import resolve_normalizer_config

        # Arrange
        node_config = {
            "source_type": "generic_xml",
            "config_s3_path": "normalizer-configs/test-config.json",
        }

        # Ensure IAC_ASSETS_BUCKET is not set
        original_value = os.environ.pop("IAC_ASSETS_BUCKET", None)

        try:
            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                resolve_normalizer_config(node_config)

            assert "IAC_ASSETS_BUCKET" in str(exc_info.value)
        finally:
            # Restore original value if it existed
            if original_value is not None:
                os.environ["IAC_ASSETS_BUCKET"] = original_value

    def test_load_config_from_s3_caching(self):
        """Verifies that S3 config loading uses LRU cache."""
        import json
        from unittest.mock import MagicMock, patch

        from nodes.external_metadata_fetch.normalizers import (
            clear_config_cache,
            load_config_from_s3,
        )

        # Clear cache before test
        clear_config_cache()

        # Arrange
        mock_s3 = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps({"cached": "config"}).encode("utf-8")
        mock_s3.get_object.return_value = {"Body": mock_body}

        with patch(
            "nodes.external_metadata_fetch.normalizers.config_loader.get_s3_client",
            return_value=mock_s3,
        ):
            # Act - call twice with same parameters
            result1 = load_config_from_s3("test-bucket", "test-key.json")
            result2 = load_config_from_s3("test-bucket", "test-key.json")

            # Assert - S3 should only be called once due to caching
            assert mock_s3.get_object.call_count == 1
            assert result1 == result2
            assert result1["cached"] == "config"

        # Clear cache after test
        clear_config_cache()

    def test_load_config_from_s3_not_found_error(self):
        """Raises ValueError when S3 config file is not found."""
        from unittest.mock import MagicMock, patch

        from botocore.exceptions import ClientError
        from nodes.external_metadata_fetch.normalizers import (
            clear_config_cache,
            load_config_from_s3,
        )

        # Clear cache before test
        clear_config_cache()

        # Arrange
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject",
        )

        with patch(
            "nodes.external_metadata_fetch.normalizers.config_loader.get_s3_client",
            return_value=mock_s3,
        ):
            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                load_config_from_s3("test-bucket", "missing-key.json")

            assert "not found" in str(exc_info.value).lower()

        # Clear cache after test
        clear_config_cache()

    def test_load_config_from_s3_invalid_json_error(self):
        """Raises ValueError when S3 config file contains invalid JSON."""
        from unittest.mock import MagicMock, patch

        from nodes.external_metadata_fetch.normalizers import (
            clear_config_cache,
            load_config_from_s3,
        )

        # Clear cache before test
        clear_config_cache()

        # Arrange
        mock_s3 = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = b"not valid json {"
        mock_s3.get_object.return_value = {"Body": mock_body}

        with patch(
            "nodes.external_metadata_fetch.normalizers.config_loader.get_s3_client",
            return_value=mock_s3,
        ):
            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                load_config_from_s3("test-bucket", "invalid.json")

            assert "Invalid JSON" in str(exc_info.value)

        # Clear cache after test
        clear_config_cache()

    def test_resolve_normalizer_config_hybrid_mode(self):
        """Inline config overrides S3 config in hybrid mode."""
        import json
        import os
        from unittest.mock import MagicMock, patch

        from nodes.external_metadata_fetch.normalizers import (
            clear_config_cache,
            resolve_normalizer_config,
        )

        # Clear cache before test
        clear_config_cache()

        # Arrange
        s3_config = {
            "source_namespace_prefix": "S3_VALUE",
            "primary_id_field": "s3_id",
            "other_field": "from_s3",
        }

        mock_s3 = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(s3_config).encode("utf-8")
        mock_s3.get_object.return_value = {"Body": mock_body}

        node_config = {
            "source_type": "generic_xml",
            "config_s3_path": "normalizer-configs/test-config.json",
            "config": {
                "source_namespace_prefix": "INLINE_OVERRIDE",  # Override S3 value
            },
        }

        # Set environment variable
        original_value = os.environ.get("IAC_ASSETS_BUCKET")
        os.environ["IAC_ASSETS_BUCKET"] = "test-bucket"

        try:
            with patch(
                "nodes.external_metadata_fetch.normalizers.config_loader.get_s3_client",
                return_value=mock_s3,
            ):
                # Act
                result = resolve_normalizer_config(node_config)

                # Assert - inline should override S3
                assert result["source_namespace_prefix"] == "INLINE_OVERRIDE"
                # S3 values not overridden should be preserved
                assert result["primary_id_field"] == "s3_id"
                assert result["other_field"] == "from_s3"
        finally:
            # Restore original value
            if original_value is not None:
                os.environ["IAC_ASSETS_BUCKET"] = original_value
            else:
                os.environ.pop("IAC_ASSETS_BUCKET", None)

        # Clear cache after test
        clear_config_cache()
