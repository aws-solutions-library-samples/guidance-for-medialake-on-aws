"""Shared Cognito utilities for user service handlers."""

from typing import List, Set

from botocore.exceptions import ClientError


def list_all_groups(cognito, user_pool_id: str, logger) -> Set[str]:
    """
    List all group names in a Cognito user pool, handling pagination.

    Args:
        cognito: boto3 cognito-idp client
        user_pool_id: The user pool ID
        logger: Logger instance

    Returns:
        Set of all group names
    """
    group_names: Set[str] = set()
    params = {"UserPoolId": user_pool_id}

    try:
        while True:
            response = cognito.list_groups(**params)
            for group in response.get("Groups", []):
                group_names.add(group["GroupName"])

            next_token = response.get("NextToken")
            if not next_token:
                break
            params["NextToken"] = next_token
    except ClientError as e:
        logger.error(
            {
                "message": "Failed to list groups from Cognito",
                "error_code": e.response["Error"]["Code"],
                "error_message": e.response["Error"]["Message"],
                "operation": "list_all_groups",
            }
        )
        raise

    return group_names


def list_user_groups(cognito, user_pool_id: str, user_id: str, logger) -> List[str]:
    """
    List all groups a user belongs to, handling pagination.

    Args:
        cognito: boto3 cognito-idp client
        user_pool_id: The user pool ID
        user_id: The username / user ID
        logger: Logger instance

    Returns:
        List of group names the user belongs to
    """
    groups: List[str] = []
    params = {"UserPoolId": user_pool_id, "Username": user_id}

    try:
        while True:
            response = cognito.admin_list_groups_for_user(**params)
            for group in response.get("Groups", []):
                groups.append(group["GroupName"])

            next_token = response.get("NextToken")
            if not next_token:
                break
            params["NextToken"] = next_token
    except ClientError as e:
        logger.error(
            {
                "message": "Failed to list user groups",
                "error_code": e.response["Error"]["Code"],
                "error_message": e.response["Error"]["Message"],
                "user_id": user_id,
                "operation": "list_user_groups",
            }
        )
        return []

    return groups
