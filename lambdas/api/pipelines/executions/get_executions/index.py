import base64
import json
import os
from typing import Any, Dict

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.api_gateway import CORSConfig
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
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


def encode_last_evaluated_key(
    last_evaluated_key: Dict,
    sort_by: str = None,
    sort_order: str = None,
    last_sort_value: Any = None,
) -> str:
    """Encode the LastEvaluatedKey and sort parameters to a base64 string"""
    # Create token data - last_key can be empty dict for client-side pagination
    token_data = {
        "last_key": last_evaluated_key if last_evaluated_key else {},
        "sort_by": sort_by,
        "sort_order": sort_order,
        "last_sort_value": last_sort_value,
    }
    return base64.b64encode(json.dumps(token_data).encode()).decode()


def decode_last_evaluated_key(encoded_key: str) -> Dict:
    """Decode the base64 string back to LastEvaluatedKey and sort parameters"""
    if not encoded_key:
        return None
    try:
        token_data = json.loads(base64.b64decode(encoded_key.encode()).decode())
        # Handle old format (just the last_key) for backward compatibility
        if isinstance(token_data, dict) and "last_key" in token_data:
            return token_data
        # Old format - just return as last_key
        return {
            "last_key": token_data,
            "sort_by": None,
            "sort_order": None,
            "last_sort_value": None,
        }
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
        "ttl": str(execution.ttl),  # Convert to string for JSON
    }

    # Add optional fields if they exist
    if hasattr(execution, "end_time") and execution.end_time is not None:
        response["end_time"] = str(execution.end_time)
    if hasattr(execution, "end_time_iso") and execution.end_time_iso is not None:
        response["end_time_iso"] = execution.end_time_iso

    # Add duration_seconds - prefer stored value over calculated
    if (
        hasattr(execution, "duration_seconds")
        and execution.duration_seconds is not None
    ):
        response["duration_seconds"] = str(execution.duration_seconds)
    elif hasattr(execution, "end_time") and execution.end_time is not None:
        # Calculate duration in seconds if not stored
        try:
            start_time_int = int(execution.start_time)
            end_time_int = int(execution.end_time)
            duration_seconds = end_time_int - start_time_int
            response["duration_seconds"] = str(duration_seconds)
        except (ValueError, TypeError):
            response["duration_seconds"] = "0"

    # Add additional optional fields
    if hasattr(execution, "dsa_type") and execution.dsa_type is not None:
        response["dsa_type"] = execution.dsa_type
    if hasattr(execution, "inventory_id") and execution.inventory_id is not None:
        response["inventory_id"] = execution.inventory_id
    if hasattr(execution, "object_key_name") and execution.object_key_name is not None:
        response["object_key_name"] = execution.object_key_name
    if (
        hasattr(execution, "pipeline_trace_id")
        and execution.pipeline_trace_id is not None
    ):
        response["pipeline_trace_id"] = execution.pipeline_trace_id
    if hasattr(execution, "stepname") and execution.stepname is not None:
        response["stepname"] = execution.stepname
    if hasattr(execution, "stepresult") and execution.stepresult is not None:
        response["stepresult"] = execution.stepresult
    if hasattr(execution, "stepstatus") and execution.stepstatus is not None:
        response["stepstatus"] = execution.stepstatus
    if hasattr(execution, "metadata") and execution.metadata is not None:
        # Convert MapAttribute to dict for JSON serialization
        response["metadata"] = (
            execution.metadata.as_dict()
            if hasattr(execution.metadata, "as_dict")
            else dict(execution.metadata)
        )

    return response


@tracer.capture_method
def get_pipeline_executions(
    page_size: int,
    next_token: str = None,
    status: str = None,
    sort_by: str = "start_time",
    sort_order: str = "desc",
    search: str = None,
) -> Dict[str, Any]:
    """
    Retrieve paginated pipeline executions from DynamoDB using PynamoDB
    """
    try:
        logger.info(
            f"Getting pipeline executions with search: {search}, status: {status}, sort_by: {sort_by}, sort_order: {sort_order}"
        )

        # Decode and validate token if provided
        token_data = None
        last_sort_value = None
        if next_token:
            token_data = decode_last_evaluated_key(next_token)
            if token_data:
                # Check if sort parameters changed - if so, ignore token
                token_sort_by = token_data.get("sort_by")
                token_sort_order = token_data.get("sort_order")
                if token_sort_by != sort_by or token_sort_order != sort_order:
                    logger.warning(
                        f"Sort parameters changed (was {token_sort_by}/{token_sort_order}, now {sort_by}/{sort_order}). Resetting pagination."
                    )
                    token_data = None
                else:
                    last_sort_value = token_data.get("last_sort_value")

        # Configure scan parameters
        scan_kwargs = {}

        # Add status filter if provided
        if status:
            scan_kwargs["filter_condition"] = PipelineExecution.status == status

        # For initial request (no token): scan ALL items to ensure correct sorting
        # DynamoDB scan returns items in arbitrary order, so we must retrieve all items
        # to sort properly by any field (start_time, end_time, pipeline_name, status, etc.)
        # For subsequent pages: continue from where we left off using last_sort_value filtering
        if token_data and token_data.get("last_key"):
            last_key = token_data["last_key"]
            # Only use DynamoDB last_evaluated_key if it's not an empty placeholder
            if last_key:  # Check if not empty dict
                scan_kwargs["last_evaluated_key"] = last_key
                scan_kwargs["limit"] = page_size * 3  # Limit for subsequent pages
        # else: no limit - scan all items for proper sorting across any sortable field

        # Execute scan
        executions = []
        count = 0
        total_scanned = 0

        # Perform the scan
        scan_operation = PipelineExecution.scan(**scan_kwargs)

        # Get items and apply search filter if provided
        for item in scan_operation:
            total_scanned += 1

            # Apply search filter if search term is provided
            if search:
                search_term = search.lower()
                # Search across multiple fields
                searchable_fields = [
                    item.pipeline_name or "",
                    item.status or "",
                    item.execution_id or "",
                    getattr(item, "dsa_type", "") or "",
                    getattr(item, "object_key_name", "") or "",
                    getattr(item, "pipeline_trace_id", "") or "",
                    getattr(item, "stepname", "") or "",
                    getattr(item, "stepresult", "") or "",
                    getattr(item, "stepstatus", "") or "",
                ]

                # Check if search term is found in any of the searchable fields
                if not any(search_term in field.lower() for field in searchable_fields):
                    continue

            executions.append(item)
            count += 1

        if search:
            logger.info(
                f"Search filtering: scanned {total_scanned} items, found {count} matches for term '{search}'"
            )

        # Sort based on the provided sort parameters
        reverse_order = sort_order.lower() == "desc"

        if sort_by == "start_time":
            executions.sort(key=lambda x: int(x.start_time), reverse=reverse_order)
        elif sort_by == "end_time":
            executions.sort(
                key=lambda x: (
                    int(x.end_time)
                    if hasattr(x, "end_time") and x.end_time is not None
                    else 0
                ),
                reverse=reverse_order,
            )
        elif sort_by == "pipeline_name":
            executions.sort(
                key=lambda x: x.pipeline_name.lower(), reverse=reverse_order
            )
        elif sort_by == "status":
            executions.sort(key=lambda x: x.status.lower(), reverse=reverse_order)
        elif sort_by == "execution_id":
            executions.sort(key=lambda x: x.execution_id.lower(), reverse=reverse_order)
        elif sort_by == "duration_seconds":
            # Sort by duration - prefer stored value over calculated
            def get_duration(x):
                if hasattr(x, "duration_seconds") and x.duration_seconds is not None:
                    try:
                        return int(x.duration_seconds)
                    except (ValueError, TypeError):
                        return 0
                elif hasattr(x, "end_time") and x.end_time is not None:
                    try:
                        return int(x.end_time) - int(x.start_time)
                    except (ValueError, TypeError):
                        return 0
                return 0

            executions.sort(key=get_duration, reverse=reverse_order)
        elif sort_by == "dsa_type":
            executions.sort(
                key=lambda x: (x.dsa_type or "").lower(), reverse=reverse_order
            )
        elif sort_by == "object_key_name":
            executions.sort(
                key=lambda x: (x.object_key_name or "").lower(), reverse=reverse_order
            )
        elif sort_by == "pipeline_trace_id":
            executions.sort(
                key=lambda x: (x.pipeline_trace_id or "").lower(), reverse=reverse_order
            )
        elif sort_by == "stepname":
            executions.sort(
                key=lambda x: (x.stepname or "").lower(), reverse=reverse_order
            )
        elif sort_by == "stepresult":
            executions.sort(
                key=lambda x: (x.stepresult or "").lower(), reverse=reverse_order
            )
        elif sort_by == "stepstatus":
            executions.sort(
                key=lambda x: (x.stepstatus or "").lower(), reverse=reverse_order
            )
        else:
            # Default to start_time if unknown sort field
            executions.sort(key=lambda x: int(x.start_time), reverse=reverse_order)

        # Apply pagination to sorted results
        # If we have a last_sort_value from previous page, filter out items we've already seen
        if last_sort_value is not None and len(executions) > 0:
            reverse_order = sort_order.lower() == "desc"
            filtered_executions = []

            for execution in executions:
                if sort_by == "start_time":
                    current_value = int(execution.start_time)
                    if reverse_order:
                        # desc: include items older than last value
                        if current_value < last_sort_value:
                            filtered_executions.append(execution)
                    else:
                        # asc: include items newer than last value
                        if current_value > last_sort_value:
                            filtered_executions.append(execution)
                elif sort_by == "end_time":
                    if (
                        hasattr(execution, "end_time")
                        and execution.end_time is not None
                    ):
                        current_value = int(execution.end_time)
                        if reverse_order:
                            if current_value < last_sort_value:
                                filtered_executions.append(execution)
                        else:
                            if current_value > last_sort_value:
                                filtered_executions.append(execution)
                # Add other sort fields as needed
                else:
                    # For string comparisons, just add all (fallback)
                    filtered_executions.append(execution)

            executions = filtered_executions

        # Limit to requested page size
        has_more = len(executions) > page_size
        executions = executions[:page_size]

        # Format executions for response
        formatted_executions = [
            format_execution_response(execution) for execution in executions
        ]

        # Get the next token for pagination
        next_token = None
        if has_more and len(executions) > 0:
            # Get the last item's sort value for next page filtering
            last_execution = executions[-1]
            last_sort_val = None

            if sort_by == "start_time":
                last_sort_val = int(last_execution.start_time)
            elif (
                sort_by == "end_time"
                and hasattr(last_execution, "end_time")
                and last_execution.end_time
            ):
                last_sort_val = int(last_execution.end_time)

            # Create next token with last_evaluated_key if available (for subsequent pages)
            # or with empty dict (for initial full scan) - the last_sort_value is what matters
            last_key = None
            if (
                hasattr(scan_operation, "last_evaluated_key")
                and scan_operation.last_evaluated_key
            ):
                last_key = scan_operation.last_evaluated_key
            else:
                # For initial full scan, use empty dict as placeholder
                # The last_sort_value will handle pagination
                last_key = {}

            next_token = encode_last_evaluated_key(
                last_key,
                sort_by,
                sort_order,
                last_sort_val,
            )

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
        raise PipelineExecutionError(
            f"Failed to retrieve pipeline executions: {str(e)}"
        )


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

        # Get search parameter if provided
        search = query_string.get("search")

        # Get sorting parameters
        sort_by = query_string.get("sortBy", "start_time")
        sort_order = query_string.get("sortOrder", "desc")

        return get_pipeline_executions(
            page_size, next_token, status, sort_by, sort_order, search
        )
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
        PipelineExecution.Meta.table_name = os.environ[
            "PIPELINES_EXECUTIONS_TABLE_NAME"
        ]
        PipelineExecution.Meta.region = os.environ["AWS_REGION"]

        return app.resolve(event, context)
    except Exception:
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
