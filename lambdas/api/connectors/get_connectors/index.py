import os
import boto3
import json
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.event_handler import APIGatewayRestResolver

tracer = Tracer()
logger = Logger()
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
app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")


def format_connector(item: dict) -> dict:
    return {
        "id": item.get("id", ""),
        "name": item.get("name", ""),
        "description": item.get("description", ""),
        "usage": {"total": item.get("usage", {}).get("total", 0)},
        "type": item.get("type", ""),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
        "storageIdentifier": item.get("storageIdentifier", ""),
        "sqsArn": item.get("sqsArn", ""),
        "region": item.get("region", ""),
        "status": item.get("status", ""),
        "integrationMethod": item.get("integrationMethod", ""),
        "iamRoleArn": item.get("iamRoleArn", ""),
        "lambdaArn": item.get("lambdaArn", ""),
        "queueUrl": item.get("queueUrl", ""),
        "configuration": {
            "queueUrl": item.get("queueUrl", ""),
            "lambdaArn": item.get("lambdaArn", ""),
            "iamRoleArn": item.get("iamRoleArn", ""),
        },
        "settings": {
            "bucket": item.get("storageIdentifier", ""),
            "region": item.get("region", ""),
        },
    }


@app.get("/connectors")
@tracer.capture_method
def get_connectors() -> dict:
    try:
        # Get DynamoDB table name from environment variables
        table_name = os.environ.get("MEDIALAKE_CONNECTOR_TABLE")
        if not table_name:
            logger.error("MEDIALAKE_CONNECTOR_TABLE environment variable is not set")
            return {
                "status": "500",
                "message": "MEDIALAKE_CONNECTOR_TABLE environment variable "
                "is not set",
                "data": {"connectors": []},
            }

        # Get table reference
        table = dynamodb.Table(table_name)

        # Scan the table to get all connectors
        try:
            response = table.scan()
            connectors = [format_connector(item) for item in response.get("Items", [])]

            # Handle pagination if there are more items
            while "LastEvaluatedKey" in response:
                response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
                connectors.extend(
                    [format_connector(item) for item in response.get("Items", [])]
                )

            logger.info(f"Retrieved {len(connectors)} connectors successfully")

            return {
                "status": "200",
                "message": "ok",
                "data": {"connectors": connectors},
            }

        except Exception as e:
            logger.error(f"Error querying DynamoDB table: {str(e)}")
            return {
                "status": "500",
                "message": "Error querying DynamoDB: {str(e)}",
                "data": {"connectors": []},
            }

    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        return {
            "status": "500",
            "message": "Internal server error",
            "data": {"connectors": []},
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
