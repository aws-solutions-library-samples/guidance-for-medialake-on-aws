"""Validation utilities for collections API."""

import re
from typing import Any, Dict, List

from aws_lambda_powertools import Logger

logger = Logger(service="validation-utils")

# Allowed Material-UI icon names
ALLOWED_ICONS = [
    "Folder",
    "FolderOpen",
    "Work",
    "Campaign",
    "Assignment",
    "Archive",
    "PhotoLibrary",
    "Collections",
    "Category",
    "Label",
    "Bookmarks",
    "Star",
    "Favorite",
    "Inventory",
    "Storage",
    "Dashboard",
]

# Hex color pattern
HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


def validate_hex_color(color: str) -> bool:
    """
    Validate hex color format.

    Args:
        color: Color string to validate

    Returns:
        True if valid hex color
    """
    if not color:
        return False
    return bool(HEX_COLOR_PATTERN.match(color))


def validate_icon_name(icon: str) -> bool:
    """
    Validate icon name is in allowed list.

    Args:
        icon: Icon name to validate

    Returns:
        True if valid icon name
    """
    if not icon:
        return False
    return icon in ALLOWED_ICONS


def validate_collection_type_data(
    data: Dict[str, Any], is_update: bool = False
) -> List[Dict[str, str]]:
    """
    Validate collection type data and return list of validation errors.

    Args:
        data: Collection type data to validate
        is_update: Whether this is an update operation (makes fields optional)

    Returns:
        List of validation error dictionaries with field, message, code
    """
    errors = []

    # Required fields for creation
    if not is_update:
        required_fields = {
            "name": "Name is required",
            "color": "Color is required",
            "icon": "Icon is required",
        }

        for field, message in required_fields.items():
            if not data.get(field):
                errors.append(
                    {"field": field, "message": message, "code": "REQUIRED_FIELD"}
                )

    # Name validation
    if "name" in data:
        name = data["name"]
        if name:
            if len(name.strip()) < 1:
                errors.append(
                    {
                        "field": "name",
                        "message": "Name must not be empty",
                        "code": "MIN_LENGTH",
                    }
                )
            elif len(name) > 50:
                errors.append(
                    {
                        "field": "name",
                        "message": "Name must not exceed 50 characters",
                        "code": "MAX_LENGTH",
                    }
                )

    # Description validation
    if "description" in data and data["description"]:
        description = data["description"]
        if len(description) > 255:
            errors.append(
                {
                    "field": "description",
                    "message": "Description must not exceed 255 characters",
                    "code": "MAX_LENGTH",
                }
            )

    # Color validation
    if "color" in data:
        color = data["color"]
        if color and not validate_hex_color(color):
            errors.append(
                {
                    "field": "color",
                    "message": "Must be valid hex color format (#RRGGBB)",
                    "code": "INVALID_FORMAT",
                }
            )

    # Icon validation
    if "icon" in data:
        icon = data["icon"]
        if icon and not validate_icon_name(icon):
            errors.append(
                {
                    "field": "icon",
                    "message": f"Must be one of: {', '.join(ALLOWED_ICONS)}",
                    "code": "INVALID_VALUE",
                }
            )

    if errors:
        logger.warning(
            "Validation errors found", extra={"errors": errors, "data": data}
        )

    return errors
