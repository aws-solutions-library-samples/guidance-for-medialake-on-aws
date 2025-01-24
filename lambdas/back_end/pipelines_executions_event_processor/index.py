from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import EventBridgeEvent
from aws_lambda_powertools.utilities.data_classes.dynamo_db_stream_event import (
    DynamoDBRecord,
)
from aws_lambda_powertools import single_metric
from typing import Dict, Any, Optional
import os
import boto3
from datetime import datetime
import json
from decimal import Decimal
from lambda_utils import lambda_handler_decorator, logger, metrics, tracer, handle_error

# Initialize AWS clients with X-Ray tracing
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["PIPELINES_EXECUTIONS_TABLE_NAME"])


def calculate_execution_duration(
    start_time: Any, end_time: Optional[str] = None
) -> Optional[Decimal]:
    """
    Calculate the duration of the execution in seconds

    Parameters
    ----------
    start_time : Any
        Start time (can be string or datetime)
    end_time : Optional[str]
        ISO formatted end time

    Returns
    -------
    Optional[Decimal]
        Duration in seconds if end_time is provided, None otherwise
    """
    if not end_time or not start_time:
        return None

    # Convert start_time to string if it's a datetime object
    if isinstance(start_time, datetime):
        start_time = start_time.isoformat()
    elif not isinstance(start_time, str):
        logger.warning(f"Invalid start_time format: {type(start_time)}")
        return None

    try:
        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time)
        # Convert to Decimal for DynamoDB compatibility
        return Decimal(str((end - start).total_seconds()))
    except (ValueError, TypeError) as e:
        logger.warning(f"Error calculating duration: {str(e)}")
        return None


@tracer.capture_method
def store_execution_details(item: Dict[str, Any]) -> None:
    """
    Store execution details in DynamoDB with tracing

    Parameters
    ----------
    item : Dict[str, Any]
        Item to store in DynamoDB
    """
    table.put_item(Item=item)


@tracer.capture_method
def extract_pipeline_name(execution_arn: str) -> str:
    """
    Extract pipeline name from Step Functions execution ARN

    Parameters
    ----------
    execution_arn : str
        Full execution ARN

    Returns
    -------
    str
        Pipeline name

    Raises
    ------
    ValueError
        If pipeline name cannot be extracted from ARN
    """
    try:
        # ARN format: arn:aws:states:region:account:execution:pipeline_name:execution_id
        pipeline_name = execution_arn.split(":")[-2]
        return pipeline_name
    except (IndexError, AttributeError):
        logger.error(f"Failed to extract pipeline name from ARN: {execution_arn}")
        raise ValueError(f"Invalid execution ARN format: {execution_arn}")


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Process Step Functions execution events and store in DynamoDB

    Parameters
    ----------
    event : Dict[str, Any]
        EventBridge event containing Step Functions execution details
    context : LambdaContext
        Lambda context object

    Returns
    -------
    Dict[str, Any]
        Response indicating processing status
    """
    try:
        # Parse event using PowerTools EventBridge data class
        event_bridge_event = EventBridgeEvent(event)
        detail = event_bridge_event.detail

        # Extract and validate required information
        execution_arn = detail.get("executionArn")
        if not execution_arn:
            raise ValueError(
                "executionArn is required but was not provided in the event"
            )

        # Extract execution_id from the ARN (last part after ':')
        execution_id = execution_arn.split(":")[-1]
        if not execution_id:
            raise ValueError("Could not extract execution_id from executionArn")

        state_machine_arn = detail.get("stateMachineArn")
        if not state_machine_arn:
            raise ValueError(
                "stateMachineArn is required but was not provided in the event"
            )

        status = detail.get("status")
        if not status:
            raise ValueError("status is required but was not provided in the event")

        # Convert startDate from milliseconds timestamp to ISO format
        start_date_ms = detail.get("startDate")
        if not start_date_ms:
            raise ValueError("startDate is required but was not provided in the event")

        try:
            start_date = datetime.fromtimestamp(start_date_ms / 1000.0).isoformat()
        except (ValueError, TypeError):
            logger.error(f"Invalid start_date format: {start_date_ms}")
            raise ValueError(f"Invalid start_date format: {start_date_ms}")

        current_time = datetime.utcnow().isoformat()

        # Log the event details for debugging
        logger.debug(
            "Processing execution event",
            extra={
                "execution_id": execution_id,
                "execution_arn": execution_arn,
                "state_machine_arn": state_machine_arn,
                "status": status,
                "start_date": start_date,
            },
        )

        # Extract pipeline name from execution ARN
        pipeline_name = extract_pipeline_name(execution_arn)
        logger.debug(
            "Extracted pipeline information",
            extra={
                "pipeline_name": pipeline_name,
                "execution_id": execution_id,
            },
        )

        # Prepare DynamoDB item
        item = {
            "execution_id": execution_id,  # Partition key
            "start_time": start_date,  # Sort key
            "pipeline_name": pipeline_name,  # Add pipeline name
            "execution_arn": execution_arn,
            "state_machine_arn": state_machine_arn,
            "status": status,
            "last_updated": current_time,
            "ttl": int(
                (datetime.utcnow().timestamp() + (90 * 24 * 60 * 60))
            ),  # 90 days TTL
        }

        # Handle execution completion
        if status in ["SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"]:
            stop_date_ms = detail.get("stopDate")
            if stop_date_ms:
                end_time = datetime.fromtimestamp(stop_date_ms / 1000.0).isoformat()
                item["end_time"] = end_time
                item["duration_seconds"] = calculate_execution_duration(
                    start_date, end_time
                )

            # Add failure details if applicable
            if status in ["FAILED", "TIMED_OUT", "ABORTED"]:
                error = detail.get("error")
                cause = detail.get("cause")
                if error:
                    item["error"] = error
                if cause:
                    item["cause"] = cause

        # Store in DynamoDB with tracing
        store_execution_details(item)

        # Add custom metrics
        metrics.add_metric(name="SuccessfulExecutionUpdates", unit="Count", value=1)
        if "duration_seconds" in item:
            # Convert duration to float for metrics
            duration = float(item["duration_seconds"])
            metrics.add_metric(name="ExecutionDuration", unit="Seconds", value=duration)

        logger.info(
            f"Successfully processed execution event",
            extra={
                "execution_id": execution_id,
                "status": status,
                "duration_seconds": item.get("duration_seconds"),
            },
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Successfully processed execution event",
                    "execution_id": execution_id,
                    "status": status,
                }
            ),
        }

    except Exception as e:
        # Log error with context
        logger.exception("Error processing execution event")
        metrics.add_metric(name="FailedExecutionUpdates", unit="Count", value=1)
        raise
