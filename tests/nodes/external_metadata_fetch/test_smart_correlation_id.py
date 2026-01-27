"""
Unit tests for smart correlation ID resolution with existing ID support.

Tests that the correlation ID resolution correctly handles the priority:
1. Override (from params) - always takes precedence
2. Existing ExternalAssetId (from previous SUCCESSFUL lookup)
3. Filename extraction (fallback for new assets)

This ensures that:
- Manual overrides always work for corrections
- Previously successful lookups are preserved for bulk re-runs
- Bad correlation IDs from failed attempts are NOT reused

**Feature: external-metadata-enrichment**
**Validates: Requirements 2.3, 9.3, 11.3**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Import from nodes (pytest.ini adds lambdas/ to pythonpath)
from nodes.external_metadata_fetch.correlation_id import (
    resolve_correlation_id,
)


@pytest.mark.unit
class TestExistingExternalIdPriority:
    """Tests for existing ExternalAssetId priority in correlation ID resolution."""

    def test_existing_id_used_when_no_override(self):
        """
        Test that existing ExternalAssetId is used when no override is provided.

        This validates the scenario where a previous successful lookup stored
        a good correlation ID, and we want to reuse it for bulk re-runs.
        """
        # Arrange
        filename = "original-file.mp4"  # Would extract to "original-file"
        existing_id = "EXT-001234"  # Previously successful lookup used this ID

        # Act
        result = resolve_correlation_id(
            filename=filename,
            override_correlation_id=None,
            existing_external_id=existing_id,
        )

        # Assert
        assert result.correlation_id == existing_id
        assert result.source == "existing"
        assert result.original_filename == filename

    def test_override_takes_precedence_over_existing_id(self):
        """
        Test that override always takes precedence over existing ExternalAssetId.

        This validates the scenario where someone needs to correct a bad
        correlation ID by providing an explicit override.
        """
        # Arrange
        filename = "original-file.mp4"
        existing_id = "EXT-001234"
        override_id = "CORRECTED-ID"

        # Act
        result = resolve_correlation_id(
            filename=filename,
            override_correlation_id=override_id,
            existing_external_id=existing_id,
        )

        # Assert
        assert result.correlation_id == override_id
        assert result.source == "override"
        assert result.original_filename == filename

    def test_filename_used_when_no_existing_id(self):
        """
        Test that filename extraction is used when no existing ID is available.

        This validates the scenario for new assets that haven't been
        processed before.
        """
        # Arrange
        filename = "ABC123.mp4"

        # Act
        result = resolve_correlation_id(
            filename=filename,
            override_correlation_id=None,
            existing_external_id=None,
        )

        # Assert
        assert result.correlation_id == "ABC123"
        assert result.source == "filename"
        assert result.original_filename == filename

    def test_empty_existing_id_falls_back_to_filename(self):
        """
        Test that empty existing ID falls back to filename extraction.

        This handles the edge case where ExternalAssetId exists but is empty.
        """
        # Arrange
        filename = "ABC123.mp4"

        # Act - empty string
        result = resolve_correlation_id(
            filename=filename,
            override_correlation_id=None,
            existing_external_id="",
        )

        # Assert
        assert result.correlation_id == "ABC123"
        assert result.source == "filename"

    def test_whitespace_existing_id_falls_back_to_filename(self):
        """
        Test that whitespace-only existing ID falls back to filename extraction.
        """
        # Arrange
        filename = "ABC123.mp4"

        # Act - whitespace only
        result = resolve_correlation_id(
            filename=filename,
            override_correlation_id=None,
            existing_external_id="   ",
        )

        # Assert
        assert result.correlation_id == "ABC123"
        assert result.source == "filename"

    def test_existing_id_is_stripped(self):
        """
        Test that existing ID is stripped of whitespace before use.
        """
        # Arrange
        filename = "original-file.mp4"
        existing_id = "  EXT-001234  "  # With surrounding whitespace

        # Act
        result = resolve_correlation_id(
            filename=filename,
            override_correlation_id=None,
            existing_external_id=existing_id,
        )

        # Assert
        assert result.correlation_id == "EXT-001234"  # Stripped
        assert result.source == "existing"

    @given(
        existing_id=st.text(
            min_size=1,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ),
        filename=st.from_regex(r"[A-Za-z0-9_-]+\.[a-z0-9]+", fullmatch=True),
    )
    @settings(max_examples=100)
    def test_existing_id_always_preferred_over_filename(
        self, existing_id: str, filename: str
    ):
        """
        Property: Existing ID always preferred over filename extraction.

        *For any* non-empty existing ID and any filename, the resolve function
        SHALL use the existing ID when no override is provided.
        """
        # Act
        result = resolve_correlation_id(
            filename=filename,
            override_correlation_id=None,
            existing_external_id=existing_id,
        )

        # Assert
        assert result.correlation_id == existing_id
        assert result.source == "existing"

    @given(
        override_id=st.text(
            min_size=1,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ),
        existing_id=st.text(
            min_size=1,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ),
        filename=st.from_regex(r"[A-Za-z0-9_-]+\.[a-z0-9]+", fullmatch=True),
    )
    @settings(max_examples=100)
    def test_override_always_wins(
        self, override_id: str, existing_id: str, filename: str
    ):
        """
        Property: Override always takes precedence.

        *For any* override, existing ID, and filename combination,
        the override SHALL always be used.
        """
        # Act
        result = resolve_correlation_id(
            filename=filename,
            override_correlation_id=override_id,
            existing_external_id=existing_id,
        )

        # Assert
        assert result.correlation_id == override_id
        assert result.source == "override"
