"""
Sanitization utilities for Step Functions state machine names and IAM roles.
"""

import os
import re

# Get resource prefix from environment
resource_prefix = os.environ.get("RESOURCE_PREFIX", "")


def sanitize_role_name(name: str) -> str:
    """
    Create a sanitized IAM role name from a pipeline name.

    Args:
        name: Name to sanitize

    Returns:
        A sanitized name suitable for IAM roles
    """
    # Convert to lowercase
    sanitized_name = name.lower()

    # Replace spaces with hyphens
    sanitized_name = sanitized_name.replace(" ", "-")

    # Replace non-alphanumeric characters (except allowed special chars) with underscores
    sanitized_name = re.sub(r"[^a-z0-9+=,.@_-]", "_", sanitized_name)

    # Ensure the name starts with a letter or allowed character
    sanitized_name = re.sub(r"^[^a-z0-9+=,.@_-]+", "", sanitized_name)

    # Truncate to 64 characters (maximum length for IAM role names)
    sanitized_name = sanitized_name[:64]

    # Ensure the name doesn't end with a hyphen or underscore
    sanitized_name = re.sub(r"[-_]+$", "", sanitized_name)

    return sanitized_name


def sanitize_state_machine_name(name: str) -> str:
    """
    Create a sanitized state machine name from a pipeline name.

    Args:
        name: Name to sanitize

    Returns:
        A sanitized name suitable for AWS Step Functions state machines
    """
    # Replace spaces with hyphens
    sanitized_name = name.replace(" ", "-")

    # Replace non-alphanumeric characters (except hyphens) with underscores
    sanitized_name = re.sub(r"[^a-zA-Z0-9-]", "_", sanitized_name)

    # Ensure the name starts with a letter or number
    sanitized_name = re.sub(r"^[^a-zA-Z0-9]+", "", sanitized_name)

    # Truncate to 80 characters (maximum length for Step Function names)
    sanitized_name = sanitized_name[:80]

    # Ensure the name doesn't end with a hyphen or underscore
    sanitized_name = re.sub(r"[-_]+$", "", sanitized_name)

    return f"{resource_prefix}_{sanitized_name}_pipeline"


def sanitize_state_name(name: str, node_id: str) -> str:
    """
    Create a sanitized state name for a Step Functions state.

    Args:
        name: The original name (typically node label)
        node_id: The node ID to ensure uniqueness

    Returns:
        A sanitized state name suitable for Step Functions states
    """
    # Create a unique state name that combines the name and node ID
    unique_state_name = f"{name} ({node_id})"

    # Sanitize the state name to ensure it's valid for Step Functions
    # Remove special characters and spaces that might cause issues
    sanitized_state_name = "".join(c if c.isalnum() else "_" for c in unique_state_name)

    # Ensure it starts with a letter or number
    if not sanitized_state_name[0].isalnum():
        sanitized_state_name = "state_" + sanitized_state_name

    return sanitized_state_name
