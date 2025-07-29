import datetime
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
logger = Logger(service="update-role-service")
tracer = Tracer(service="update-role-service")
metrics = Metrics(namespace="MediaLake", service="update-role-service")
app = APIGatewayRestResolver()

# Initialize AWS clients with X-Ray tracing
session = boto3.Session()
dynamodb = session.resource("dynamodb")


@app.put("/roles/<role_id>")
@tracer.capture_method
def update_role(role_id: str) -> Dict[str, Any]:
    """
    Update a role in DynamoDB

    Args:
        role_id: The unique identifier of the role to update

    Returns:
        Dict containing the updated role information
    """
    try:
        # Extract data from request body
        request_body = app.current_event.json_body

        # Get the DynamoDB table
        table_name = os.environ.get("MEDIALAKE_ROLES_TABLE").split("/")[-1]
        table = dynamodb.Table(table_name)

        # Check if the role exists
        response = table.get_item(Key={"id": role_id})
        if "Item" not in response:
            logger.warning(f"Role not found: {role_id}")
            return {
                "statusCode": 404,
                "body": {"status": "error", "message": f"Role {role_id} not found"},
            }

        response["Item"]
        current_time = datetime.datetime.utcnow().isoformat()

        # Update role fields if they exist in the request
        updates = {}
        if "name" in request_body:
            updates["name"] = request_body["name"]
        if "description" in request_body:
            updates["description"] = request_body["description"]
        if "permissions" in request_body:
            updates["permissions"] = request_body["permissions"]

        # Add updatedAt timestamp
        updates["updatedAt"] = current_time

        # Build update expression
        update_expression = "SET "
        expression_attribute_values = {}

        for key, value in updates.items():
            update_expression += f"{key} = :{key}, "
            expression_attribute_values[f":{key}"] = value

        # Remove trailing comma and space
        update_expression = update_expression[:-2]

        # Update the item in DynamoDB
        response = table.update_item(
            Key={"id": role_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="ALL_NEW",
        )

        updated_role = response.get("Attributes", {})

        # Add custom metrics
        metrics.add_metric(name="SuccessfulRoleUpdates", unit=MetricUnit.Count, value=1)
        logger.info(f"Successfully updated role: {role_id}")

        return {
            "statusCode": 200,
            "body": {
                "status": "success",
                "message": "Role updated successfully",
                "data": {"role": updated_role},
            },
        }

    except ClientError as e:
        error_message = e.response.get("Error", {}).get("Message", str(e))

        # Add error metrics
        metrics.add_metric(name="FailedRoleUpdates", unit=MetricUnit.Count, value=1)
        logger.error(f"Error updating role {role_id}: {error_message}")

        return {
            "statusCode": 500,
            "body": {
                "status": "error",
                "message": "Internal server error while updating role",
            },
        }

    except Exception:
        # Add error metrics
        metrics.add_metric(name="UnhandledErrors", unit=MetricUnit.Count, value=1)
        logger.exception(f"Unexpected error while updating role {role_id}")

        return {
            "statusCode": 500,
            "body": {
                "status": "error",
                "message": "Internal server error while updating role",
            },
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for role update endpoint
    """
    try:
        return app.resolve(event, context)
    except Exception:
        logger.exception("Error processing request")
        return {
            "statusCode": 500,
            "body": {"status": "error", "message": "Internal server error"},
        }
