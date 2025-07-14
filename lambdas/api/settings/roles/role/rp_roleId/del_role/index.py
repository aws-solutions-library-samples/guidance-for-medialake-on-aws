import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize Power Tools
logger = Logger(service="delete-role-service")
tracer = Tracer(service="delete-role-service")
metrics = Metrics(namespace="MediaLake", service="delete-role-service")
app = APIGatewayRestResolver()

# Initialize AWS clients with X-Ray tracing
session = boto3.Session()
cognito_idp = session.client("cognito-idp")


@app.delete("/settings/roles/role/<role_id>")
@tracer.capture_method
def delete_role(role_id: str) -> Dict[str, Any]:
    """
    Delete a Cognito role from the user pool

    Args:
        role_id: The unique identifier of the role to delete

    Returns:
        Dict containing status of the deletion
    """
    try:
        # Get the User Pool ID from environment variables
        user_pool_id = os.environ["USER_POOL_ID"]

        # Delete the role from Cognito
        cognito_idp.delete_group(GroupName=role_id, UserPoolId=user_pool_id)

        # Add custom metrics
        metrics.add_metric(
            name="SuccessfulRoleDeletions", unit=MetricUnit.Count, value=1
        )

        logger.info(f"Successfully deleted role: {role_id}")
        return {
            "statusCode": 200,
            "body": {"message": f"Role {role_id} successfully deleted"},
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        # Add error metrics
        metrics.add_metric(name="FailedRoleDeletions", unit=MetricUnit.Count, value=1)

        if error_code == "ResourceNotFoundException":
            logger.warning(f"Role not found: {role_id}")
            return {"statusCode": 404, "body": {"message": f"Role {role_id} not found"}}

        logger.error(
            f"Error deleting role {role_id}: {error_message}",
            extra={"error_code": error_code},
        )
        return {
            "statusCode": 500,
            "body": {"message": "Internal server error while deleting role"},
        }

    except Exception:
        # Add error metrics
        metrics.add_metric(name="UnhandledErrors", unit=MetricUnit.Count, value=1)

        logger.exception(f"Unexpected error while deleting role {role_id}")
        return {
            "statusCode": 500,
            "body": {"message": "Internal server error while deleting role"},
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for role deletion endpoint
    """
    try:
        return app.resolve(event, context)
    except Exception:
        logger.exception("Error processing request")
        return {"statusCode": 500, "body": {"message": "Internal server error"}}
