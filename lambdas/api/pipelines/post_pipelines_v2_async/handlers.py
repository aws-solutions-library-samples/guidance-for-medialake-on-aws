import json
import os
from typing import Dict, Any

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.event_handler.api_gateway import (
    APIGatewayRestResolver,
    CORSConfig,
)

from models import PipelineDefinition

# Initialize AWS Lambda Powertools utilities
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="PostPipelineAsyncHandler")

# Configure CORS and API Gateway resolver
cors_config = CORSConfig(allow_origin="*", allow_headers=["*"])
app = APIGatewayRestResolver(cors=cors_config)

# Get the Step Function ARN from environment variables
PIPELINE_CREATION_STATE_MACHINE_ARN = os.environ.get("PIPELINE_CREATION_STATE_MACHINE_ARN")

@app.post("/pipelinesv2")
@tracer.capture_method
def create_pipeline() -> Dict[str, Any]:
    """
    Start a pipeline creation process asynchronously.
    
    Returns:
        API Gateway response with the execution ARN
    """
    try:
        logger.info("Received request to create/update a pipeline")
        request_data = app.current_event.json_body
        
        # Validate the pipeline definition
        pipeline = PipelineDefinition(**request_data)
        logger.debug(f"Pipeline configuration: {pipeline}")
        
        pipeline_name = pipeline.name
        logger.info(f"Processing pipeline: {pipeline_name} - {pipeline.description}")
        
        # Start the Step Function execution
        sfn_client = boto3.client("stepfunctions")
        response = sfn_client.start_execution(
            stateMachineArn=PIPELINE_CREATION_STATE_MACHINE_ARN,
            input=json.dumps(request_data)
        )
        
        execution_arn = response["executionArn"]
        logger.info(f"Started Step Function execution: {execution_arn}")
        
        # Return a response to the client
        response_body = {
            "message": f"Pipeline creation started for '{pipeline_name}'",
            "execution_arn": execution_arn,
            "status": "RUNNING",
            "pipeline_name": pipeline_name
        }
        
        return {
            "statusCode": 202,  # Accepted
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(response_body),
        }
        
    except Exception as e:
        logger.exception("Error starting pipeline creation")
        error_body = {"error": "Failed to start pipeline creation", "details": str(e)}
        
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(error_body),
        }

@app.get("/pipelinesv2/status/{executionArn}")
@tracer.capture_method
def get_pipeline_status(executionArn: str) -> Dict[str, Any]:
    """
    Get the status of a pipeline creation.
    
    Args:
        executionArn: ARN of the Step Function execution
        
    Returns:
        API Gateway response with the execution status
    """
    try:
        logger.info(f"Checking status of execution: {executionArn}")
        
        # Get the execution status
        sfn_client = boto3.client("stepfunctions")
        response = sfn_client.describe_execution(
            executionArn=executionArn
        )
        
        status = response["status"]
        output = json.loads(response.get("output", "{}")) if "output" in response else {}
        
        # Return the status to the client
        response_body = {
            "execution_arn": executionArn,
            "status": status,
            "output": output
        }
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(response_body),
        }
        
    except Exception as e:
        logger.exception("Error checking pipeline status")
        error_body = {"error": "Failed to check pipeline status", "details": str(e)}
        
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(error_body),
        }

@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    AWS Lambda handler entry point.
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response
    """
    logger.info("Lambda handler invoked", extra={"event": event})
    response = app.resolve(event, context)
    logger.info(f"Returning response from lambda_handler: {response}")
    return response