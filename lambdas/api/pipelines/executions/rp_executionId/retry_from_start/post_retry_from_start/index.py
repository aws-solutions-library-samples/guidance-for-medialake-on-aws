from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError
import os
from typing import Dict, Any
from models import PipelineExecution

# Initialize AWS clients
sfn = boto3.client("stepfunctions")

# Initialize Powertools
logger = Logger(service="PipelineExecutions", level=os.getenv("LOG_LEVEL", "WARNING"))
tracer = Tracer()
metrics = Metrics(namespace="Pipelines", service="ExecutionStartRetry")

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

app = APIGatewayRestResolver(cors=cors_config)


class ExecutionNotFoundError(Exception):
    """Raised when execution is not found in DynamoDB"""
    pass


class StepFunctionError(Exception):
    """Raised when Step Function operation fails"""
    pass


class RetryFromStartResponse(BaseModel):
    """Response model for retry from start execution"""
    status: str = Field(..., description="Status code of the operation")
    message: str = Field(..., description="Response message")
    new_execution_arn: str = Field(None, description="ARN of the new execution")


@tracer.capture_method
def get_execution_details(execution_id: str) -> Dict[str, Any]:
    """
    Retrieve execution details from DynamoDB

    Args:
        execution_id: The ID of the execution to retrieve

    Returns:
        Dict containing execution details

    Raises:
        ExecutionNotFoundError: If execution is not found
    """
    try:
        # Query by execution_id since it's the hash key
        executions = list(PipelineExecution.query(execution_id, limit=1))
        
        if not executions:
            logger.error(f"Execution not found: {execution_id}")
            raise ExecutionNotFoundError(f"Execution {execution_id} not found")

        execution = executions[0]
        logger.debug(
            f"Retrieved execution details: {execution.execution_id}", extra={"execution_id": execution_id}
        )
        return execution

    except Exception as e:
        logger.exception("Failed to retrieve execution from DynamoDB")
        metrics.add_metric(name="DynamoDBErrors", unit="Count", value=1)
        raise ExecutionNotFoundError(f"Failed to retrieve execution: {str(e)}")


@tracer.capture_method
def start_new_execution(execution_arn: str) -> str:
    """
    Start a new Step Function execution with the same input as the original

    Args:
        execution_arn: The ARN of the original execution

    Returns:
        str: The ARN of the new execution

    Raises:
        StepFunctionError: If start operation fails
    """
    try:
        # Get the state machine ARN from the execution ARN
        state_machine_arn = ":".join(execution_arn.split(":")[:-1])

        # Get the original execution details to retrieve input
        execution_details = sfn.describe_execution(executionArn=execution_arn)
        original_input = execution_details.get("input", "{}")

        # Start new execution with same input
        response = sfn.start_execution(
            stateMachineArn=state_machine_arn, 
            input=original_input
        )

        new_execution_arn = response["executionArn"]

        logger.info(
            "Successfully started new execution from start",
            extra={
                "original_execution_arn": execution_arn,
                "new_execution_arn": new_execution_arn,
            },
        )

        metrics.add_metric(name="SuccessfulStartRetries", unit="Count", value=1)
        return new_execution_arn

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        
        logger.exception("Failed to start new Step Function execution")
        metrics.add_metric(name="FailedStartRetries", unit="Count", value=1)
        
        # Map AWS errors to user-friendly messages
        if error_code == "ExecutionLimitExceeded":
            raise StepFunctionError("Maximum number of concurrent executions reached")
        elif error_code == "ExecutionAlreadyExists":
            raise StepFunctionError("An execution with this name already exists")
        elif error_code == "StateMachineDoesNotExist":
            raise StepFunctionError("The state machine no longer exists")
        elif error_code == "InvalidExecutionInput":
            raise StepFunctionError("The original execution input is invalid")
        else:
            raise StepFunctionError(f"Failed to start new execution: {error_message}")


@app.post("/pipelines/executions/<execution_id>/retry-from-start")
@tracer.capture_method
def handle_retry_from_start(execution_id: str) -> Dict[str, Any]:
    """
    Handle retry from start request by creating a new execution

    Args:
        execution_id: The ID of the execution to retry

    Returns:
        Dict containing response data
    """
    try:
        # Get execution details from DynamoDB
        execution = get_execution_details(execution_id)
        execution_arn = execution.execution_arn

        # Start new execution with same input
        new_execution_arn = start_new_execution(execution_arn)

        response = RetryFromStartResponse(
            status="200", 
            message="New execution started successfully from beginning",
            new_execution_arn=new_execution_arn
        )

        return {"statusCode": 200, "body": response.model_dump()}

    except ExecutionNotFoundError as e:
        logger.warning(f"Execution not found: {execution_id}")
        return {"statusCode": 404, "body": {"status": "404", "message": str(e)}}

    except StepFunctionError as e:
        logger.error(f"Failed to start new execution: {str(e)}")
        return {"statusCode": 500, "body": {"status": "500", "message": str(e)}}


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """
    Main Lambda handler

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    try:
        # Configure PynamoDB model with environment variables
        PipelineExecution.Meta.table_name = os.environ["PIPELINES_EXECUTIONS_TABLE_NAME"]
        PipelineExecution.Meta.region = os.environ["AWS_REGION"]
        
        return app.resolve(event, context)
    except Exception as e:
        logger.exception("Unhandled error in lambda handler")
        metrics.add_metric(name="UnhandledErrors", unit="Count", value=1)
        return {
            "statusCode": 500,
            "body": {"message": "Internal server error", "status": "error"},
        }