"""
Property-based tests for correlation ID extraction.

These tests verify that the correlation ID extractor correctly removes
file extensions from filenames to derive the correlation ID.

**Feature: external-metadata-enrichment, Property 1: Correlation ID Extraction**
**Validates: Requirements 1.2, 9.1**
"""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# Import from nodes (pytest.ini adds lambdas/ to pythonpath)
from nodes.external_metadata_fetch.correlation_id import (
    CorrelationIdError,
    extract_correlation_id_from_filename,
    resolve_correlation_id,
)


@pytest.mark.unit
class TestCorrelationIdExtractionProperty:
    """Property-based tests for correlation ID extraction from filenames."""

    @given(filename=st.from_regex(r"[A-Za-z0-9_-]+\.[a-z0-9]+", fullmatch=True))
    @settings(max_examples=100)
    def test_extraction_removes_extension(self, filename: str):
        """
        Property 1: Correlation ID Extraction

        *For any* valid filename with a standard extension pattern,
        the extract_correlation_id_from_filename() function SHALL
        return the filename without the extension.

        **Validates: Requirements 1.2, 9.1**

        This property ensures that:
        1. The extension (last dot and everything after) is removed
        2. The base filename is preserved
        3. The result does not contain the extension
        """
        # Act
        correlation_id = extract_correlation_id_from_filename(filename)

        # Assert
        # The correlation ID should not end with the extension
        last_dot_index = filename.rfind(".")
        expected_base = filename[:last_dot_index]
        extension = filename[last_dot_index:]

        assert correlation_id == expected_base, (
            f"Correlation ID should be '{expected_base}' for filename '{filename}', "
            f"but got '{correlation_id}'"
        )
        assert not correlation_id.endswith(
            extension
        ), f"Correlation ID should not end with extension '{extension}'"

    @given(
        base_name=st.from_regex(r"[A-Za-z0-9_-]+", fullmatch=True),
        extension=st.from_regex(r"[a-z0-9]+", fullmatch=True),
    )
    @settings(max_examples=100)
    def test_extraction_preserves_base_name(self, base_name: str, extension: str):
        """
        Property 1 (extended): Base name preservation

        *For any* base name and extension, when combined into a filename,
        the extraction SHALL return exactly the original base name.

        **Validates: Requirements 1.2, 9.1**

        This property ensures round-trip consistency: if we know the
        base name and extension, extraction should recover the base name.
        """
        # Arrange
        filename = f"{base_name}.{extension}"

        # Act
        correlation_id = extract_correlation_id_from_filename(filename)

        # Assert
        assert correlation_id == base_name, (
            f"Extraction should return base name '{base_name}' "
            f"for filename '{filename}', but got '{correlation_id}'"
        )

    @given(
        base_parts=st.lists(
            st.from_regex(r"[A-Za-z0-9_-]+", fullmatch=True),
            min_size=2,
            max_size=5,
        ),
        extension=st.from_regex(r"[a-z0-9]+", fullmatch=True),
    )
    @settings(max_examples=100)
    def test_extraction_handles_multiple_dots(self, base_parts: list, extension: str):
        """
        Property 1 (extended): Multiple dots handling

        *For any* filename with multiple dots (e.g., "my.video.file.mp4"),
        the extraction SHALL only remove the last extension, preserving
        all other dots in the correlation ID.

        **Validates: Requirements 1.2, 9.1**

        This property ensures that filenames with dots in the base name
        are handled correctly.
        """
        # Arrange
        base_name = ".".join(base_parts)
        filename = f"{base_name}.{extension}"

        # Act
        correlation_id = extract_correlation_id_from_filename(filename)

        # Assert
        assert correlation_id == base_name, (
            f"Extraction should return '{base_name}' for filename '{filename}', "
            f"but got '{correlation_id}'"
        )

    @given(filename=st.from_regex(r"[A-Za-z0-9_-]+", fullmatch=True))
    @settings(max_examples=100)
    def test_extraction_handles_no_extension(self, filename: str):
        """
        Property 1 (extended): No extension handling

        *For any* filename without an extension (no dot), the extraction
        SHALL return the filename unchanged.

        **Validates: Requirements 1.2, 9.1**

        This property ensures that filenames without extensions are
        handled gracefully.
        """
        # Ensure no dot in filename
        assume("." not in filename)

        # Act
        correlation_id = extract_correlation_id_from_filename(filename)

        # Assert
        assert correlation_id == filename, (
            f"Extraction should return '{filename}' unchanged when no extension, "
            f"but got '{correlation_id}'"
        )

    @given(filename=st.from_regex(r"\.[A-Za-z0-9_-]+", fullmatch=True))
    @settings(max_examples=100)
    def test_extraction_handles_hidden_files(self, filename: str):
        """
        Property 1 (extended): Hidden file handling

        *For any* hidden file (starting with dot, like ".gitignore"),
        the extraction SHALL return the filename unchanged, as the
        leading dot is not an extension separator.

        **Validates: Requirements 1.2, 9.1**

        This property ensures Unix-style hidden files are handled correctly.
        """
        # Ensure filename starts with dot and has no other dots
        assume(filename.startswith("."))
        assume(filename.count(".") == 1)

        # Act
        correlation_id = extract_correlation_id_from_filename(filename)

        # Assert
        assert correlation_id == filename, (
            f"Hidden file '{filename}' should be returned unchanged, "
            f"but got '{correlation_id}'"
        )

    @given(base_name=st.from_regex(r"[A-Za-z0-9_-]+", fullmatch=True))
    @settings(max_examples=100)
    def test_extraction_handles_trailing_dot(self, base_name: str):
        """
        Property 1 (extended): Trailing dot handling

        *For any* filename ending with a dot (empty extension),
        the extraction SHALL return the base name without the trailing dot.

        **Validates: Requirements 1.2, 9.1**

        This property ensures edge case of empty extension is handled.
        """
        # Arrange
        filename = f"{base_name}."

        # Act
        correlation_id = extract_correlation_id_from_filename(filename)

        # Assert
        assert correlation_id == base_name, (
            f"Extraction should return '{base_name}' for filename '{filename}', "
            f"but got '{correlation_id}'"
        )

    def test_extraction_raises_for_empty_filename(self):
        """
        Property 1 (error case): Empty filename handling

        WHEN an empty filename is provided, the extraction SHALL raise
        a CorrelationIdError with a descriptive message.

        **Validates: Requirements 9.4**
        """
        # Act & Assert
        with pytest.raises(CorrelationIdError) as exc_info:
            extract_correlation_id_from_filename("")

        assert "empty" in str(exc_info.value).lower()

    def test_extraction_raises_for_whitespace_only_filename(self):
        """
        Property 1 (error case): Whitespace-only filename handling

        WHEN a whitespace-only filename is provided, the extraction SHALL
        raise a CorrelationIdError with a descriptive message.

        **Validates: Requirements 9.4**
        """
        # Act & Assert
        with pytest.raises(CorrelationIdError) as exc_info:
            extract_correlation_id_from_filename("   ")

        assert "empty" in str(exc_info.value).lower()


@pytest.mark.unit
class TestCorrelationIdOverrideProperty:
    """Property-based tests for correlation ID override behavior."""

    @given(
        filename=st.from_regex(r"[A-Za-z0-9_-]+\.[a-z0-9]+", fullmatch=True),
        override_id=st.text(
            min_size=1,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ),
    )
    @settings(max_examples=100)
    def test_override_takes_precedence_over_filename(
        self, filename: str, override_id: str
    ):
        """
        Property 3: Correlation ID Override

        *For any* filename and non-empty override correlation ID,
        the resolve_correlation_id() function SHALL use the override
        instead of extracting from the filename.

        **Validates: Requirements 2.3, 9.3, 11.3**

        This property ensures that:
        1. The override takes precedence over filename extraction
        2. The source is correctly identified as "override"
        3. The original filename is preserved in the result
        """
        # Act
        result = resolve_correlation_id(
            filename=filename,
            override_correlation_id=override_id,
        )

        # Assert
        assert result.correlation_id == override_id, (
            f"Override '{override_id}' should take precedence over filename '{filename}', "
            f"but got '{result.correlation_id}'"
        )
        assert result.source == "override", (
            f"Source should be 'override' when override is provided, "
            f"but got '{result.source}'"
        )
        assert result.original_filename == filename, (
            f"Original filename should be preserved as '{filename}', "
            f"but got '{result.original_filename}'"
        )

    @given(
        override_id=st.text(
            min_size=1,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ),
    )
    @settings(max_examples=100)
    def test_override_works_without_filename(self, override_id: str):
        """
        Property 3 (extended): Override without filename

        *For any* non-empty override correlation ID, the resolve function
        SHALL succeed even when no filename is provided.

        **Validates: Requirements 2.3, 9.3, 11.3**

        This property ensures that override can be used independently
        of filename extraction.
        """
        # Act
        result = resolve_correlation_id(
            filename=None,
            override_correlation_id=override_id,
        )

        # Assert
        assert result.correlation_id == override_id, (
            f"Override '{override_id}' should be used when no filename provided, "
            f"but got '{result.correlation_id}'"
        )
        assert (
            result.source == "override"
        ), f"Source should be 'override', but got '{result.source}'"

    @given(
        filename=st.from_regex(r"[A-Za-z0-9_-]+\.[a-z0-9]+", fullmatch=True),
    )
    @settings(max_examples=100)
    def test_empty_override_falls_back_to_filename(self, filename: str):
        """
        Property 3 (extended): Empty override fallback

        *For any* filename, when an empty or whitespace-only override is
        provided, the resolve function SHALL fall back to filename extraction.

        **Validates: Requirements 2.3, 9.3, 11.3**

        This property ensures that empty overrides don't prevent
        filename extraction from working.
        """
        # Test with empty string
        result = resolve_correlation_id(
            filename=filename,
            override_correlation_id="",
        )

        expected_id = extract_correlation_id_from_filename(filename)
        assert result.correlation_id == expected_id, (
            f"Empty override should fall back to filename extraction, "
            f"expected '{expected_id}', but got '{result.correlation_id}'"
        )
        assert result.source == "filename", (
            f"Source should be 'filename' when override is empty, "
            f"but got '{result.source}'"
        )

    @given(
        filename=st.from_regex(r"[A-Za-z0-9_-]+\.[a-z0-9]+", fullmatch=True),
    )
    @settings(max_examples=100)
    def test_whitespace_override_falls_back_to_filename(self, filename: str):
        """
        Property 3 (extended): Whitespace override fallback

        *For any* filename, when a whitespace-only override is provided,
        the resolve function SHALL fall back to filename extraction.

        **Validates: Requirements 2.3, 9.3, 11.3**
        """
        # Test with whitespace-only string
        result = resolve_correlation_id(
            filename=filename,
            override_correlation_id="   ",
        )

        expected_id = extract_correlation_id_from_filename(filename)
        assert result.correlation_id == expected_id, (
            f"Whitespace override should fall back to filename extraction, "
            f"expected '{expected_id}', but got '{result.correlation_id}'"
        )
        assert result.source == "filename", (
            f"Source should be 'filename' when override is whitespace, "
            f"but got '{result.source}'"
        )

    @given(
        filename=st.from_regex(r"[A-Za-z0-9_-]+\.[a-z0-9]+", fullmatch=True),
    )
    @settings(max_examples=100)
    def test_none_override_uses_filename(self, filename: str):
        """
        Property 3 (extended): None override uses filename

        *For any* filename, when override is None (not provided),
        the resolve function SHALL extract from filename.

        **Validates: Requirements 2.3, 9.3, 11.3**
        """
        # Act
        result = resolve_correlation_id(
            filename=filename,
            override_correlation_id=None,
        )

        # Assert
        expected_id = extract_correlation_id_from_filename(filename)
        assert result.correlation_id == expected_id, (
            f"None override should use filename extraction, "
            f"expected '{expected_id}', but got '{result.correlation_id}'"
        )
        assert result.source == "filename", (
            f"Source should be 'filename' when override is None, "
            f"but got '{result.source}'"
        )

    @given(
        override_id=st.text(
            min_size=1,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ).map(
            lambda x: f"  {x}  "
        ),  # Add surrounding whitespace
    )
    @settings(max_examples=100)
    def test_override_is_stripped(self, override_id: str):
        """
        Property 3 (extended): Override whitespace stripping

        *For any* override with surrounding whitespace, the resolve
        function SHALL strip the whitespace before using it.

        **Validates: Requirements 2.3, 9.3, 11.3**
        """
        # Act
        result = resolve_correlation_id(
            filename="test.mp4",
            override_correlation_id=override_id,
        )

        # Assert
        expected_stripped = override_id.strip()
        assert result.correlation_id == expected_stripped, (
            f"Override should be stripped, expected '{expected_stripped}', "
            f"but got '{result.correlation_id}'"
        )

    def test_resolve_raises_when_no_id_available(self):
        """
        Property 3 (error case): No correlation ID available

        WHEN neither filename nor override is provided, the resolve
        function SHALL raise a CorrelationIdError.

        **Validates: Requirements 9.4**
        """
        # Act & Assert
        with pytest.raises(CorrelationIdError) as exc_info:
            resolve_correlation_id(filename=None, override_correlation_id=None)

        error_msg = str(exc_info.value).lower()
        assert "cannot determine" in error_msg or "no" in error_msg
