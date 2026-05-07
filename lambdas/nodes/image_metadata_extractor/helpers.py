"""
Helper functions for metadata processing.

This module provides utility functions for transforming and formatting
metadata values for storage in DynamoDB.
"""

import re
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Tuple


def pretty_case(key: str) -> str:
    """
    Convert camelCase/PascalCase to Pretty Case.

    Transforms field names like "imageWidth" to "Image Width" and
    "ISO" to "ISO" (preserves all-caps acronyms).

    Args:
        key: Field name in camelCase or PascalCase

    Returns:
        Pretty cased string with spaces and capitalization

    Examples:
        >>> pretty_case("imageWidth")
        "Image Width"
        >>> pretty_case("ISO")
        "ISO"
        >>> pretty_case("fNumber")
        "F Number"
    """
    # Handle non-string keys (convert to string first)
    if not isinstance(key, str):
        key = str(key)

    if not key:
        return key

    # Handle all-caps acronyms (e.g., "ISO", "GPS")
    if key.isupper():
        return key

    # Insert space before uppercase letters that follow lowercase letters
    # or before uppercase letters followed by lowercase (for acronyms like "GPSLatitude")
    result = re.sub(r"([a-z])([A-Z])", r"\1 \2", key)
    result = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", result)

    # Capitalize first letter and each word after a space
    words = result.split(" ")
    capitalized = [word.capitalize() if not word.isupper() else word for word in words]

    return " ".join(capitalized)


def format_bytes(data: bytes, max_bytes: int = 60) -> str:
    """
    Format bytes as hexadecimal string.

    Converts bytes to space-separated hex pairs (e.g., "ff 00 a1").

    Args:
        data: Bytes to format
        max_bytes: Maximum number of bytes to include

    Returns:
        Hex string representation
    """
    limited = data[:max_bytes]
    hex_pairs = [f"{b:02x}" for b in limited]
    return " ".join(hex_pairs)


def slice_array(arr: List[Any], max_length: int) -> Tuple[List[Any], int]:
    """
    Slice array and return remainder count.

    Args:
        arr: Array to slice
        max_length: Maximum length to keep

    Returns:
        Tuple of (sliced_array, remainder_count)
    """
    if len(arr) <= max_length:
        return arr, 0

    return arr[:max_length], len(arr) - max_length


def clip_bytes(data: bytes, max_bytes: int = 60) -> str:
    """
    Convert byte array to hex string with truncation.

    Truncates at max_bytes and adds indication if longer.
    Format: "ff 00 a1 ... (N more bytes)"

    Args:
        data: Bytes to convert
        max_bytes: Maximum number of bytes to include (default: 60)

    Returns:
        Hex string representation with truncation indicator if needed

    Examples:
        >>> clip_bytes(b'\\xff\\x00\\xa1')
        "ff 00 a1"
        >>> clip_bytes(b'\\xff' * 100, max_bytes=2)
        "ff ff ... (98 more bytes)"
    """
    if not data:
        return ""

    hex_str = format_bytes(data, max_bytes)

    if len(data) > max_bytes:
        remaining = len(data) - max_bytes
        return f"{hex_str} ... ({remaining} more bytes)"

    return hex_str


def clip_string(text: str, max_length: int = 300) -> str:
    """
    Truncate string with indication of remaining characters.

    Args:
        text: String to truncate
        max_length: Maximum length to keep (default: 300)

    Returns:
        Truncated string with indicator if needed

    Examples:
        >>> clip_string("short")
        "short"
        >>> clip_string("a" * 400, max_length=300)
        "aaa...aaa (100 more characters)"
    """
    if not text or len(text) <= max_length:
        return text

    remaining = len(text) - max_length
    truncated = text[:max_length]
    return f"{truncated} ... ({remaining} more characters)"


import re as regex_module
from datetime import datetime


def normalize_date_string(date_str: str) -> str | None:
    """
    Normalize date string to ISO format (YYYY-MM-DD).

    Handles various date formats and validates they are parseable.
    Excludes invalid dates starting with "0000-00-00".

    Args:
        date_str: Date string in various formats

    Returns:
        ISO formatted date string (YYYY-MM-DD) or None if invalid

    Examples:
        >>> normalize_date_string("2023-12-08")
        "2023-12-08"
        >>> normalize_date_string("0000-00-00")
        None
        >>> normalize_date_string("12/08/2023")
        "2023-12-08"
    """
    if not date_str or not isinstance(date_str, str):
        return None

    # Check for invalid dates starting with "0000-00-00"
    if date_str.startswith("0000-00-00") or date_str.startswith("0000:00:00"):
        return None

    # Try to parse the date string
    date_formats = [
        "%Y-%m-%d",  # ISO format: 2023-12-08
        "%Y:%m:%d",  # EXIF format: 2023:12:08
        "%m/%d/%Y",  # US format: 12/08/2023
        "%d/%m/%Y",  # European format: 08/12/2023
        "%Y/%m/%d",  # Alternative: 2023/12/08
        "%Y-%m-%dT%H:%M:%S",  # ISO datetime (extract date part)
        "%Y:%m:%d %H:%M:%S",  # EXIF datetime (extract date part)
    ]

    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_str.strip(), fmt)
            # Return in ISO format
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # If no format matched, return None
    return None


def normalize_datetime_string(datetime_str: str) -> str | None:
    """
    Normalize datetime string to ISO format (YYYY-MM-DDTHH:MM:SS).

    Handles various datetime formats and validates they are parseable.
    Excludes invalid datetimes starting with "0000-00-00".

    Args:
        datetime_str: Datetime string in various formats

    Returns:
        ISO formatted datetime string or None if invalid

    Examples:
        >>> normalize_datetime_string("2023-12-08 14:30:00")
        "2023-12-08T14:30:00"
        >>> normalize_datetime_string("0000-00-00 00:00:00")
        None
        >>> normalize_datetime_string("2023:12:08 14:30:00")
        "2023-12-08T14:30:00"
    """
    if not datetime_str or not isinstance(datetime_str, str):
        return None

    # Check for invalid dates starting with "0000-00-00"
    if datetime_str.startswith("0000-00-00") or datetime_str.startswith("0000:00:00"):
        return None

    # Try to parse the datetime string
    datetime_formats = [
        "%Y-%m-%d %H:%M:%S",  # Standard: 2023-12-08 14:30:00
        "%Y:%m:%d %H:%M:%S",  # EXIF format: 2023:12:08 14:30:00
        "%Y-%m-%dT%H:%M:%S",  # ISO format: 2023-12-08T14:30:00
        "%Y-%m-%dT%H:%M:%SZ",  # ISO with Z: 2023-12-08T14:30:00Z
        "%Y-%m-%d %H:%M:%S.%f",  # With microseconds
        "%Y:%m:%d %H:%M:%S.%f",  # EXIF with microseconds
        "%m/%d/%Y %H:%M:%S",  # US format
        "%d/%m/%Y %H:%M:%S",  # European format
    ]

    for fmt in datetime_formats:
        try:
            parsed_datetime = datetime.strptime(datetime_str.strip(), fmt)
            # Return in ISO format
            return parsed_datetime.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue

    # If no format matched, return None
    return None


def is_likely_base64(value: str) -> bool:
    """
    Detect if a string is likely base64-encoded.

    Checks if the string:
    - Is longer than 100 characters
    - Matches base64 pattern (alphanumeric + / + = padding)

    Args:
        value: String to check

    Returns:
        True if likely base64, False otherwise

    Examples:
        >>> is_likely_base64("short")
        False
        >>> is_likely_base64("A" * 150)
        True
        >>> is_likely_base64("SGVsbG8gV29ybGQ=" * 10)
        True
    """
    if not isinstance(value, str) or len(value) <= 100:
        return False

    # Base64 pattern: alphanumeric characters, +, /, and = for padding
    # Should be mostly base64 characters (allow some flexibility)
    base64_pattern = regex_module.compile(r"^[A-Za-z0-9+/]+=*$")

    # Check if it matches base64 pattern
    if base64_pattern.match(value):
        return True

    # Also check if it's mostly base64 characters (>90%)
    base64_chars = sum(
        1
        for c in value
        if c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
    )
    ratio = base64_chars / len(value)

    return ratio > 0.9


def remove_base64_fields(obj: Any) -> None:
    """
    Remove base64-encoded fields from metadata object in-place.

    Recursively traverses the object and removes any fields that contain
    base64-encoded strings (length > 100, matching base64 pattern).

    Args:
        obj: Metadata object to clean (modified in-place)

    Examples:
        >>> data = {"image": "short", "thumbnail": "A" * 150}
        >>> remove_base64_fields(data)
        >>> "thumbnail" in data
        False
        >>> "image" in data
        True
    """
    if isinstance(obj, dict):
        # Collect keys to remove (can't modify dict during iteration)
        keys_to_remove = []

        for key, value in obj.items():
            if isinstance(value, str) and is_likely_base64(value):
                keys_to_remove.append(key)
            elif isinstance(value, (dict, list)):
                # Recursively process nested structures
                remove_base64_fields(value)

        # Remove identified keys
        for key in keys_to_remove:
            del obj[key]

    elif isinstance(obj, list):
        # Process each item in the list
        for item in obj:
            if isinstance(item, (dict, list)):
                remove_base64_fields(item)


def sanitize_metadata(obj: Any) -> Any:
    """
    Sanitize metadata for DynamoDB storage.

    Recursively processes metadata to:
    - Convert bytes to hex strings (truncated at 60 bytes)
    - Truncate long strings (> 300 characters)
    - Normalize date strings to ISO format
    - Remove invalid dates (starting with "0000-00-00")
    - Convert field names to Pretty Case
    - Remove base64-encoded fields

    Args:
        obj: Metadata object to sanitize

    Returns:
        Sanitized metadata

    Examples:
        >>> sanitize_metadata({"imageWidth": 1920})
        {"Image Width": 1920}
        >>> sanitize_metadata({"data": b'\\xff\\x00'})
        {"Data": "ff 00"}
    """
    if obj is None:
        return None

    # Handle bytes - convert to hex string
    if isinstance(obj, bytes):
        return clip_bytes(obj)

    # Handle strings
    if isinstance(obj, str):
        # Try to normalize as datetime first (more specific)
        normalized_dt = normalize_datetime_string(obj)
        if normalized_dt:
            return normalized_dt

        # Try to normalize as date
        normalized_date = normalize_date_string(obj)
        if normalized_date:
            return normalized_date

        # Truncate long strings
        return clip_string(obj)

    # Handle dictionaries
    if isinstance(obj, dict):
        sanitized = {}
        for key, value in obj.items():
            # Convert key to Pretty Case
            pretty_key = pretty_case(key)

            # Recursively sanitize the value
            sanitized_value = sanitize_metadata(value)

            # Only include if value is not None (filters out invalid dates)
            if sanitized_value is not None:
                sanitized[pretty_key] = sanitized_value

        # Remove base64 fields after sanitization
        remove_base64_fields(sanitized)

        return sanitized

    # Handle lists
    if isinstance(obj, list):
        return [
            sanitize_metadata(item)
            for item in obj
            if sanitize_metadata(item) is not None
        ]

    # Handle other types (numbers, booleans, etc.) - pass through
    return obj


def convert_floats_to_decimals(obj: Any) -> Any:
    """
    Convert all float values to decimal string representation.

    Recursively traverses the object and converts all floating-point
    numbers to string representation for DynamoDB compatibility.

    Args:
        obj: Object to transform

    Returns:
        Object with floats converted to strings

    Examples:
        >>> convert_floats_to_decimals({"value": 3.14})
        {"value": "3.14"}
        >>> convert_floats_to_decimals([1.5, 2.7])
        ["1.5", "2.7"]
    """
    if isinstance(obj, float):
        return str(obj)

    if isinstance(obj, dict):
        return {key: convert_floats_to_decimals(value) for key, value in obj.items()}

    if isinstance(obj, list):
        return [convert_floats_to_decimals(item) for item in obj]

    # Pass through other types unchanged
    return obj


def force_all_objects(x: Any) -> Any:
    """
    Wrap all leaf values in {"value": x} structure.

    Recursively transforms the object so that all leaf values
    (non-dict, non-list) are wrapped in a dictionary with a "value" key.
    This ensures DynamoDB compatibility for the MediaLake schema.

    Args:
        x: Value to transform

    Returns:
        Transformed value with all leaves wrapped

    Examples:
        >>> force_all_objects("text")
        {"value": "text"}
        >>> force_all_objects({"key": "val"})
        {"key": {"value": "val"}}
        >>> force_all_objects([1, 2])
        [{"value": 1}, {"value": 2}]
    """
    # If it's a dict, recursively process its values
    if isinstance(x, dict):
        return {key: force_all_objects(value) for key, value in x.items()}

    # If it's a list, recursively process its items
    if isinstance(x, list):
        return [force_all_objects(item) for item in x]

    # For leaf values (anything else), wrap in {"value": x}
    return {"value": x}


def clean_exception_objects(obj: Any) -> Any:
    """
    Remove or convert exception objects that can't be serialized.

    Recursively traverses the object and converts any Exception objects
    to string representations to prevent serialization errors.

    Args:
        obj: Object to clean

    Returns:
        Object with exceptions converted to strings

    Examples:
        >>> clean_exception_objects({"error": KeyError("missing_key")})
        {"error": "KeyError: missing_key"}
    """
    if isinstance(obj, Exception):
        return f"{type(obj).__name__}: {obj}"

    if isinstance(obj, dict):
        return {key: clean_exception_objects(value) for key, value in obj.items()}

    if isinstance(obj, list):
        return [clean_exception_objects(item) for item in obj]

    # Pass through other types unchanged
    return obj


def convert_datetime_objects(obj: Any) -> Any:
    """
    Convert datetime objects to ISO format strings for DynamoDB compatibility.

    Recursively traverses the object and converts all datetime objects
    to ISO format strings that can be stored in DynamoDB.

    Args:
        obj: Object to transform

    Returns:
        Object with datetime objects converted to strings

    Examples:
        >>> from datetime import datetime
        >>> convert_datetime_objects({"date": datetime(2024, 3, 22, 0, 23, 2)})
        {"date": "2024-03-22T00:23:02"}
    """
    if isinstance(obj, datetime):
        return obj.isoformat()

    if isinstance(obj, dict):
        return {key: convert_datetime_objects(value) for key, value in obj.items()}

    if isinstance(obj, list):
        return [convert_datetime_objects(item) for item in obj]

    # Pass through other types unchanged
    return obj


def convert_decimals_for_json(obj: Any) -> Any:
    """
    Convert Decimal objects to regular numbers for JSON serialization.

    Recursively traverses the object and converts all Decimal objects
    to int or float for JSON compatibility.

    Args:
        obj: Object to transform

    Returns:
        Object with Decimals converted to regular numbers

    Examples:
        >>> from decimal import Decimal
        >>> convert_decimals_for_json({"value": Decimal("3.14")})
        {"value": 3.14}
        >>> convert_decimals_for_json([Decimal("1"), Decimal("2.5")])
        [1, 2.5]
    """
    if isinstance(obj, Decimal):
        # Convert to int if it's a whole number, otherwise float
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)

    if isinstance(obj, dict):
        return {key: convert_decimals_for_json(value) for key, value in obj.items()}

    if isinstance(obj, list):
        return [convert_decimals_for_json(item) for item in obj]

    # Pass through other types unchanged
    return obj
