import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    InternalServerError,
    NotFoundError,
)
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")
secretsmanager = boto3.client("secretsmanager")

# Initialize Powertools
logger = Logger(service="delete_integration")
tracer = Tracer(service="delete_integration")
metrics = Metrics(namespace="Integrations", service="delete_integration")

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

# API Gateway event handler
app = APIGatewayRestResolver(cors=cors_config)


@tracer.capture_method
def delete_api_key_secret(secret_arn: str) -> None:
    """
    Delete API key from Secrets Manager
    """
    try:
        secretsmanager.delete_secret(
            SecretId=secret_arn, ForceDeleteWithoutRecovery=True
        )
        logger.info(f"Successfully deleted API key secret: {secret_arn}")
    except ClientError as e:
        logger.error(f"Failed to delete API key secret: {str(e)}")
        # Continue with integration deletion even if secret deletion fails
        # We don't want to block the integration deletion if the secret is already gone


@tracer.capture_method
def delete_integration(integration_id: str) -> bool:
    """
    Delete an integration from DynamoDB
    """
    table = dynamodb.Table(os.environ["INTEGRATIONS_TABLE"])

    try:
        # First, query to get all items for this integration
        response = table.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": f"INTEGRATION#{integration_id}"},
        )

        items = response.get("Items", [])

        if not items:
            logger.warning(f"No integration found with ID: {integration_id}")
            return False

        # Check if there's an API key secret to delete
        for item in items:
            if "ApiKeySecretArn" in item:
                delete_api_key_secret(item["ApiKeySecretArn"])

        # Delete all items for this integration
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

        # Add success metric
        metrics.add_metric(name="IntegrationsDeleted", unit=MetricUnit.Count, value=1)

        return True
    except ClientError as e:
        logger.error(f"Failed to delete integration: {str(e)}")
        metrics.add_metric(
            name="IntegrationDeletionErrors", unit=MetricUnit.Count, value=1
        )
        raise InternalServerError("Failed to delete integration")


@app.delete("/integrations/<integration_id>")
@tracer.capture_method
def handle_delete_integration(integration_id: str) -> Dict[str, Any]:
    """
    Handle DELETE request to delete an integration
    """
    try:
        # Validate integration ID
        if not integration_id:
            raise BadRequestError("Integration ID is required")

        # Delete the integration
        success = delete_integration(integration_id)

        if not success:
            raise NotFoundError(f"Integration with ID {integration_id} not found")

        return {
            "statusCode": 200,
            "body": {
                "status": "success",
                "message": f"Integration {integration_id} deleted successfully",
                "data": {"id": integration_id},
            },
        }
    except NotFoundError as e:
        logger.warning(f"Integration not found: {str(e)}")
        return {
            "statusCode": 404,
            "body": {
                "status": "error",
                "message": str(e),
                "requestId": app.current_event.request_context.request_id,
            },
        }
    except BadRequestError as e:
        logger.warning(f"Bad request: {str(e)}")
        metrics.add_metric(name="ValidationErrors", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 400,
            "body": {
                "status": "error",
                "message": str(e),
                "requestId": app.current_event.request_context.request_id,
            },
        }
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        metrics.add_metric(name="UnhandledErrors", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": {
                "status": "error",
                "message": f"Internal server error: {str(e)}",
                "requestId": app.current_event.request_context.request_id,
            },
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for DELETE /integrations/{id} endpoint
    """
    # Set log level from environment variable
    log_level = os.getenv("LOG_LEVEL", "WARNING").upper()
    logger.setLevel(log_level)

    try:
        return app.resolve(event, context)
    except Exception as e:
        logger.error(f"Unhandled error: {str(e)}")
        metrics.add_metric(name="UnhandledErrors", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": f"Internal server error: {str(e)}",
                    "requestId": context.aws_request_id,
                }
            ),
        }
