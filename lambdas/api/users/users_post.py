"""POST /users - Create a new user"""

import json
from typing import Any, Dict, List, Tuple

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from cognito_utils import list_all_groups


def _validate_groups_exist(
    cognito, user_pool_id: str, group_ids: List[str], logger, tracer
) -> Tuple[List[str], List[str]]:
    """
    Validate that the specified groups exist in Cognito.
    Uses paginated listing to handle pools with 60+ groups.

    Returns:
        Tuple of (valid_groups, invalid_groups)
    """
    if not group_ids:
        return [], []

    try:
        existing_group_names = list_all_groups(cognito, user_pool_id, logger)

        valid_groups = [g for g in group_ids if g in existing_group_names]
        invalid_groups = [g for g in group_ids if g not in existing_group_names]

        logger.info(
            {
                "message": "Group validation completed",
                "valid_groups": valid_groups,
                "invalid_groups": invalid_groups,
                "operation": "validate_groups_exist",
            }
        )

        return valid_groups, invalid_groups

    except ClientError as e:
        logger.warning(
            {
                "message": "list_all_groups validation failed, falling back to assuming all groups valid",
                "error": str(e),
                "group_ids": group_ids,
                "operation": "validate_groups_exist",
            }
        )
        return list(group_ids), []


def handle_create_user(
    app, cognito, user_pool_id: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """Create a new user in Cognito user pool"""
    try:
        request_data = app.current_event.json_body
        logger.debug(
            {
                "message": "Processing user creation request",
                "operation": "create_user",
            }
        )

        # Prepare user attributes with only required fields
        user_attributes = [
            {"Name": "email", "Value": request_data["email"]},
            {"Name": "email_verified", "Value": "true"},
        ]

        if "given_name" in request_data:
            user_attributes.append(
                {"Name": "given_name", "Value": request_data["given_name"]}
            )
        if "family_name" in request_data:
            user_attributes.append(
                {"Name": "family_name", "Value": request_data["family_name"]}
            )

        # Create user in Cognito using the configured invitation template
        response = cognito.admin_create_user(
            UserPoolId=user_pool_id,
            Username=request_data["email"],
            UserAttributes=user_attributes,
        )
        logger.info(
            {
                "message": "User created successfully in Cognito",
                "username": request_data["email"],
                "user_status": response["User"]["UserStatus"],
                "operation": "cognito_create_user",
            }
        )

        # Add user to groups if specified
        groups_added = []
        groups_failed = []
        invalid_groups = []
        if "groups" in request_data and request_data["groups"]:
            valid_groups, invalid_groups = _validate_groups_exist(
                cognito, user_pool_id, request_data["groups"], logger, tracer
            )

            if invalid_groups:
                logger.warning(
                    {
                        "message": "Some groups do not exist in Cognito",
                        "username": request_data["email"],
                        "invalid_groups": invalid_groups,
                        "operation": "invalid_groups_detected",
                    }
                )

            for group_id in valid_groups:
                try:
                    cognito.admin_add_user_to_group(
                        UserPoolId=user_pool_id,
                        Username=request_data["email"],
                        GroupName=group_id,
                    )
                    groups_added.append(group_id)
                except ClientError as group_error:
                    groups_failed.append(
                        {
                            "group_id": group_id,
                            "error_code": group_error.response["Error"]["Code"],
                            "error_message": group_error.response["Error"]["Message"],
                        }
                    )
                    logger.error(
                        {
                            "message": "Failed to add user to group",
                            "username": request_data["email"],
                            "group_id": group_id,
                            "error_code": group_error.response["Error"]["Code"],
                            "operation": "add_user_to_group_failed",
                        }
                    )
                except Exception as unexpected_error:
                    groups_failed.append(
                        {
                            "group_id": group_id,
                            "error_code": "UnexpectedError",
                            "error_message": str(unexpected_error),
                        }
                    )
                    logger.error(
                        {
                            "message": "Unexpected error adding user to group",
                            "username": request_data["email"],
                            "group_id": group_id,
                            "error_type": type(unexpected_error).__name__,
                            "operation": "add_user_to_group_unexpected_error",
                        }
                    )

        # Log metrics
        metrics.add_metric(
            name="SuccessfulUserCreations", unit=MetricUnit.Count, value=1
        )
        if groups_added:
            metrics.add_metric(
                name="UserGroupAssignments",
                unit=MetricUnit.Count,
                value=len(groups_added),
            )
        if groups_failed:
            metrics.add_metric(
                name="FailedGroupAssignments",
                unit=MetricUnit.Count,
                value=len(groups_failed),
            )
        if invalid_groups:
            metrics.add_metric(
                name="InvalidGroupsRequested",
                unit=MetricUnit.Count,
                value=len(invalid_groups),
            )

        # Build response data (preserving existing API contract)
        response_data = {
            "username": request_data["email"],
            "userStatus": response["User"]["UserStatus"],
            "groupsAdded": groups_added,
        }
        if groups_failed:
            response_data["groupsFailed"] = groups_failed
            response_data["groupsFailedCount"] = len(groups_failed)
        if invalid_groups:
            response_data["invalidGroups"] = invalid_groups
            response_data["invalidGroupsCount"] = len(invalid_groups)

        return {
            "statusCode": 201,
            "body": json.dumps(
                {
                    "status": 201,
                    "message": "User created successfully",
                    "data": response_data,
                }
            ),
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        if error_code in ["UsernameExistsException", "InvalidParameterException"]:
            logger.warning(
                {
                    "message": "Cognito client error during user creation",
                    "error_code": error_code,
                    "operation": "cognito_create_user",
                }
            )
        else:
            logger.error(
                {
                    "message": "Severe Cognito client error during user creation",
                    "error_code": error_code,
                    "error_message": error_message,
                    "operation": "cognito_create_user",
                }
            )

        metrics.add_metric(name="FailedUserCreations", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": (
                400
                if error_code
                in ["UsernameExistsException", "InvalidParameterException"]
                else 500
            ),
            "body": json.dumps({"error": error_code, "message": error_message}),
        }

    except Exception:
        logger.exception("Unexpected error during user creation")
        metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred",
                }
            ),
        }
