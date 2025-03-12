import os
from typing import Optional
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel
import json

# Initialize Power Tools
logger = Logger(service="get_pipline_service", level=os.getenv("LOG_LEVEL", "WARNING"))
tracer = Tracer(service="get_pipline_service")
metrics = Metrics(namespace="MediaLake", service="get_pipline_service")

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["PIPELINES_TABLE_NAME"])

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


class PipelineResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict]


@app.get("/pipelines/<pipeline_id>")
@tracer.capture_method
def get_pipeline(pipeline_id: str):
    try:
        logger.debug(f"Retrieving pipeline details for ID: {pipeline_id}")
        metrics.add_metric(name="GetPipelineAttempt", unit="Count", value=1)

        # Validate pipeline_id is not empty
        if not pipeline_id:
            logger.error("Pipeline ID is required")
            return PipelineResponse(
                status="error", message="Pipeline ID is required", data=None
            ).dict()

        # Query DynamoDB
        response = table.get_item(Key={"id": pipeline_id})

        # Check if item exists
        if "Item" not in response:
            logger.warning(f"Pipeline not found for ID: {pipeline_id}")
            metrics.add_metric(name="PipelineNotFound", unit="Count", value=1)
            return PipelineResponse(
                status="error", message="Pipeline not found", data=None
            ).dict()

        logger.info(f"Successfully retrieved pipeline: {pipeline_id}")
        metrics.add_metric(name="SuccessfulPipeline", unit="Count", value=1)

        return PipelineResponse(
            status="success",
            message="Pipeline retrieved successfully",
            data={"pipeline": response["Item"]},
        ).dict()

    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        metrics.add_metric(name="DynamoDBError", unit="Count", value=1)
        return PipelineResponse(
            status="error", message="Internal server error", data=None
        ).dict()
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        metrics.add_metric(name="UnexpectedError", unit="Count", value=1)
        return PipelineResponse(
            status="error", message="Internal server error", data=None
        ).dict()


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: APIGatewayProxyEvent, context: LambdaContext):
    return app.resolve(event, context)
