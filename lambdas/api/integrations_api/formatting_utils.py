"""
Formatting utilities for integrations API.

Functions to format integration data for API responses.
"""

from typing import Any, Dict


def format_integration(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format DynamoDB integration item to API response format.

    Args:
        item: Raw DynamoDB item

    Returns:
        Formatted integration dictionary
    """
    # Use the stored Name field if available, otherwise generate from nodeId
    stored_name = item.get("Name", "")
    if not stored_name:
        # Generate name from nodeId by replacing underscores with spaces and title-casing
        stored_name = item.get("Node", "").replace("_", " ").title()

    # Build the response object
    formatted = {
        "id": item.get("ID", ""),
        "name": stored_name,
        "nodeId": item.get("Node", ""),
        "type": item.get("Type", ""),
        "status": item.get("Status", ""),
        "description": item.get("Description", ""),
        "createdAt": item.get("CreatedDate", ""),
        "updatedAt": item.get("ModifiedDate", ""),
    }

    # Add optional fields
    if "Environment" in item:
        formatted["environment"] = item["Environment"]

    if "Configuration" in item:
        # Return configuration without sensitive data
        config = (
            item["Configuration"].copy()
            if isinstance(item["Configuration"], dict)
            else {}
        )
        # Remove any API keys from credentials if present
        if "auth" in config and "credentials" in config["auth"]:
            if "apiKey" in config["auth"]["credentials"]:  # pragma: allowlist secret
                config["auth"]["credentials"] = {
                    "apiKey": "***"
                }  # pragma: allowlist secret
        formatted["configuration"] = config

    return formatted
