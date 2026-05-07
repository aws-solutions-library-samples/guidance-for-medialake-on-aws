"""DELETE /integrations/<integration_id> - Delete an integration."""

import os

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    InternalServerError,
    NotFoundError,
)
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from response_utils import create_error_response, create_success_response
from secrets_utils import delete_api_key_secret

logger = Logger(
    service="integrations-ID-delete", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="integrations-ID-delete")
metrics = Metrics(namespace="medialake", service="integrations")

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")


@tracer.capture_method
def delete_integration(integration_id: str) -> bool:
    """
    Delete an integration from DynamoDB.

    Args:
        integration_id: Integration ID to delete

    Returns:
        True if deleted successfully, False if not found

    Raises:
        InternalServerError: If deletion fails
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
            if "ApiKeySecretArn" in item:  # pragma: allowlist secret
                delete_api_key_secret(
                    item["ApiKeySecretArn"]
                )  # pragma: allowlist secret

        # Delete all items for this integration
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

        # Add success metric
        metrics.add_metric(name="IntegrationsDeleted", unit=MetricUnit.Count, value=1)

        logger.info(f"Successfully deleted integration: {integration_id}")
        return True
    except ClientError as e:
        logger.error(f"Failed to delete integration: {str(e)}")
        metrics.add_metric(
            name="IntegrationDeletionErrors", unit=MetricUnit.Count, value=1
        )
        raise InternalServerError("Failed to delete integration")


def register_route(app):
    """Register DELETE /integrations/<integration_id> route"""

    @app.delete("/integrations/<integration_id>")
    @tracer.capture_method
    def integrations_ID_delete(integration_id: str):
        """Delete an integration"""
        try:
            # Validate integration ID
            if not integration_id:
                raise BadRequestError("Integration ID is required")

            logger.info(f"Deleting integration: {integration_id}")

            # Delete the integration
            success = delete_integration(integration_id)

            if not success:
                raise NotFoundError(f"Integration with ID {integration_id} not found")

            logger.info(f"Integration deleted: {integration_id}")

            return create_success_response(
                data={"id": integration_id},
                message=f"Integration {integration_id} deleted successfully",
                request_id=app.current_event.request_context.request_id,
            )

        except (BadRequestError, NotFoundError):
            raise
        except InternalServerError:
            raise
        except Exception as e:
            logger.exception("Error deleting integration", exc_info=e)
            metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred while deleting integration",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
