"""XML parsing utilities for the Generic XML normalizer.

This module provides helper functions for parsing XML structures that have been
converted to dictionaries (typically via xmltodict or similar libraries).

Key features:
- Handle nested elements (actors/actor, ratings/Rating, etc.)
- Handle single item vs list variations
- Safely extract values from nested structures
- Handle XML attribute conventions (@attr, #text)

These utilities are used by the GenericXmlNormalizer and field mappers to
consistently handle the various XML-to-dict conversion patterns.
"""

from typing import Any


def ensure_list(value: Any) -> list[Any]:
    """Ensure a value is a list, wrapping single items if needed.

    XML-to-dict converters often produce a dict for single items and a list
    for multiple items. This function normalizes to always return a list.

    Args:
        value: Any value - could be None, a dict, a list, or a scalar.

    Returns:
        A list containing the value(s). Empty list if value is None.

    Examples:
        >>> ensure_list(None)
        []
        >>> ensure_list({"name": "John"})
        [{'name': 'John'}]
        >>> ensure_list([{"name": "John"}, {"name": "Jane"}])
        [{'name': 'John'}, {'name': 'Jane'}]
        >>> ensure_list("simple_value")
        ['simple_value']
    """
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def get_nested_value(
    data: dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    """Safely get a nested value from a dictionary.

    Traverses nested dictionaries using the provided keys.
    Returns default if any key is not found or if a non-dict is encountered.

    Args:
        data: The dictionary to traverse.
        *keys: Variable number of keys to traverse.
        default: Value to return if path not found.

    Returns:
        The value at the nested path, or default if not found.

    Examples:
        >>> data = {"a": {"b": {"c": "value"}}}
        >>> get_nested_value(data, "a", "b", "c")
        'value'
        >>> get_nested_value(data, "a", "x", "c", default="not_found")
        'not_found'
        >>> get_nested_value(data, "a", "b")
        {'c': 'value'}
    """
    current = data

    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default

    return current


def get_text_content(element: Any) -> str | None:
    """Extract text content from an XML element dict.

    XML elements with text content are typically represented as:
    - {"#text": "value", "@attr": "attr_value"} for elements with attributes
    - "value" for simple text elements

    Args:
        element: The element value - could be a dict with #text, or a string.

    Returns:
        The text content as a string, or None if not found/empty.

    Examples:
        >>> get_text_content({"#text": "Hello", "@lang": "en"})
        'Hello'
        >>> get_text_content("Simple text")
        'Simple text'
        >>> get_text_content({"@attr": "value"})  # No text content
        None
        >>> get_text_content(None)
        None
    """
    if element is None:
        return None

    # If it's a string, return it directly
    if isinstance(element, str):
        stripped = element.strip()
        return stripped if stripped else None

    # If it's a dict, look for #text
    if isinstance(element, dict):
        text = element.get("#text")
        if text is not None:
            text_str = str(text).strip()
            return text_str if text_str else None

    # For other types, try to convert to string
    if element is not None:
        text_str = str(element).strip()
        return text_str if text_str else None

    return None


def get_attribute(
    element: dict[str, Any],
    attr_name: str,
    default: Any = None,
) -> Any:
    """Get an XML attribute from an element dict.

    XML attributes are typically prefixed with @ in dict representations.
    This function handles both @attr and attr formats.

    Args:
        element: The element dictionary.
        attr_name: The attribute name (with or without @ prefix).
        default: Value to return if attribute not found.

    Returns:
        The attribute value, or default if not found.

    Examples:
        >>> element = {"@type": "movie", "@id": "123", "#text": "Title"}
        >>> get_attribute(element, "@type")
        'movie'
        >>> get_attribute(element, "type")  # Also works without @
        'movie'
        >>> get_attribute(element, "missing", "default")
        'default'
    """
    if not isinstance(element, dict):
        return default

    # Try with @ prefix first
    if attr_name.startswith("@"):
        value = element.get(attr_name)
        if value is not None:
            return value
        # Try without @ prefix
        return element.get(attr_name[1:], default)
    else:
        # Try without @ prefix first
        value = element.get(attr_name)
        if value is not None:
            return value
        # Try with @ prefix
        return element.get(f"@{attr_name}", default)


def extract_child_elements(
    parent: dict[str, Any],
    container_name: str,
    child_name: str | None = None,
) -> list[dict[str, Any]]:
    """Extract child elements from a container structure.

    Handles common XML-to-dict patterns:
    - {"actors": {"actor": [...]}} → list of actor dicts
    - {"actors": {"actor": {...}}} → list with single actor dict
    - {"actors": [...]} → list directly under container
    - {"actors": {...}} → single item directly under container

    Args:
        parent: The parent dictionary containing the container.
        container_name: Name of the container element (e.g., "actors").
        child_name: Name of child elements (e.g., "actor"). If None,
                   defaults to singular form of container_name.

    Returns:
        List of child element dictionaries.

    Examples:
        >>> parent = {"actors": {"actor": [{"name": "John"}, {"name": "Jane"}]}}
        >>> extract_child_elements(parent, "actors", "actor")
        [{'name': 'John'}, {'name': 'Jane'}]

        >>> parent = {"actors": {"actor": {"name": "John"}}}
        >>> extract_child_elements(parent, "actors", "actor")
        [{'name': 'John'}]

        >>> parent = {"actors": [{"name": "John"}]}
        >>> extract_child_elements(parent, "actors")
        [{'name': 'John'}]
    """
    if not isinstance(parent, dict):
        return []

    container = parent.get(container_name)
    if container is None:
        return []

    # Determine child element name
    if child_name is None:
        # Default to singular form (remove trailing 's')
        child_name = container_name.rstrip("s")

    # If container is a list, return it directly
    if isinstance(container, list):
        return [item for item in container if isinstance(item, dict)]

    # If container is a dict, look for child elements
    if isinstance(container, dict):
        children = container.get(child_name)
        if children is not None:
            return ensure_list(children)

        # Container might be the child element itself
        # (when there's only one child and no wrapper)
        return [container]

    return []


def parse_boolean(value: Any, default: bool = False) -> bool:
    """Parse a boolean value from various representations.

    Handles common boolean representations in XML:
    - "true", "True", "TRUE", "yes", "Yes", "YES", "1", "Y", "y"
    - "false", "False", "FALSE", "no", "No", "NO", "0", "N", "n"
    - Python bool values

    Args:
        value: The value to parse.
        default: Default value if parsing fails.

    Returns:
        Boolean value.

    Examples:
        >>> parse_boolean("true")
        True
        >>> parse_boolean("FALSE")
        False
        >>> parse_boolean("yes")
        True
        >>> parse_boolean("1")
        True
        >>> parse_boolean(None, default=False)
        False
    """
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    value_str = str(value).strip().lower()

    if value_str in ("true", "yes", "1", "y"):
        return True
    if value_str in ("false", "no", "0", "n"):
        return False

    return default


def parse_int(value: Any, default: int | None = None) -> int | None:
    """Parse an integer value from various representations.

    Args:
        value: The value to parse.
        default: Default value if parsing fails.

    Returns:
        Integer value, or default if parsing fails.

    Examples:
        >>> parse_int("123")
        123
        >>> parse_int(456)
        456
        >>> parse_int("invalid", default=0)
        0
        >>> parse_int(None)
        None
    """
    if value is None:
        return default

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return default


def parse_float(value: Any, default: float | None = None) -> float | None:
    """Parse a float value from various representations.

    Args:
        value: The value to parse.
        default: Default value if parsing fails.

    Returns:
        Float value, or default if parsing fails.

    Examples:
        >>> parse_float("123.45")
        123.45
        >>> parse_float(456)
        456.0
        >>> parse_float("invalid", default=0.0)
        0.0
    """
    if value is None:
        return default

    if isinstance(value, float):
        return value

    if isinstance(value, int):
        return float(value)

    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return default


def flatten_single_item_lists(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively flatten single-item lists in a dictionary.

    Some XML-to-dict converters always produce lists even for single items.
    This function converts single-item lists to their contained value.

    Note: This modifies the dictionary in place and returns it.

    Args:
        data: Dictionary to process.

    Returns:
        The same dictionary with single-item lists flattened.

    Examples:
        >>> data = {"items": [{"name": "single"}], "multi": [1, 2, 3]}
        >>> flatten_single_item_lists(data)
        {'items': {'name': 'single'}, 'multi': [1, 2, 3]}
    """
    if not isinstance(data, dict):
        return data

    for key, value in data.items():
        if isinstance(value, list) and len(value) == 1:
            data[key] = value[0]
            # Recursively process if the item is a dict
            if isinstance(data[key], dict):
                flatten_single_item_lists(data[key])
        elif isinstance(value, dict):
            flatten_single_item_lists(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    flatten_single_item_lists(item)

    return data


def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge two dictionaries, with override values taking precedence.

    Performs a shallow merge - nested dicts are replaced, not merged.

    Args:
        base: Base dictionary.
        override: Dictionary with values to override.

    Returns:
        New dictionary with merged values.

    Examples:
        >>> base = {"a": 1, "b": 2}
        >>> override = {"b": 3, "c": 4}
        >>> merge_dicts(base, override)
        {'a': 1, 'b': 3, 'c': 4}
    """
    result = base.copy()
    result.update(override)
    return result
