"""POST /integrations - Create a new integration."""

import os
import uuid
from datetime import datetime
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    InternalServerError,
)
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError, parse
from botocore.exceptions import ClientError
from integration_models import CreateIntegrationRequest
from response_utils import create_error_response, create_success_response
from secrets_utils import store_api_key_secret

logger = Logger(service="integrations-post", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="integrations-post")
metrics = Metrics(namespace="medialake", service="integrations")

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")


@tracer.capture_method
def get_default_environment() -> str:
    """
    Find the default environment from DynamoDB.

    Returns:
        Environment ID string

    Raises:
        InternalServerError: If default environment not found
    """
    try:
        table = dynamodb.Table(os.environ.get("ENVIRONMENTS_TABLE", ""))
        # Scan for the default environment
        response = table.scan(
            FilterExpression="begins_with(PK, :pk_prefix) AND #name = :name",
            ExpressionAttributeNames={"#name": "name"},
            ExpressionAttributeValues={":pk_prefix": "ENV#", ":name": "default"},
        )

        if not response.get("Items"):
            logger.error("Default environment not found")
            raise InternalServerError("Default environment not found")

        # Return the environment ID (extracting from "ENV#uuid" format)
        environment_id = response["Items"][0]["PK"].split("#")[1]
        logger.info(f"Found default environment: {environment_id}")
        return environment_id
    except ClientError as e:
        logger.error(f"Failed to find default environment: {str(e)}")
        raise InternalServerError("Failed to find default environment")


@tracer.capture_method
def create_integration(
    integration_data: CreateIntegrationRequest, integration_id: str, environment_id: str
) -> Dict[str, Any]:
    """
    Create a new integration in DynamoDB.

    Args:
        integration_data: Validated integration request data
        integration_id: Generated integration ID
        environment_id: Environment ID for the integration

    Returns:
        Created integration item

    Raises:
        InternalServerError: If integration creation fails
    """
    table = dynamodb.Table(os.environ["INTEGRATIONS_TABLE"])

    try:
        # Extract node type from nodeId
        node_type = (
            integration_data.nodeId.split("-")[1]
            if len(integration_data.nodeId.split("-")) > 1
            else "unknown"
        )

        # Get current UTC timestamp
        current_time = datetime.utcnow().isoformat() + "Z"

        # Generate name from nodeId
        generated_name = integration_data.nodeId.replace("_", " ").title()

        # Prepare the item
        item = {
            "PK": f"INTEGRATION#{integration_id}",
            "SK": f"CONFIG#{environment_id}",
            "ID": integration_id,
            "Name": generated_name,
            "Node": integration_data.nodeId,
            "Type": node_type,
            "Environment": environment_id,
            "Status": "active",  # Default to active
            "Description": integration_data.description or "",
            "Configuration": {"auth": integration_data.auth.model_dump()},
            "CreatedDate": current_time,
            "ModifiedDate": current_time,
        }

        # Store API key in Secrets Manager if present
        if (
            integration_data.auth.type.value == "apiKey"
            and integration_data.auth.credentials.apiKey
        ):
            secret_arn = store_api_key_secret(
                integration_data.auth.credentials.apiKey, integration_id
            )
            item["ApiKeySecretArn"] = secret_arn  # pragma: allowlist secret
            # Remove the API key from the configuration that goes to DynamoDB
            item["Configuration"]["auth"]["credentials"] = {
                "apiKeySecretArn": secret_arn
            }

        # Put item in DynamoDB
        table.put_item(Item=item)

        # Add success metric
        metrics.add_metric(name="IntegrationsCreated", unit=MetricUnit.Count, value=1)

        return item
    except ClientError as e:
        logger.error(f"Failed to create integration: {str(e)}")
        metrics.add_metric(
            name="IntegrationCreationErrors", unit=MetricUnit.Count, value=1
        )
        raise InternalServerError("Failed to create integration")


def register_route(app):
    """Register POST /integrations route"""

    @app.post("/integrations")
    @tracer.capture_method
    def integrations_post():
        """Create a new integration with Pydantic validation"""
        try:
            # Parse and validate with Pydantic V2
            try:
                request_data = parse(
                    event=app.current_event.json_body,
                    model=CreateIntegrationRequest,
                )
            except ValidationError as e:
                logger.warning(f"Validation error creating integration: {e}")
                raise BadRequestError(f"Validation error: {str(e)}")

            logger.info(f"Creating integration for node: {request_data.nodeId}")

            # Get the default environment
            environment_id = get_default_environment()

            # Generate unique ID for the integration
            integration_id = str(uuid.uuid4())

            # Create the integration
            integration = create_integration(
                request_data, integration_id, environment_id
            )

            logger.info(f"Integration created: {integration_id}")

            return create_success_response(
                data={
                    "id": integration_id,
                    "name": integration["Name"],
                    "nodeId": integration["Node"],
                    "type": integration["Type"],
                    "environment": integration["Environment"],
                    "status": integration["Status"],
                    "description": integration["Description"],
                    "createdAt": integration["CreatedDate"],
                    "updatedAt": integration["ModifiedDate"],
                },
                message="Integration created successfully",
                status_code=201,
                request_id=app.current_event.request_context.request_id,
            )

        except BadRequestError:
            raise
        except InternalServerError:
            raise
        except Exception as e:
            logger.exception("Error creating integration", exc_info=e)
            metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred while creating integration",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
