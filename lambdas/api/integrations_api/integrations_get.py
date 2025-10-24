"""GET /integrations - List all integrations."""

import os

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from formatting_utils import format_integration
from response_utils import create_error_response, create_success_response

logger = Logger(service="integrations-get", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="integrations-get")
metrics = Metrics(namespace="medialake", service="integrations")

# Initialize DynamoDB resource
dynamodb = boto3.resource("dynamodb")


def register_route(app):
    """Register GET /integrations route"""

    @app.get("/integrations")
    @tracer.capture_method
    def integrations_get():
        """Get list of all integrations"""
        try:
            table = dynamodb.Table(os.environ["INTEGRATIONS_TABLE"])

            logger.info("Listing all integrations")

            # Scan all integrations from DynamoDB
            response = table.scan()
            integrations = response.get("Items", [])

            # Handle pagination if needed
            while "LastEvaluatedKey" in response:
                response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
                integrations.extend(response.get("Items", []))

            # Format each integration
            formatted_integrations = [format_integration(item) for item in integrations]

            logger.info(f"Retrieved {len(formatted_integrations)} integrations")

            metrics.add_metric(
                name="SuccessfulIntegrationRetrievals",
                unit=MetricUnit.Count,
                value=1,
            )
            metrics.add_metric(
                name="IntegrationsReturned",
                unit=MetricUnit.Count,
                value=len(formatted_integrations),
            )

            return create_success_response(
                data=formatted_integrations,
                message="Integrations retrieved successfully",
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Unexpected error listing integrations", exc_info=e)
            metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred while retrieving integrations",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
