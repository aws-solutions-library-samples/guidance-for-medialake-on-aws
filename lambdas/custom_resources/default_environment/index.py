import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from crhelper import CfnResource

# Initialize powertools
logger = Logger()
metrics = Metrics(namespace=os.environ.get("METRICS_NAMESPACE", "MediaLake"))
tracer = Tracer()

# Initialize resources
helper = CfnResource(json_logging=True, log_level="DEBUG", boto_level="CRITICAL")
dynamodb = boto3.resource("dynamodb")

# Get the environment table name from environment variables
ENVIRONMENTS_TABLE = os.environ.get("ENVIRONMENTS_TABLE")


def get_environment_pk(environment_id: str) -> str:
    """Generate the partition key for an environment."""
    return f"ENV#{environment_id}"


def get_environment_sk() -> str:
    """Generate the sort key for an environment."""
    return "METADATA"


@helper.create
@tracer.capture_method
def create_handler(event: Dict[str, Any], context: Any) -> None:
    """Handle the creation of the default environment."""
    logger.info("Creating default environment")

    # Get region from the Lambda context
    region = context.invoked_function_arn.split(":")[3]

    # Initialize DynamoDB table
    table = dynamodb.Table(ENVIRONMENTS_TABLE)

    # Generate unique ID and timestamps
    environment_id = str(uuid.uuid4())
    current_time = datetime.utcnow().isoformat()

    # Prepare DynamoDB item
    item = {
        "PK": get_environment_pk(environment_id),
        "SK": get_environment_sk(),
        "name": "default",
        "status": "active",
        "region": region,
        "cost_center": "0",
        "team": "default",
        "createdAt": current_time,
        "updatedAt": current_time,
    }

    # Check if default environment already exists
    try:
        response = table.scan(
            ConsistentRead=False,
            FilterExpression="begins_with(PK, :pk_prefix) AND SK = :sk AND #name = :env_name",
            ExpressionAttributeValues={
                ":pk_prefix": "ENV#",
                ":sk": "METADATA",
                ":env_name": "default",
            },
            ExpressionAttributeNames={"#name": "name"},
        )

        if response.get("Items", []):
            logger.info("Default environment already exists, skipping creation")
            return

        # Add the default environment to DynamoDB
        table.put_item(Item=item)
        logger.info(f"Successfully created default environment {environment_id}")

    except Exception as e:
        logger.error(f"Error creating default environment: {str(e)}")
        raise e


@helper.update
@tracer.capture_method
def update_handler(event: Dict[str, Any], context: Any) -> None:
    """Handle updates to the custom resource."""
    logger.info("Update operation - checking if default environment exists")
    # For updates, we'll just ensure the default environment exists
    create_handler(event, context)


@helper.delete
@tracer.capture_method
def delete_handler(event: Dict[str, Any], context: Any) -> None:
    """Handle the deletion of the custom resource."""
    # We don't delete the default environment when the stack is deleted
    logger.info("Delete operation - not removing default environment")


@logger.inject_lambda_context
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: Any) -> None:
    """Lambda handler to process CloudFormation Custom Resource events."""
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        helper(event, context)
    except Exception as e:
        logger.exception(f"Error in lambda_handler: {str(e)}")
        helper.init_failure(e)
