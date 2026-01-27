"""
Correlation ID extraction module for External Metadata Fetch Node.

This module provides functionality to extract correlation IDs from asset filenames
and handle correlation ID overrides from pipeline parameters.

The correlation ID is used to look up assets in external source systems.
By default, it is extracted from the filename by removing the file extension.
"""

from dataclasses import dataclass


@dataclass
class CorrelationIdResult:
    """Result of correlation ID extraction or resolution."""

    correlation_id: str
    source: str  # "filename", "override", or "error"
    original_filename: str | None = None
    error_message: str | None = None


class CorrelationIdError(Exception):
    """Raised when correlation ID cannot be extracted or resolved."""


def extract_correlation_id_from_filename(filename: str) -> str:
    """
    Extract correlation ID from a filename by removing the file extension.

    The correlation ID is derived by removing the last file extension from
    the filename. This handles various edge cases:
    - Standard filenames: "ABC123.mp4" → "ABC123"
    - Multiple dots: "my.video.file.mp4" → "my.video.file"
    - No extension: "ABC123" → "ABC123"
    - Hidden files: ".gitignore" → ".gitignore" (no change, dot is not extension separator)
    - Empty extension: "file." → "file"

    Args:
        filename: The filename to extract correlation ID from

    Returns:
        The correlation ID (filename without extension)

    Raises:
        CorrelationIdError: If filename is empty or invalid
    """
    if not filename:
        raise CorrelationIdError("Filename cannot be empty")

    # Strip any leading/trailing whitespace
    filename = filename.strip()

    if not filename:
        raise CorrelationIdError("Filename cannot be empty or whitespace only")

    # Find the last dot in the filename
    last_dot_index: int = filename.rfind(".")

    # Handle edge cases:
    # - No dot found: return filename as-is
    # - Dot at position 0 (hidden file like .gitignore): return filename as-is
    # - Dot at the end (file.): return filename without trailing dot
    if last_dot_index <= 0:
        # No extension or hidden file without extension
        return filename

    # Return everything before the last dot
    return filename[:last_dot_index]


def resolve_correlation_id(
    filename: str | None = None,
    override_correlation_id: str | None = None,
    existing_external_id: str | None = None,
) -> CorrelationIdResult:
    """
    Resolve the correlation ID to use for metadata lookup.

    This function determines the correlation ID based on the following priority:
    1. If override_correlation_id is provided (from params), use it
    2. If existing_external_id is set (from previous SUCCESSFUL lookup), use it
    3. Otherwise, extract from filename

    This priority ensures that:
    - Manual overrides always take precedence (for corrections)
    - Previously successful lookups are preserved (for bulk re-runs)
    - Filename extraction is the fallback for new assets

    Note: The existing_external_id should only be passed if the previous
    lookup was successful (ExternalMetadataStatus.status == "success").
    This prevents re-using a bad correlation ID from a failed attempt.

    Args:
        filename: The asset filename to extract correlation ID from
        override_correlation_id: Optional override from pipeline params
        existing_external_id: Optional existing ExternalAssetId from asset record
                             (only if previous lookup was successful)

    Returns:
        CorrelationIdResult with the resolved correlation ID and source

    Raises:
        CorrelationIdError: If no correlation ID can be determined
    """
    # Priority 1: Use override if provided
    if override_correlation_id is not None:
        # Validate override is not empty
        override_stripped = override_correlation_id.strip()
        if override_stripped:
            return CorrelationIdResult(
                correlation_id=override_stripped,
                source="override",
                original_filename=filename,
            )
        # Empty override falls through to next priority

    # Priority 2: Use existing ExternalAssetId if set (from previous successful lookup)
    if existing_external_id is not None:
        existing_stripped = existing_external_id.strip()
        if existing_stripped:
            return CorrelationIdResult(
                correlation_id=existing_stripped,
                source="existing",
                original_filename=filename,
            )
        # Empty existing ID falls through to filename extraction

    # Priority 3: Extract from filename
    if filename:
        try:
            correlation_id = extract_correlation_id_from_filename(filename)
            return CorrelationIdResult(
                correlation_id=correlation_id,
                source="filename",
                original_filename=filename,
            )
        except CorrelationIdError as e:
            raise CorrelationIdError(
                f"Failed to extract correlation ID from filename '{filename}': {e}"
            )

    # No correlation ID available
    raise CorrelationIdError(
        "Cannot determine correlation ID: no override provided, no existing ID, and no filename available"
    )
