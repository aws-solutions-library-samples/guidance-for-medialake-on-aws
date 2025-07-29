import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from models import PipelineExecution
from pydantic import BaseModel, Field

# Initialize AWS clients
sfn = boto3.client("stepfunctions")

# Initialize Powertools
logger = Logger(service="PipelineExecutions", level=os.getenv("LOG_LEVEL", "WARNING"))
tracer = Tracer()
metrics = Metrics(namespace="Pipelines", service="ExecutionUnifiedRetry")

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


class ExecutionNotRedrivableError(Exception):
    """Raised when execution cannot be redriven"""


class StepFunctionError(Exception):
    """Raised when Step Function operation fails"""


class InvalidRetryTypeError(Exception):
    """Raised when invalid retry type is specified"""


class UnifiedRetryResponse(BaseModel):
    """Response model for unified retry execution"""

    status: str = Field(..., description="Status code of the operation")
    message: str = Field(..., description="Response message")
    retry_type: str = Field(..., description="Type of retry performed")
    new_execution_arn: Optional[str] = Field(
        None, description="ARN of the new execution (for from_start)"
    )
    redrive_date: Optional[str] = Field(
        None, description="Date when execution was redriven (for from_current)"
    )


@tracer.capture_method
def get_execution_details(execution_id: str) -> PipelineExecution:
    """
    Retrieve execution details from DynamoDB

    Args:
        execution_id: The ID of the execution to retrieve

    Returns:
        PipelineExecution object

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
            f"Retrieved execution details: {execution.execution_id}",
            extra={"execution_id": execution_id},
        )
        return execution

    except Exception as e:
        logger.exception("Failed to retrieve execution from DynamoDB")
        metrics.add_metric(name="DynamoDBErrors", unit="Count", value=1)
        raise ExecutionNotFoundError(f"Failed to retrieve execution: {str(e)}")


@tracer.capture_method
def validate_redrive_eligibility(execution: PipelineExecution) -> None:
    """
    Validate if execution can be redriven based on AWS constraints

    Args:
        execution: Execution details from DynamoDB

    Raises:
        ExecutionNotRedrivableError: If execution cannot be redriven
    """
    execution_arn = execution.execution_arn
    status = execution.status

    # Check if execution status is eligible for redrive
    if status == "SUCCEEDED":
        raise ExecutionNotRedrivableError("Cannot redrive successful executions")

    # Check if execution is within 14-day redrivable period
    if execution.end_time:
        try:
            end_timestamp = int(execution.end_time)
            end_date = datetime.fromtimestamp(end_timestamp)
            fourteen_days_ago = datetime.now() - timedelta(days=14)

            if end_date < fourteen_days_ago:
                raise ExecutionNotRedrivableError(
                    "Execution is older than 14 days and cannot be redriven"
                )
        except (ValueError, TypeError):
            logger.warning(f"Could not parse end_time: {execution.end_time}")

    # Additional validation by checking execution details from Step Functions
    try:
        sfn_response = sfn.describe_execution(executionArn=execution_arn)
        sfn_status = sfn_response.get("status")

        if sfn_status == "SUCCEEDED":
            raise ExecutionNotRedrivableError(
                "Execution has succeeded and cannot be redriven"
            )

        # Check if execution is still running
        if sfn_status == "RUNNING":
            raise ExecutionNotRedrivableError("Cannot redrive a running execution")

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "ExecutionDoesNotExist":
            raise ExecutionNotRedrivableError(
                "Execution no longer exists in Step Functions"
            )
        else:
            logger.warning(f"Could not validate execution status: {str(e)}")


@tracer.capture_method
def redrive_step_function_execution(execution_arn: str) -> Dict[str, Any]:
    """
    Redrive a Step Function execution from the failed step

    Args:
        execution_arn: The ARN of the execution to redrive

    Returns:
        Dict containing redrive response

    Raises:
        StepFunctionError: If redrive operation fails
    """
    try:
        response = sfn.redrive_execution(executionArn=execution_arn)

        logger.info(
            "Successfully redrove execution",
            extra={
                "execution_arn": execution_arn,
                "redrive_date": response.get("redriveDate"),
            },
        )

        metrics.add_metric(name="SuccessfulRedrives", unit="Count", value=1)
        return response

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        logger.exception("Failed to redrive Step Function execution")
        metrics.add_metric(name="FailedRedrives", unit="Count", value=1)

        # Map AWS errors to user-friendly messages
        if error_code == "ExecutionNotRedrivable":
            raise ExecutionNotRedrivableError(
                f"Execution cannot be redriven: {error_message}"
            )
        elif error_code == "ExecutionDoesNotExist":
            raise ExecutionNotRedrivableError("Execution no longer exists")
        elif error_code == "ExecutionLimitExceeded":
            raise ExecutionNotRedrivableError("Execution has exceeded redrive limits")
        else:
            raise StepFunctionError(f"Failed to redrive execution: {error_message}")


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
        # Get the original execution details to retrieve input and state machine ARN
        execution_details = sfn.describe_execution(executionArn=execution_arn)
        original_input = execution_details.get("input", "{}")
        state_machine_arn = execution_details.get("stateMachineArn")

        if not state_machine_arn:
            raise StepFunctionError(
                "Could not determine state machine ARN from execution details"
            )

        # Start new execution with same input
        response = sfn.start_execution(
            stateMachineArn=state_machine_arn, input=original_input
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


@app.post("/pipelines/executions/<execution_id>/retry")
@tracer.capture_method
def handle_unified_retry(execution_id: str) -> Dict[str, Any]:
    """
    Handle unified retry request with support for both retry types via query parameters

    Args:
        execution_id: The ID of the execution to retry

    Query Parameters:
        type: 'from_current' or 'from_start' (defaults to 'from_start')

    Returns:
        Dict containing response data
    """
    try:
        # Get retry type from query parameters
        retry_type = (
            app.current_event.query_string_parameters.get("type", "from_start")
            if app.current_event.query_string_parameters
            else "from_start"
        )

        if retry_type not in ["from_current", "from_start"]:
            raise InvalidRetryTypeError(
                f"Invalid retry type: {retry_type}. Must be 'from_current' or 'from_start'"
            )

        # Get execution details from DynamoDB
        execution = get_execution_details(execution_id)
        execution_arn = execution.execution_arn

        logger.info(f"Processing {retry_type} retry for execution: {execution_id}")

        if retry_type == "from_current":
            # Validate if execution can be redriven
            validate_redrive_eligibility(execution)

            # Redrive the Step Function execution
            redrive_response = redrive_step_function_execution(execution_arn)

            response = UnifiedRetryResponse(
                status="200",
                message="Execution successfully redriven from current position",
                retry_type=retry_type,
                redrive_date=(
                    redrive_response.get("redriveDate").isoformat()
                    if redrive_response.get("redriveDate")
                    else None
                ),
            )

        else:  # from_start
            # Start new execution with same input
            new_execution_arn = start_new_execution(execution_arn)

            response = UnifiedRetryResponse(
                status="200",
                message="New execution started successfully from beginning",
                retry_type=retry_type,
                new_execution_arn=new_execution_arn,
            )

        return {"statusCode": 200, "body": response.model_dump()}

    except InvalidRetryTypeError as e:
        logger.warning(f"Invalid retry type specified: {str(e)}")
        return {"statusCode": 400, "body": {"status": "400", "message": str(e)}}

    except ExecutionNotFoundError as e:
        logger.warning(f"Execution not found: {execution_id}")
        return {"statusCode": 404, "body": {"status": "404", "message": str(e)}}

    except ExecutionNotRedrivableError as e:
        logger.warning(f"Execution not redrivable: {execution_id} - {str(e)}")
        return {
            "statusCode": 400,
            "body": {
                "status": "400",
                "message": str(e),
                "suggestedAction": "USE_RETRY_FROM_START",
            },
        }

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
        # Configure PynamoDB model with environment variables
        PipelineExecution.Meta.table_name = os.environ[
            "PIPELINES_EXECUTIONS_TABLE_NAME"
        ]
        PipelineExecution.Meta.region = os.environ["AWS_REGION"]

        return app.resolve(event, context)
    except Exception:
        logger.exception("Unhandled error in lambda handler")
        metrics.add_metric(name="UnhandledErrors", unit="Count", value=1)
        return {
            "statusCode": 500,
            "body": {"message": "Internal server error", "status": "error"},
        }
