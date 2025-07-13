import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize PowerTools with configurable log level
logger = Logger(
    service="user-creation",
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    json_default=str,
)
tracer = Tracer(service="user-creation")
metrics = Metrics(namespace="medialake", service="user-creation")

# Configure CORS
cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=[
        "Content-Type",
        "X-Amz-Date",
        "Authorization",
        "X-Api-Key",
        "X-Amz-Security-Token",
    ],
)

# Initialize API Gateway resolver
app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)

# Initialize Cognito client
cognito = boto3.client("cognito-idp")

# Get environment variables
USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]


@tracer.capture_method
def validate_groups_exist(group_ids: list) -> tuple[list, list]:
    """
    Validate that the specified groups exist in Cognito

    Args:
        group_ids: List of group IDs to validate

    Returns:
        Tuple of (valid_groups, invalid_groups)
    """
    if not group_ids:
        return [], []

    valid_groups = []
    invalid_groups = []

    try:
        # Get all groups in the user pool
        response = cognito.list_groups(UserPoolId=USER_POOL_ID)
        existing_group_names = {
            group["GroupName"] for group in response.get("Groups", [])
        }

        logger.debug(
            {
                "message": "Retrieved existing groups from Cognito",
                "existing_groups": list(existing_group_names),
                "requested_groups": group_ids,
                "operation": "validate_groups_exist",
            }
        )

        for group_id in group_ids:
            if group_id in existing_group_names:
                valid_groups.append(group_id)
            else:
                invalid_groups.append(group_id)

        logger.info(
            {
                "message": "Group validation completed",
                "valid_groups": valid_groups,
                "invalid_groups": invalid_groups,
                "operation": "validate_groups_exist",
            }
        )

    except ClientError as e:
        logger.error(
            {
                "message": "Failed to validate groups",
                "error_code": e.response["Error"]["Code"],
                "error_message": e.response["Error"]["Message"],
                "operation": "validate_groups_exist",
            }
        )
        # If we can't validate, assume all groups are valid and let Cognito handle the errors
        valid_groups = group_ids
        invalid_groups = []

    return valid_groups, invalid_groups


@app.post("/users/user")
@tracer.capture_method
def create_user():
    """Create a new user in Cognito user pool"""
    try:
        # Get request body from the event
        request_data = app.current_event.json_body
        logger.debug(
            {
                "message": "Processing user creation request",
                "request_data": request_data,
                "operation": "create_user",
            }
        )

        # Prepare user attributes with only required fields
        user_attributes = [
            {"Name": "email", "Value": request_data["email"]},
            {"Name": "email_verified", "Value": "true"},
        ]

        # Add optional attributes if they exist
        if "given_name" in request_data:
            user_attributes.append(
                {"Name": "given_name", "Value": request_data["given_name"]}
            )
        if "family_name" in request_data:
            user_attributes.append(
                {"Name": "family_name", "Value": request_data["family_name"]}
            )

        logger.debug(
            {
                "message": "Prepared user attributes",
                "attributes": user_attributes,
                "operation": "attribute_preparation",
            }
        )

        # Create user in Cognito using the configured invitation template
        response = cognito.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=request_data["email"],
            UserAttributes=user_attributes,
            # Remove TemporaryPassword to use the configured invite template
            # MessageAction defaults to "SEND" which will use the invite_message_template
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
            logger.info(
                {
                    "message": "Starting group assignment process",
                    "username": request_data["email"],
                    "total_groups": len(request_data["groups"]),
                    "group_list": request_data["groups"],
                    "operation": "group_assignment_start",
                }
            )

            valid_groups, invalid_groups = validate_groups_exist(request_data["groups"])

            # Log about invalid groups
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
                logger.info(
                    {
                        "message": "Attempting to add user to group",
                        "username": request_data["email"],
                        "group_id": group_id,
                        "operation": "add_user_to_group_attempt",
                    }
                )
                try:
                    cognito.admin_add_user_to_group(
                        UserPoolId=USER_POOL_ID,
                        Username=request_data["email"],
                        GroupName=group_id,
                    )
                    groups_added.append(group_id)
                    logger.info(
                        {
                            "message": "User added to group successfully",
                            "username": request_data["email"],
                            "group_id": group_id,
                            "operation": "add_user_to_group_success",
                        }
                    )
                except ClientError as group_error:
                    error_code = group_error.response["Error"]["Code"]
                    error_message = group_error.response["Error"]["Message"]
                    groups_failed.append(
                        {
                            "group_id": group_id,
                            "error_code": error_code,
                            "error_message": error_message,
                        }
                    )

                    logger.error(
                        {
                            "message": "Failed to add user to group",
                            "username": request_data["email"],
                            "group_id": group_id,
                            "error_code": error_code,
                            "error_message": error_message,
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
                            "error_message": str(unexpected_error),
                            "operation": "add_user_to_group_unexpected_error",
                        }
                    )

            # Final summary of group assignment
            logger.info(
                {
                    "message": "Group assignment process completed",
                    "username": request_data["email"],
                    "groups_added_count": len(groups_added),
                    "groups_failed_count": len(groups_failed),
                    "invalid_groups_count": len(invalid_groups),
                    "groups_added": groups_added,
                    "groups_failed": groups_failed,
                    "invalid_groups": invalid_groups,
                    "operation": "group_assignment_complete",
                }
            )

        # Log success metrics
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

        # Include group assignment details in response
        response_data = {
            "username": request_data["email"],
            "userStatus": response["User"]["UserStatus"],
            "groupsAdded": groups_added,
        }

        # Include failed groups in response if any failed
        if groups_failed:
            response_data["groupsFailed"] = groups_failed
            response_data["groupsFailedCount"] = len(groups_failed)

        # Include invalid groups in response if any were invalid
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

        (
            logger.warning(
                {
                    "message": "Cognito client error during user creation",
                    "error_code": error_code,
                    "error_message": error_message,
                    "user_email": request_data.get("email"),
                    "operation": "cognito_create_user",
                    "status": "failed",
                }
            )
            if error_code in ["UsernameExistsException", "InvalidParameterException"]
            else logger.error(
                {
                    "message": "Severe Cognito client error during user creation",
                    "error_code": error_code,
                    "error_message": error_message,
                    "user_email": request_data.get("email"),
                    "operation": "cognito_create_user",
                    "status": "failed",
                }
            )
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

    except Exception as e:
        logger.error(
            {
                "message": "Unexpected error during user creation",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "create_user",
                "status": "failed",
            }
        )
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


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler"""
    logger.debug(
        {
            "message": "Lambda handler invoked",
            "event": event,
            "operation": "lambda_handler",
        }
    )
    return app.resolve(event, context)
