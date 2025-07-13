import json
import os
from typing import Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from pydantic import BaseModel

# Initialize Power Tools
logger = Logger(
    service="get_execution_service", level=os.getenv("LOG_LEVEL", "WARNING")
)
tracer = Tracer(service="get_execution_service")
metrics = Metrics(namespace="MediaLake", service="get_execution_service")

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["EXECUTIONS_TABLE_NAME"])

# CORS Configuration
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

# Initialize API Gateway resolver
app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)


class ExecutionResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict]


@app.get("/pipelines/executions/<execution_id>")
@tracer.capture_method
def get_execution(execution_id: str):
    try:
        logger.debug(f"Retrieving execution details for ID: {execution_id}")
        metrics.add_metric(name="GetExecutionAttempt", unit="Count", value=1)

        # Validate execution_id is not empty
        if not execution_id:
            logger.error("Execution ID is required")
            return ExecutionResponse(
                status="error", message="Execution ID is required", data=None
            ).dict()

        # Query DynamoDB
        response = table.get_item(Key={"execution_id": execution_id})

        # Check if item exists
        if "Item" not in response:
            logger.warning(f"Execution not found for ID: {execution_id}")
            metrics.add_metric(name="ExecutionNotFound", unit="Count", value=1)
            return ExecutionResponse(
                status="error", message="Execution not found", data=None
            ).dict()

        logger.info(f"Successfully retrieved execution: {execution_id}")
        metrics.add_metric(name="SuccessfulExecution", unit="Count", value=1)

        return ExecutionResponse(
            status="success",
            message="Execution retrieved successfully",
            data={"execution": response["Item"]},
        ).dict()

    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        metrics.add_metric(name="DynamoDBError", unit="Count", value=1)
        return ExecutionResponse(
            status="error", message="Internal server error", data=None
        ).dict()
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        metrics.add_metric(name="UnexpectedError", unit="Count", value=1)
        return ExecutionResponse(
            status="error", message="Internal server error", data=None
        ).dict()


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: APIGatewayProxyEvent, context: LambdaContext):
    return app.resolve(event, context)
