"""GET /users/{user_id} - Get user details"""

from typing import Any, Dict

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from response_utils import error_response, success_response


def _get_cognito_user(
    cognito, user_pool_id: str, user_id: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Fetch user details from Cognito User Pool
    """
    try:
        response = cognito.admin_get_user(UserPoolId=user_pool_id, Username=user_id)

        user_attributes = {
            attr["Name"]: attr["Value"] for attr in response.get("UserAttributes", [])
        }

        return {
            "username": response.get("Username"),
            "user_status": response.get("UserStatus"),
            "enabled": response.get("Enabled", False),
            "user_created": response.get("UserCreateDate").isoformat(),
            "last_modified": response.get("UserLastModifiedDate").isoformat(),
            "attributes": user_attributes,
        }

    except cognito.exceptions.UserNotFoundException:
        logger.warning("User not found", extra={"user_id": user_id})
        metrics.add_metric(name="UserNotFound", unit=MetricUnit.Count, value=1)
        raise

    except ClientError as e:
        logger.error("Cognito API error", extra={"error": str(e)})
        metrics.add_metric(name="CognitoAPIError", unit=MetricUnit.Count, value=1)
        raise


def handle_get_user(
    user_id: str, cognito, user_pool_id: str, logger, metrics, tracer
) -> Dict[str, Any]:
    """
    Lambda handler to fetch user details from Cognito User Pool
    """
    try:
        if not user_id:
            logger.error("Missing user_id in path parameters")
            metrics.add_metric(
                name="MissingUserIdError", unit=MetricUnit.Count, value=1
            )
            return error_response(400, "Missing user_id parameter")

        user_details = _get_cognito_user(
            cognito, user_pool_id, user_id, logger, metrics, tracer
        )

        logger.info("Successfully retrieved user details", extra={"user_id": user_id})
        metrics.add_metric(name="SuccessfulUserLookup", unit=MetricUnit.Count, value=1)

        return success_response(
            200, "User details retrieved successfully", user_details
        )

    except cognito.exceptions.UserNotFoundException:
        return error_response(404, "User not found")

    except Exception:
        logger.exception("Error processing request")
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)
        return error_response(500, "Internal server error")
