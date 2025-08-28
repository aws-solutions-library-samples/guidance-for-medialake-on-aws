from typing import List

# OpenSearch instance types - can be expanded as needed
VALID_OPENSEARCH_INSTANCE_TYPES: List[str] = [
    "r7g.medium.search",
    "r7g.large.search",
    "r7g.xlarge.search",
    "r7g.2xlarge.search",
    "r7g.4xlarge.search",
    "r7g.8xlarge.search",
    "r6g.medium.search",
    "r6g.large.search",
    "r6g.xlarge.search",
    "r6g.2xlarge.search",
    "r6g.4xlarge.search",
    "r6g.8xlarge.search",
]


def validate_opensearch_instance_type(v: str) -> str:
    """
    Validates if the provided instance type is a valid OpenSearch instance type.

    Args:
        v (str): The instance type to validate

    Returns:
        str: The validated instance type

    Raises:
        ValueError: If the instance type is invalid
    """
    if v not in VALID_OPENSEARCH_INSTANCE_TYPES:
        raise ValueError(
            f"Invalid instance type: {v}. Must be one of: {', '.join(VALID_OPENSEARCH_INSTANCE_TYPES)}"
        )
    return v
