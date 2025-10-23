"""PUT /integrations/<integration_id> - Update an integration."""

import os
from datetime import datetime
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    InternalServerError,
    NotFoundError,
)
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError, parse
from botocore.exceptions import ClientError
from integration_models import UpdateIntegrationRequest
from response_utils import create_error_response, create_success_response
from secrets_utils import update_api_key_secret

logger = Logger(
    service="integrations-ID-put", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="integrations-ID-put")
metrics = Metrics(namespace="medialake", service="integrations")

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")


@tracer.capture_method
def get_integration(integration_id: str) -> Optional[Dict[str, Any]]:
    """
    Get an integration from DynamoDB.

    Args:
        integration_id: Integration ID to retrieve

    Returns:
        Integration item or None if not found

    Raises:
        InternalServerError: If retrieval fails
    """
    table = dynamodb.Table(os.environ["INTEGRATIONS_TABLE"])

    try:
        # Query to get all items for this integration
        response = table.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": f"INTEGRATION#{integration_id}"},
        )

        items = response.get("Items", [])

        if not items:
            logger.warning(f"No integration found with ID: {integration_id}")
            return None

        # Return the first item (there should be only one per integration ID)
        return items[0]
    except ClientError as e:
        logger.error(f"Failed to get integration: {str(e)}")
        raise InternalServerError("Failed to get integration")


@tracer.capture_method
def update_integration(
    integration_id: str, update_data: UpdateIntegrationRequest
) -> Optional[Dict[str, Any]]:
    """
    Update an integration in DynamoDB.

    Args:
        integration_id: Integration ID to update
        update_data: Validated update request data

    Returns:
        Updated integration item or None if not found

    Raises:
        InternalServerError: If update fails
    """
    table = dynamodb.Table(os.environ["INTEGRATIONS_TABLE"])

    try:
        # First, get the existing integration
        existing_integration = get_integration(integration_id)

        if not existing_integration:
            return None

        # Prepare update expression and attribute values
        update_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {}

        # Handle description update
        if update_data.description is not None:
            update_expression_parts.append("#description = :description")
            expression_attribute_values[":description"] = update_data.description
            expression_attribute_names["#description"] = "Description"

        # Handle status update
        if update_data.status is not None:
            update_expression_parts.append("#status = :status")
            expression_attribute_values[":status"] = update_data.status.value
            expression_attribute_names["#status"] = "Status"

        # Handle auth update
        if update_data.auth is not None:
            # Deep copy the auth object
            auth_config = update_data.auth.model_dump()

            # Handle API key update if present
            if (
                auth_config["type"] == "apiKey"
                and "apiKey" in auth_config["credentials"]
            ):
                # Get the API key
                api_key = auth_config["credentials"]["apiKey"]

                # Update or create the secret
                secret_arn = update_api_key_secret(
                    api_key,
                    integration_id,
                    existing_integration.get(
                        "ApiKeySecretArn"
                    ),  # pragma: allowlist secret
                )

                # Update the ApiKeySecretArn in DynamoDB
                update_expression_parts.append("#apiKeySecretArn = :apiKeySecretArn")
                expression_attribute_values[":apiKeySecretArn"] = secret_arn
                expression_attribute_names["#apiKeySecretArn"] = (
                    "ApiKeySecretArn"  # pragma: allowlist secret
                )

                # Remove the API key from the configuration that goes to DynamoDB
                auth_config["credentials"] = {"apiKeySecretArn": secret_arn}

            # Update the Configuration.auth field
            update_expression_parts.append("#configuration.#auth = :auth")
            expression_attribute_values[":auth"] = auth_config
            expression_attribute_names["#configuration"] = "Configuration"
            expression_attribute_names["#auth"] = "auth"

        # Add ModifiedDate
        current_time = datetime.utcnow().isoformat() + "Z"
        update_expression_parts.append("#modifiedDate = :modifiedDate")
        expression_attribute_values[":modifiedDate"] = current_time
        expression_attribute_names["#modifiedDate"] = "ModifiedDate"

        # Build the update expression
        update_expression = "SET " + ", ".join(update_expression_parts)

        # Update the item in DynamoDB
        response = table.update_item(
            Key={"PK": existing_integration["PK"], "SK": existing_integration["SK"]},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names,
            ReturnValues="ALL_NEW",
        )

        # Add success metric
        metrics.add_metric(name="IntegrationsUpdated", unit=MetricUnit.Count, value=1)

        return response.get("Attributes", {})
    except ClientError as e:
        logger.error(f"Failed to update integration: {str(e)}")
        metrics.add_metric(
            name="IntegrationUpdateErrors", unit=MetricUnit.Count, value=1
        )
        raise InternalServerError("Failed to update integration")


def register_route(app):
    """Register PUT /integrations/<integration_id> route"""

    @app.put("/integrations/<integration_id>")
    @tracer.capture_method
    def integrations_ID_put(integration_id: str):
        """Update an integration with Pydantic validation"""
        try:
            # Validate integration ID
            if not integration_id:
                raise BadRequestError("Integration ID is required")

            # Parse and validate with Pydantic V2
            try:
                request_data = parse(
                    event=app.current_event.json_body,
                    model=UpdateIntegrationRequest,
                )
            except ValidationError as e:
                logger.warning(f"Validation error updating integration: {e}")
                raise BadRequestError(f"Validation error: {str(e)}")

            logger.info(f"Updating integration: {integration_id}")

            # Update the integration
            updated_integration = update_integration(integration_id, request_data)

            if not updated_integration:
                raise NotFoundError(f"Integration with ID {integration_id} not found")

            logger.info(f"Integration updated: {integration_id}")

            return create_success_response(
                data={
                    "id": integration_id,
                    "name": updated_integration.get("Name", ""),
                    "nodeId": updated_integration.get("Node", ""),
                    "type": updated_integration.get("Type", ""),
                    "environment": updated_integration.get("Environment", ""),
                    "status": updated_integration.get("Status", ""),
                    "description": updated_integration.get("Description", ""),
                    "createdAt": updated_integration.get("CreatedDate", ""),
                    "updatedAt": updated_integration.get("ModifiedDate", ""),
                },
                message=f"Integration {integration_id} updated successfully",
                request_id=app.current_event.request_context.request_id,
            )

        except (BadRequestError, NotFoundError):
            raise
        except InternalServerError:
            raise
        except Exception as e:
            logger.exception("Error updating integration", exc_info=e)
            metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred while updating integration",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
