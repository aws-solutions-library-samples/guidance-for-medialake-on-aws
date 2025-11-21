"""
Sanitization utilities for Step Functions state machine names and IAM roles.
"""

import os
import re

from aws_lambda_powertools import Logger

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

    # Ensure the name doesn't end with a hyphen or underscore before truncating
    sanitized_name = re.sub(r"[-_]+$", "", sanitized_name)

    # Truncate to 64 characters (maximum length for IAM role names)
    sanitized_name = sanitized_name[:64]

    # Final cleanup - ensure no trailing hyphens or underscores after truncation
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

    AWS Step Functions enforces an 80-character limit on state names.
    This function ensures the name is valid and within the limit while
    maintaining uniqueness through the node_id suffix.

    Args:
        name: The original name (typically node label)
        node_id: The node ID to ensure uniqueness

    Returns:
        A sanitized state name suitable for Step Functions states (max 80 chars)
    """
    logger = Logger()

    # AWS Step Functions has an 80-character limit for state names
    max_length = 80

    # Sanitize the node_id part first
    sanitized_node_id = "".join(c if c.isalnum() else "_" for c in node_id)

    # Reserve space for the node_id suffix (including separators)
    # Format will be: "name_part__node_id_"
    node_id_suffix = f"__{sanitized_node_id}_"
    reserved_space = len(node_id_suffix)

    # Sanitize the descriptive name part
    # Remove special characters and spaces that might cause issues
    sanitized_name = "".join(c if c.isalnum() else "_" for c in name)

    # Remove consecutive underscores to reduce length
    while "__" in sanitized_name:
        sanitized_name = sanitized_name.replace("__", "_")

    # Remove leading/trailing underscores
    sanitized_name = sanitized_name.strip("_")

    # Ensure it starts with a letter or number, add prefix if needed
    prefix = ""
    if sanitized_name and not sanitized_name[0].isalnum():
        prefix = "state_"
        sanitized_name = sanitized_name.lstrip("_")
    elif not sanitized_name:
        prefix = "state_"

    # Calculate available space for the descriptive name part (including prefix)
    available_space = max_length - reserved_space - len(prefix)

    # Truncate the name part if necessary
    if len(sanitized_name) > available_space:
        original_length = len(sanitized_name)
        sanitized_name = sanitized_name[:available_space]
        logger.info(
            f"Truncated state name from {original_length} to {len(sanitized_name)} characters "
            f"to fit 80-char limit. Original: '{name}', Node ID: '{node_id}'"
        )

    # Combine the parts
    sanitized_state_name = f"{prefix}{sanitized_name}{node_id_suffix}"

    # Final verification and safety check
    if len(sanitized_state_name) > max_length:
        logger.warning(
            f"State name '{sanitized_state_name}' ({len(sanitized_state_name)} chars) still exceeds {max_length} chars. "
            f"Applying emergency truncation. Original: '{name}', Node ID: '{node_id}'"
        )
        # Emergency truncation: Keep only the suffix to ensure uniqueness
        # and fit as much of the name as possible
        available_for_name = max_length - reserved_space - len(prefix)
        sanitized_name = sanitized_name[:available_for_name]
        sanitized_state_name = f"{prefix}{sanitized_name}{node_id_suffix}"

    # Absolute final check - this should never trigger but ensures correctness
    if len(sanitized_state_name) > max_length:
        logger.error(
            f"CRITICAL: State name '{sanitized_state_name}' ({len(sanitized_state_name)} chars) "
            f"STILL exceeds {max_length} chars after all processing. Forcing truncation."
        )
        sanitized_state_name = sanitized_state_name[:max_length]

    return sanitized_state_name
