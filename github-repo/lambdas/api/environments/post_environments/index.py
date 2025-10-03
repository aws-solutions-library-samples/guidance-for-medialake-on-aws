import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict

import boto3
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from lambda_utils import handle_error, lambda_handler_decorator, logger, metrics, tracer
from pydantic import BaseModel, Field

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ENVIRONMENTS_TABLE"])


class EnvironmentCreate(BaseModel):
    name: str = Field(..., min_length=1)
    # region: str = Field(..., min_length=1)
    # tags: Dict[str, str] = Field(default_factory=dict)


def get_environment_pk(environment_id: str) -> str:
    return f"ENV#{environment_id}"


def get_environment_sk() -> str:
    return "METADATA"


def format_environment(item: Dict[str, Any]) -> Dict[str, Any]:
    """Format environment data for response"""
    formatted = {
        "id": item["PK"].split("#")[1],
        "name": item["name"],
        "status": item["status"],
        "createdAt": item["createdAt"],
        "updatedAt": item["updatedAt"],
    }

    # Add optional fields if they exist
    if "region" in item:
        formatted["region"] = item["region"]
    if "tags" in item:
        formatted["tags"] = item["tags"]

    return formatted


@tracer.capture_method
def create_environment(event: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new environment."""
    try:
        # Parse and validate request body
        body = json.loads(event.get("body", "{}"))
        environment_data = EnvironmentCreate(**body)

        # Generate unique ID and timestamps
        environment_id = str(uuid.uuid4())
        current_time = datetime.utcnow().isoformat()

        # Prepare DynamoDB item
        item = {
            "PK": get_environment_pk(environment_id),
            "SK": get_environment_sk(),
            "name": environment_data.name,
            "status": "active",
            # "region": environment_data.region,
            # "tags": environment_data.tags,
            "createdAt": current_time,
            "updatedAt": current_time,
        }

        # Save to DynamoDB
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(PK)",
        )

        # Record metric
        metrics.add_metric(name="CreateEnvironment", unit=MetricUnit.Count, value=1)
        logger.info(f"Created environment {environment_id}")

        return {"statusCode": 201, "body": json.dumps(format_environment(item))}

    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {
                "statusCode": 409,
                "body": json.dumps(
                    {"error": "ConflictError", "message": "Environment already exists"}
                ),
            }
        return handle_error(e)

    except Exception as e:
        return handle_error(e)


@metrics.log_metrics(capture_cold_start_metric=True)
@lambda_handler_decorator(cors=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler for environment creation"""
    return create_environment(event)
