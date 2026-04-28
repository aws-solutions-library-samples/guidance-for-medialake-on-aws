"""PUT /users/{user_id} - Update user details"""

from typing import Any, Dict, List

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from cognito_utils import list_user_groups
from response_utils import error_response, success_response


def _update_user_groups(
    cognito, user_pool_id: str, user_id: str, new_groups: List[str], logger, metrics
) -> Dict[str, Any]:
    """
    Update user group memberships.
    Uses paginated group listing to correctly diff memberships.

    Returns:
        Dict with groups_added, groups_removed, groups_failed
    """
    current_groups = set(list_user_groups(cognito, user_pool_id, user_id, logger))
    new_groups_set = set(new_groups)

    groups_to_add = new_groups_set - current_groups
    groups_to_remove = current_groups - new_groups_set

    groups_added = []
    groups_removed = []
    groups_failed = []

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
            groups_failed.append(
                {
                    "group": group_name,
                    "error_code": e.response["Error"]["Code"],
                    "error_message": e.response["Error"]["Message"],
                    "action": "add",
                }
            )
            logger.error(
                {
                    "message": "Failed to add user to group",
                    "user_id": user_id,
                    "group": group_name,
                    "error": e.response["Error"]["Message"],
                }
            )

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
            groups_failed.append(
                {
                    "group": group_name,
                    "error_code": e.response["Error"]["Code"],
                    "error_message": e.response["Error"]["Message"],
                    "action": "remove",
                }
            )
            logger.error(
                {
                    "message": "Failed to remove user from group",
                    "user_id": user_id,
                    "group": group_name,
                    "error": e.response["Error"]["Message"],
                }
            )

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
        user_attributes = []

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
            cognito.admin_update_user_attributes(
                UserPoolId=user_pool_id,
                Username=user_id,
                UserAttributes=user_attributes,
            )

        response = cognito.admin_get_user(UserPoolId=user_pool_id, Username=user_id)

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

        if "groups" in update_data and isinstance(update_data["groups"], list):
            group_result = _update_user_groups(
                cognito, user_pool_id, user_id, update_data["groups"], logger, metrics
            )
            result["group_changes"] = group_result

        return result

    except cognito.exceptions.UserNotFoundException:
        logger.warning("User not found", extra={"user_id": user_id})
        metrics.add_metric(name="UserNotFound", unit=MetricUnit.Count, value=1)
        raise ValueError("User not found")

    except ClientError as e:
        logger.error("Cognito API error", extra={"error": str(e)})
        metrics.add_metric(name="CognitoAPIError", unit=MetricUnit.Count, value=1)
        raise


def handle_put_user(
    user_id: str, app, cognito, user_pool_id: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Lambda handler to update user details in Cognito User Pool
    """
    try:
        try:
            body = app.current_event.json_body
        except Exception:
            return error_response(400, "Invalid request body")

        if not user_id:
            logger.error("Missing user_id in path parameters")
            metrics.add_metric(
                name="MissingUserIdError", unit=MetricUnit.Count, value=1
            )
            return error_response(400, "Missing user_id parameter")

        logger.info(
            {
                "message": "Processing user update request",
                "user_id": user_id,
                "has_groups": "groups" in body,
            }
        )

        updated_user = _update_cognito_user(
            cognito, user_pool_id, user_id, body, logger, metrics, tracer
        )

        logger.info("Successfully updated user details", extra={"user_id": user_id})
        metrics.add_metric(name="SuccessfulUserUpdate", unit=MetricUnit.Count, value=1)

        return success_response(200, "User details updated successfully", updated_user)

    except ValueError as e:
        if "User not found" in str(e):
            return error_response(404, "User not found")
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")

    except Exception:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")
