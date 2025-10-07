"""PUT /users/{user_id} - Update user details"""

from typing import Any, Dict, List

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    status: str = Field(..., description="Error status code")
    message: str = Field(..., description="Error message")
    data: Dict = Field(default={}, description="Empty data object for errors")


class UserResponse(BaseModel):
    status: str = Field(..., description="Success status code")
    message: str = Field(..., description="Success message")
    data: Dict[str, Any] = Field(..., description="User data from Cognito")


def _get_user_groups(cognito, user_pool_id: str, user_id: str, logger) -> List[str]:
    """Get current groups for a user"""
    try:
        response = cognito.admin_list_groups_for_user(
            UserPoolId=user_pool_id, Username=user_id
        )
        return [group["GroupName"] for group in response.get("Groups", [])]
    except ClientError as e:
        logger.error(
            f"Failed to list user groups", extra={"error": str(e), "user_id": user_id}
        )
        return []


def _update_user_groups(
    cognito, user_pool_id: str, user_id: str, new_groups: List[str], logger, metrics
) -> Dict[str, Any]:
    """
    Update user group memberships

    Returns:
        Dict with groups_added, groups_removed, groups_failed
    """
    # Get current groups
    current_groups = set(_get_user_groups(cognito, user_pool_id, user_id, logger))
    new_groups_set = set(new_groups)

    # Determine which groups to add and remove
    groups_to_add = new_groups_set - current_groups
    groups_to_remove = current_groups - new_groups_set

    groups_added = []
    groups_removed = []
    groups_failed = []

    # Add user to new groups
    for group_name in groups_to_add:
        try:
            cognito.admin_add_user_to_group(
                UserPoolId=user_pool_id, Username=user_id, GroupName=group_name
            )
            groups_added.append(group_name)
            logger.info(
                {
                    "message": "Added user to group",
                    "user_id": user_id,
                    "group": group_name,
                }
            )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            groups_failed.append(
                {
                    "group": group_name,
                    "error_code": error_code,
                    "error_message": error_message,
                    "action": "add",
                }
            )
            logger.error(
                {
                    "message": "Failed to add user to group",
                    "user_id": user_id,
                    "group": group_name,
                    "error": error_message,
                }
            )

    # Remove user from old groups
    for group_name in groups_to_remove:
        try:
            cognito.admin_remove_user_from_group(
                UserPoolId=user_pool_id, Username=user_id, GroupName=group_name
            )
            groups_removed.append(group_name)
            logger.info(
                {
                    "message": "Removed user from group",
                    "user_id": user_id,
                    "group": group_name,
                }
            )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            groups_failed.append(
                {
                    "group": group_name,
                    "error_code": error_code,
                    "error_message": error_message,
                    "action": "remove",
                }
            )
            logger.error(
                {
                    "message": "Failed to remove user from group",
                    "user_id": user_id,
                    "group": group_name,
                    "error": error_message,
                }
            )

    # Log metrics
    if groups_added:
        metrics.add_metric(
            name="GroupsAdded", unit=MetricUnit.Count, value=len(groups_added)
        )
    if groups_removed:
        metrics.add_metric(
            name="GroupsRemoved", unit=MetricUnit.Count, value=len(groups_removed)
        )
    if groups_failed:
        metrics.add_metric(
            name="GroupUpdatesFailed", unit=MetricUnit.Count, value=len(groups_failed)
        )

    return {
        "groups_added": groups_added,
        "groups_removed": groups_removed,
        "groups_failed": groups_failed,
    }


def _update_cognito_user(
    cognito,
    user_pool_id: str,
    user_id: str,
    update_data: Dict[str, Any],
    logger,
    metrics,
    tracer,
) -> Dict[str, Any]:
    """
    Update user attributes in Cognito User Pool
    """
    try:
        # Prepare user attributes for update
        user_attributes = []

        # Map frontend fields to Cognito attributes
        attribute_mapping = {
            "given_name": "given_name",
            "family_name": "family_name",
            "email": "email",
            "phone_number": "phone_number",
        }

        for frontend_field, cognito_attr in attribute_mapping.items():
            if frontend_field in update_data:
                user_attributes.append(
                    {"Name": cognito_attr, "Value": update_data[frontend_field]}
                )

        if user_attributes:
            # Update user attributes
            cognito.admin_update_user_attributes(
                UserPoolId=user_pool_id,
                Username=user_id,
                UserAttributes=user_attributes,
            )

        # Get updated user details
        response = cognito.admin_get_user(UserPoolId=user_pool_id, Username=user_id)

        # Transform Cognito response into a cleaner format
        updated_attributes = {
            attr["Name"]: attr["Value"] for attr in response.get("UserAttributes", [])
        }

        result = {
            "username": response.get("Username"),
            "user_status": response.get("UserStatus"),
            "enabled": response.get("Enabled", False),
            "user_created": response.get("UserCreateDate").isoformat(),
            "last_modified": response.get("UserLastModifiedDate").isoformat(),
            "attributes": updated_attributes,
        }

        # Handle group updates if provided
        if "groups" in update_data and isinstance(update_data["groups"], list):
            group_result = _update_user_groups(
                cognito, user_pool_id, user_id, update_data["groups"], logger, metrics
            )
            result["group_changes"] = group_result

        return result

    except cognito.exceptions.UserNotFoundException:
        logger.warning(f"User not found", extra={"user_id": user_id})
        metrics.add_metric(name="UserNotFound", unit=MetricUnit.Count, value=1)
        raise ValueError("User not found")

    except ClientError as e:
        logger.error(f"Cognito API error", extra={"error": str(e)})
        metrics.add_metric(name="CognitoAPIError", unit=MetricUnit.Count, value=1)
        raise


def _create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Create standardized error response
    """
    error_response = ErrorResponse(status=str(status_code), message=message, data={})

    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": error_response.model_dump_json(),
    }


def handle_put_user(
    user_id: str, app, cognito, user_pool_id: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Lambda handler to update user details in Cognito User Pool
    """
    try:
        # Parse request body
        try:
            body = app.current_event.json_body
        except Exception:
            return _create_error_response(400, "Invalid request body")

        if not user_id:
            logger.error("Missing user_id in path parameters")
            metrics.add_metric(
                name="MissingUserIdError", unit=MetricUnit.Count, value=1
            )
            return _create_error_response(400, "Missing user_id parameter")

        logger.info(
            {
                "message": "Processing user update request",
                "user_id": user_id,
                "has_groups": "groups" in body,
            }
        )

        # Update user attributes and groups in Cognito
        updated_user = _update_cognito_user(
            cognito, user_pool_id, user_id, body, logger, metrics, tracer
        )

        # Create success response
        response = UserResponse(
            status="200",
            message="User details updated successfully",
            data=updated_user,
        )

        logger.info("Successfully updated user details", extra={"user_id": user_id})
        metrics.add_metric(name="SuccessfulUserUpdate", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": response.model_dump_json(),
        }

    except Exception as e:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return _create_error_response(500, str(e))
