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
logger = Logger(service="role-management")
tracer = Tracer(service="role-management")
metrics = Metrics(namespace="RoleManagement")
app = APIGatewayRestResolver()

# Initialize AWS clients with X-Ray tracing
session = boto3.Session()
cognito_idp = session.client("cognito-idp")


@app.post("/roles/<roleId>")
@tracer.capture_method
def create_role(roleId: str) -> Dict[str, Any]:
    """
    Creates a new role in Cognito for the application
    """
    try:
        # Extract data from request body
        request_body = app.current_event.json_body
        role_name = request_body.get("roleName")
        description = request_body.get("description", "")
        permissions = request_body.get("permissions", [])

        if not role_name:
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "roleName is required"}),
            }

        # Create the role in Cognito
        user_pool_id = os.environ["USER_POOL_ID"]

        response = cognito_idp.create_group(
            GroupName=role_name,
            UserPoolId=user_pool_id,
            Description=description,
            Precedence=0,  # You might want to make this configurable
        )

        # Add custom metrics
        metrics.add_metric(name="RoleCreated", unit=MetricUnit.Count, value=1)

        logger.info(f"Successfully created role: {role_name}")

        return {
            "statusCode": 201,
            "body": json.dumps(
                {
                    "message": "Role created successfully",
                    "roleId": response["Group"]["GroupName"],
                    "roleName": role_name,
                    "description": description,
                    "permissions": permissions,
                }
            ),
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        # Add error metrics
        metrics.add_metric(name="RoleCreationError", unit=MetricUnit.Count, value=1)

        logger.error(f"Failed to create role: {error_code} - {error_message}")

        if error_code == "GroupExistsException":
            return {
                "statusCode": 409,
                "body": json.dumps(
                    {"message": "Role already exists", "error": error_message}
                ),
            }

        return {
            "statusCode": 500,
            "body": json.dumps(
                {"message": "Internal server error", "error": error_message}
            ),
        }
    except Exception as e:
        logger.exception("Unexpected error while creating role")
        metrics.add_metric(name="UnexpectedError", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Internal server error", "error": str(e)}),
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Main Lambda handler
    """
    return app.resolve(event, context)
