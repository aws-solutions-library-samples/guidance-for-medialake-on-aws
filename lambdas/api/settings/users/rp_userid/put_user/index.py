import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize PowerTools
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="medialake")
app = APIGatewayRestResolver()

# Initialize Cognito client
cognito = boto3.client("cognito-idp")


class ValidationError(Exception):
    pass


@tracer.capture_method
def validate_input(body: Dict[str, Any]) -> None:
    """Validate the input payload"""
    required_fields = ["email", "given_name", "family_name"]

    if not isinstance(body, dict):
        raise ValidationError("Request body must be a JSON object")

    for field in required_fields:
        if field not in body:
            raise ValidationError(f"Missing required field: {field}")

    if "email" in body and not isinstance(body["email"], str):
        raise ValidationError("Email must be a string")


@tracer.capture_method
def update_cognito_user(
    user_id: str, attributes: Dict[str, str], user_pool_id: str
) -> Dict[str, Any]:
    """Update user attributes in Cognito"""
    try:
        user_attributes = [
            {"Name": key, "Value": value} for key, value in attributes.items()
        ]

        response = cognito.admin_update_user_attributes(
            UserPoolId=user_pool_id, Username=user_id, UserAttributes=user_attributes
        )

        return response

    except ClientError as e:
        logger.error(f"Failed to update Cognito user: {str(e)}")
        raise


@app.put("/users/<user_id>")
@tracer.capture_method
def update_user(user_id: str):
    """Handle PUT request to update user"""
    try:
        # Get user pool ID from environment variable
        user_pool_id = os.environ["USER_POOL_ID"]

        # Parse and validate request body
        body = app.current_event.json_body
        validate_input(body)

        # Prepare user attributes
        attributes = {
            "email": body["email"],
            "given_name": body["given_name"],
            "family_name": body["family_name"],
        }

        if "phone_number" in body:
            attributes["phone_number"] = body["phone_number"]

        # Update user in Cognito
        update_cognito_user(user_id, attributes, user_pool_id)

        metrics.add_metric(name="SuccessfulUserUpdates", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {"message": "User updated successfully", "userId": user_id}
            ),
        }

    except ValidationError as e:
        logger.warning(f"Validation error: {str(e)}")
        metrics.add_metric(name="ValidationErrors", unit=MetricUnit.Count, value=1)
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

    except ClientError as e:
        logger.error(f"Cognito error: {str(e)}")
        metrics.add_metric(name="CognitoErrors", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to update user"}),
        }

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler"""
    return app.resolve(event, context)
