from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.validation import validate
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError
import os
from typing import Dict, Any, Optional

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
sfn = boto3.client("stepfunctions")

# Initialize Powertools
logger = Logger(service="PipelineExecutions", level=os.getenv("LOG_LEVEL", "WARNING"))
tracer = Tracer()
metrics = Metrics(namespace="Pipelines", service="ExecutionRetry")
app = APIGatewayRestResolver()

# Constants
EXECUTIONS_TABLE = os.environ["PIPELINES_EXECUTIONS_TABLE_NAME"]
table = dynamodb.Table(EXECUTIONS_TABLE)


class ExecutionNotFoundError(Exception):
    """Raised when execution is not found in DynamoDB"""

    pass


class StepFunctionError(Exception):
    """Raised when Step Function operation fails"""

    pass


class RetryExecutionResponse(BaseModel):
    """Response model for retry execution"""

    status: str = Field(..., description="Status code of the operation")
    message: str = Field(..., description="Response message")


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
        response = table.get_item(Key={"id": execution_id})
        item = response.get("Item")

        if not item:
            logger.error(f"Execution not found: {execution_id}")
            raise ExecutionNotFoundError(f"Execution {execution_id} not found")

        logger.debug(
            f"Retrieved execution details: {item}", extra={"execution_id": execution_id}
        )
        return item

    except ClientError as e:
        logger.exception("Failed to retrieve execution from DynamoDB")
        metrics.add_metric(name="DynamoDBErrors", unit="Count", value=1)
        raise ExecutionNotFoundError(f"Failed to retrieve execution: {str(e)}")


@tracer.capture_method
def retry_step_function(execution_arn: str) -> str:
    """
    Retry a Step Function execution

    Args:
        execution_arn: The ARN of the execution to retry

    Returns:
        str: The ARN of the new execution

    Raises:
        StepFunctionError: If retry operation fails
    """
    try:
        # Get the state machine ARN from the execution ARN
        state_machine_arn = ":".join(execution_arn.split(":")[:-1])

        # Start new execution with same input
        execution_details = sfn.describe_execution(executionArn=execution_arn)

        response = sfn.start_execution(
            stateMachineArn=state_machine_arn, input=execution_details["input"]
        )

        logger.info(
            "Successfully started new execution",
            extra={
                "original_execution_arn": execution_arn,
                "new_execution_arn": response["executionArn"],
            },
        )

        metrics.add_metric(name="SuccessfulRetries", unit="Count", value=1)
        return response["executionArn"]

    except ClientError as e:
        logger.exception("Failed to retry Step Function execution")
        metrics.add_metric(name="FailedRetries", unit="Count", value=1)
        raise StepFunctionError(f"Failed to retry execution: {str(e)}")


@app.post("/pipelines/executions/<execution_id>/retry")
@tracer.capture_method
def handle_retry_execution(execution_id: str) -> Dict[str, Any]:
    """
    Handle retry execution request

    Args:
        execution_id: The ID of the execution to retry

    Returns:
        Dict containing response data
    """
    try:
        # Get execution details from DynamoDB
        execution = get_execution_details(execution_id)
        execution_arn = execution["execution_arn"]

        # Retry the Step Function execution
        new_execution_arn = retry_step_function(execution_arn)

        response = RetryExecutionResponse(status="200", message="ok")

        return {"statusCode": 200, "body": response.model_dump()}

    except ExecutionNotFoundError as e:
        logger.warning(f"Execution not found: {execution_id}")
        return {"statusCode": 404, "body": {"status": "404", "message": str(e)}}

    except StepFunctionError as e:
        logger.error(f"Failed to retry execution: {str(e)}")
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
        return app.resolve(event, context)
    except Exception as e:
        logger.exception("Unhandled error in lambda handler")
        metrics.add_metric(name="UnhandledErrors", unit="Count", value=1)
        return {
            "statusCode": 500,
            "body": {"message": "Internal server error", "status": "error"},
        }
