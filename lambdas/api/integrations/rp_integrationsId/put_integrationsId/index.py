import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

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
from aws_lambda_powertools.utilities.validation import validate
from aws_lambda_powertools.utilities.validation.exceptions import SchemaValidationError
from botocore.exceptions import ClientError

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")
secretsmanager = boto3.client("secretsmanager")

# Initialize Powertools
logger = Logger(service="update_integration")
tracer = Tracer(service="update_integration")
metrics = Metrics(namespace="Integrations", service="update_integration")

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

# Schema for request validation
REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "status": {"type": "string", "enum": ["active", "inactive"]},
        "auth": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["apiKey"]},
                "credentials": {
                    "type": "object",
                    "properties": {"apiKey": {"type": "string", "minLength": 1}},
                    "required": ["apiKey"],
                },
            },
            "required": ["type", "credentials"],
        },
    },
    "minProperties": 1,  # At least one property must be provided for update
}


@tracer.capture_method
def update_api_key_secret(
    api_key: str, integration_id: str, existing_secret_arn: Optional[str] = None
) -> str:
    """
    Update API key in Secrets Manager and return the secret ARN
    """
    try:
        secret_name = f"integration/{integration_id}/api-key"

        # If there's an existing secret, update it
        if existing_secret_arn:
            response = secretsmanager.put_secret_value(
                SecretId=existing_secret_arn, SecretString=api_key
            )
            logger.info(
                f"Successfully updated API key for integration {integration_id}"
            )
            return existing_secret_arn
        # Otherwise, create a new secret
        else:
            response = secretsmanager.create_secret(
                Name=secret_name,
                SecretString=api_key,
                Description=f"API Key for integration {integration_id}",
            )
            logger.info(
                f"Successfully created API key for integration {integration_id}"
            )
            return response["ARN"]
    except ClientError as e:
        logger.error(f"Failed to update API key: {str(e)}")
        raise InternalServerError("Failed to update API key")


@tracer.capture_method
def get_integration(integration_id: str) -> Dict[str, Any]:
    """
    Get an integration from DynamoDB
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
            return {}

        # Return the first item (there should be only one per integration ID)
        return items[0]
    except ClientError as e:
        logger.error(f"Failed to get integration: {str(e)}")
        raise InternalServerError("Failed to get integration")


@tracer.capture_method
def update_integration(
    integration_id: str, update_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update an integration in DynamoDB
    """
    table = dynamodb.Table(os.environ["INTEGRATIONS_TABLE"])

    try:
        # First, get the existing integration
        existing_integration = get_integration(integration_id)

        if not existing_integration:
            return {}

        # Prepare update expression and attribute values
        update_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {}

        # Handle description update
        if "description" in update_data:
            update_expression_parts.append("#description = :description")
            expression_attribute_values[":description"] = update_data["description"]
            expression_attribute_names["#description"] = "Description"

        # Handle status update
        if "status" in update_data:
            update_expression_parts.append("#status = :status")
            expression_attribute_values[":status"] = update_data["status"]
            expression_attribute_names["#status"] = "Status"

        # Handle auth update
        if "auth" in update_data:
            # Deep copy the auth object to avoid modifying the original
            auth_config = {**update_data["auth"]}

            # Handle API key update if present
            if (
                auth_config["type"] == "apiKey"
                and "apiKey" in auth_config["credentials"]
            ):
                # Get the API key
                api_key = auth_config["credentials"]["apiKey"]

                # Update or create the secret
                secret_arn = update_api_key_secret(
                    api_key, integration_id, existing_integration.get("ApiKeySecretArn")
                )

                # Update the ApiKeySecretArn in DynamoDB
                update_expression_parts.append("#apiKeySecretArn = :apiKeySecretArn")
                expression_attribute_values[":apiKeySecretArn"] = secret_arn
                expression_attribute_names["#apiKeySecretArn"] = "ApiKeySecretArn"

                # Remove the API key from the configuration that goes to DynamoDB
                auth_config["credentials"] = {"apiKeySecretArn": secret_arn}

            # Update the Configuration.auth field
            update_expression_parts.append("#configuration.#auth = :auth")
            expression_attribute_values[":auth"] = auth_config
            expression_attribute_names["#configuration"] = "Configuration"
            expression_attribute_names["#auth"] = "auth"

        # Add ModifiedDate
        update_expression_parts.append("#modifiedDate = :modifiedDate")
        expression_attribute_values[":modifiedDate"] = datetime.utcnow().isoformat()
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


@app.put("/integrations/<integration_id>")
@tracer.capture_method
def handle_put_integration(integration_id: str) -> Dict[str, Any]:
    """
    Handle PUT request to update an integration
    """
    try:
        # Parse and validate request body
        event_body = app.current_event.json_body
        validate(event=event_body, schema=REQUEST_SCHEMA)

        # Validate integration ID
        if not integration_id:
            raise BadRequestError("Integration ID is required")

        # Update the integration
        updated_integration = update_integration(integration_id, event_body)

        if not updated_integration:
            raise NotFoundError(f"Integration with ID {integration_id} not found")

        return {
            "statusCode": 200,
            "body": {
                "status": "success",
                "message": f"Integration {integration_id} updated successfully",
                "data": {
                    "id": integration_id,
                    "name": updated_integration.get("Name", ""),
                    "nodeId": updated_integration.get("Node", ""),
                    "type": updated_integration.get("Type", ""),
                    "environment": updated_integration.get("Environment", ""),
                    "status": updated_integration.get("Status", ""),
                    "description": updated_integration.get("Description", ""),
                    "createdAt": updated_integration.get("CreatedDate", ""),
                    "updatedAt": updated_integration.get(
                        "ModifiedDate", datetime.utcnow().isoformat()
                    ),
                },
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
    except SchemaValidationError as e:
        logger.warning(f"Validation error: {str(e)}")
        metrics.add_metric(name="ValidationErrors", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 400,
            "body": {
                "status": "error",
                "message": f"Validation error: {str(e)}",
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
    Lambda handler for PUT /integrations/{id} endpoint
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
