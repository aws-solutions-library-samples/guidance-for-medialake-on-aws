import os
import uuid
from datetime import datetime
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from aws_lambda_powertools.event_handler.exceptions import InternalServerError
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
logger = Logger(service="post_integrations")
tracer = Tracer(service="post_integrations")
metrics = Metrics(namespace="Integrations", service="post_integrations")

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
        "nodeId": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
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
    "required": ["nodeId", "auth"],
}


@tracer.capture_method
def get_default_environment() -> str:
    """
    Find the default environment from DynamoDB
    """
    try:
        table = dynamodb.Table(os.environ["ENVIRONMENTS_TABLE"])
        # Simply scan the entire table as there should only be one default environment
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
def store_api_key_secret(api_key: str, integration_id: str) -> str:
    """
    Store API key in Secrets Manager and return the secret ARN
    """
    try:
        secret_name = f"integration/{integration_id}/api-key"
        response = secretsmanager.create_secret(
            Name=secret_name,
            SecretString=api_key,
            Description=f"API Key for integration {integration_id}",
        )
        logger.info(f"Successfully stored API key for integration {integration_id}")
        return response["ARN"]
    except ClientError as e:
        logger.error(f"Failed to store API key: {str(e)}")
        raise InternalServerError("Failed to store API key")


@tracer.capture_method
def create_integration(
    integration_data: Dict[str, Any], integration_id: str, environment_id: str
) -> Dict[str, Any]:
    """
    Create a new integration in DynamoDB using the provided environment ID
    """
    table = dynamodb.Table(os.environ["INTEGRATIONS_TABLE"])

    try:
        # Extract node type from nodeId (assuming format: node-{type}-api)
        node_type = (
            integration_data["nodeId"].split("-")[1]
            if len(integration_data["nodeId"].split("-")) > 1
            else "unknown"
        )

        # Get current UTC timestamp
        current_time = datetime.utcnow().isoformat()

        # Generate name from nodeId by replacing underscores with spaces and title-casing
        # Use the actual nodeId value as provided (e.g., "twelve_labs" -> "Twelve Labs")
        generated_name = integration_data["nodeId"].replace("_", " ").title()

        # Prepare the item
        item = {
            "PK": f"INTEGRATION#{integration_id}",
            "SK": f"CONFIG#{environment_id}",
            "ID": integration_id,
            "Name": generated_name,
            "Node": integration_data["nodeId"],
            "Type": node_type,
            "Environment": environment_id,
            "Status": "active",  # Default to active
            "Description": integration_data.get("description", ""),
            "Configuration": {"auth": integration_data["auth"]},
            "CreatedDate": current_time,
            "ModifiedDate": current_time,
        }

        # Store API key in Secrets Manager if present
        if (
            integration_data["auth"]["type"] == "apiKey"
            and "apiKey" in integration_data["auth"]["credentials"]
        ):
            secret_arn = store_api_key_secret(
                integration_data["auth"]["credentials"]["apiKey"], integration_id
            )
            item["ApiKeySecretArn"] = secret_arn
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


@app.post("/integrations")
@tracer.capture_method
def handle_post_integrations() -> Dict[str, Any]:
    """
    Handle POST request to create a new integration
    """
    try:
        # Parse and validate request body
        event_body = app.current_event.json_body
        validate(event=event_body, schema=REQUEST_SCHEMA)

        # Get the default environment
        environment_id = get_default_environment()

        # Generate unique ID for the integration
        integration_id = str(uuid.uuid4())

        # Create the integration with the default environment
        integration = create_integration(event_body, integration_id, environment_id)

        return {
            "statusCode": 201,
            "body": {
                "status": "success",
                "message": "Integration created successfully",
                "data": {
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
    Lambda handler for POST /integrations endpoint
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
            "body": {
                "status": "error",
                "message": f"Internal server error: {str(e)}",
                "requestId": context.aws_request_id,
            },
        }
