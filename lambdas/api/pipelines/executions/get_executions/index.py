import os
import json
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from typing import Dict, Any, List
from aws_lambda_powertools.metrics import Metrics
import base64
from datetime import datetime
from models import PipelineExecution

# Initialize Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="Pipelines")

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

app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)

# Default pagination values
DEFAULT_PAGE_SIZE = 50

class PipelineExecutionError(Exception):
    """Custom exception for pipeline execution errors"""
    pass

def encode_last_evaluated_key(last_evaluated_key: Dict) -> str:
    """Encode the LastEvaluatedKey to a base64 string"""
    if not last_evaluated_key:
        return ""
    return base64.b64encode(json.dumps(last_evaluated_key).encode()).decode()

def decode_last_evaluated_key(encoded_key: str) -> Dict:
    """Decode the base64 string back to LastEvaluatedKey"""
    if not encoded_key:
        return None
    try:
        return json.loads(base64.b64decode(encoded_key.encode()).decode())
    except:
        return None

@tracer.capture_method
def format_execution_response(execution: PipelineExecution) -> Dict[str, Any]:
    """Format execution data for API response"""
    response = {
        "execution_id": execution.execution_id,
        "start_time": str(execution.start_time),  # Convert to string for JSON
        "start_time_iso": execution.start_time_iso,
        "pipeline_name": execution.pipeline_name,
        "status": execution.status,
        "state_machine_arn": execution.state_machine_arn,
        "execution_arn": execution.execution_arn,
        "last_updated": execution.last_updated,
        "ttl": str(execution.ttl)  # Convert to string for JSON
    }

    # Add optional fields if they exist
    if hasattr(execution, 'end_time') and execution.end_time is not None:
        response["end_time"] = str(execution.end_time)
        # Calculate duration in seconds
        try:
            start_time_int = int(execution.start_time)
            end_time_int = int(execution.end_time)
            duration_seconds = end_time_int - start_time_int
            response["duration_seconds"] = str(duration_seconds)
        except (ValueError, TypeError):
            response["duration_seconds"] = "0"
    if hasattr(execution, 'end_time_iso') and execution.end_time_iso is not None:
        response["end_time_iso"] = execution.end_time_iso

    return response

@tracer.capture_method
def get_pipeline_executions(
    page_size: int, next_token: str = None, status: str = None, sort_by: str = "start_time", sort_order: str = "desc"
) -> Dict[str, Any]:
    """
    Retrieve paginated pipeline executions from DynamoDB using PynamoDB
    """
    try:
        # Configure scan parameters
        scan_kwargs = {
            "limit": page_size,
        }

        # Add status filter if provided
        if status:
            scan_kwargs["filter_condition"] = PipelineExecution.status == status

        # Add LastEvaluatedKey if next_token is provided
        if next_token:
            last_evaluated_key = decode_last_evaluated_key(next_token)
            if last_evaluated_key:
                scan_kwargs["last_evaluated_key"] = last_evaluated_key

        # Execute scan
        executions = []
        count = 0
        
        # Perform the scan
        scan_operation = PipelineExecution.scan(**scan_kwargs)
        
        # Get items
        for item in scan_operation:
            executions.append(item)
            count += 1
        
        # Sort based on the provided sort parameters
        reverse_order = sort_order.lower() == "desc"
        
        if sort_by == "start_time":
            executions.sort(key=lambda x: int(x.start_time), reverse=reverse_order)
        elif sort_by == "end_time":
            executions.sort(key=lambda x: int(x.end_time) if hasattr(x, 'end_time') and x.end_time is not None else 0, reverse=reverse_order)
        elif sort_by == "pipeline_name":
            executions.sort(key=lambda x: x.pipeline_name.lower(), reverse=reverse_order)
        elif sort_by == "status":
            executions.sort(key=lambda x: x.status.lower(), reverse=reverse_order)
        elif sort_by == "execution_id":
            executions.sort(key=lambda x: x.execution_id.lower(), reverse=reverse_order)
        elif sort_by == "duration_seconds":
            # Sort by duration (end_time - start_time)
            def get_duration(x):
                if hasattr(x, 'end_time') and x.end_time is not None:
                    try:
                        return int(x.end_time) - int(x.start_time)
                    except (ValueError, TypeError):
                        return 0
                return 0
            executions.sort(key=get_duration, reverse=reverse_order)
        else:
            # Default to start_time if unknown sort field
            executions.sort(key=lambda x: int(x.start_time), reverse=reverse_order)
        
        # Format executions for response
        formatted_executions = [format_execution_response(execution) for execution in executions]

        # Get the next token for pagination
        next_token = None
        if hasattr(scan_operation, "last_evaluated_key") and scan_operation.last_evaluated_key:
            next_token = encode_last_evaluated_key(scan_operation.last_evaluated_key)

        # Add metrics for monitoring
        metrics.add_metric(name="SuccessfulQueries", unit="Count", value=1)

        return {
            "status": "200",
            "message": "ok",
            "data": {
                "searchMetadata": {
                    "totalResults": count,
                    "pageSize": page_size,
                    "nextToken": next_token,
                },
                "executions": formatted_executions,
            },
        }

    except Exception as e:
        logger.exception("Failed to retrieve pipeline executions")
        metrics.add_metric(name="FailedQueries", unit="Count", value=1)
        raise PipelineExecutionError(f"Failed to retrieve pipeline executions: {str(e)}")

@app.get("/pipelines/executions")
@tracer.capture_method
def handle_get_executions() -> Dict[str, Any]:
    """Handle GET request for pipeline executions with pagination"""
    try:
        # Get query parameters
        query_string = app.current_event.query_string_parameters or {}

        # Parse pagination parameters
        try:
            page_size = int(query_string.get("pageSize", DEFAULT_PAGE_SIZE))
            page_size = max(1, min(100, page_size))
        except (ValueError, TypeError):
            page_size = DEFAULT_PAGE_SIZE

        # Get the next token for pagination
        next_token = query_string.get("nextToken")

        # Get status filter if provided
        status = query_string.get("status")
        
        # Get sorting parameters
        sort_by = query_string.get("sortBy", "start_time")
        sort_order = query_string.get("sortOrder", "desc")

        return get_pipeline_executions(page_size, next_token, status, sort_by, sort_order)
    except PipelineExecutionError as e:
        logger.exception("Error processing pipeline executions request")
        return {
            "status": "500",
            "message": str(e),
            "data": {
                "searchMetadata": {
                    "totalResults": 0,
                    "pageSize": DEFAULT_PAGE_SIZE,
                    "nextToken": None,
                },
                "executions": [],
            },
        }

@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """Main Lambda handler"""
    try:
        # Configure PynamoDB model with environment variables
        PipelineExecution.Meta.table_name = os.environ["PIPELINES_EXECUTIONS_TABLE_NAME"]
        PipelineExecution.Meta.region = os.environ["AWS_REGION"]
        
        return app.resolve(event, context)
    except Exception as e:
        logger.exception("Error in lambda handler")
        return {
            "statusCode": 500,
            "body": {
                "status": "500",
                "message": "Internal server error",
                "data": {
                    "searchMetadata": {
                        "totalResults": 0,
                        "pageSize": DEFAULT_PAGE_SIZE,
                        "nextToken": None,
                    },
                    "executions": [],
                },
            },
        }
