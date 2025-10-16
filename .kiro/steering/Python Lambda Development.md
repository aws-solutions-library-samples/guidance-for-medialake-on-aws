---
inclusion: fileMatch
fileMatchPattern: ['lambdas/**/*.py', '**/*lambda*.py']
---

# Python Lambda Development Standards

## Core Principles

MediaLake Lambda functions follow a standardized architecture using AWS Lambda Powertools for observability, custom middleware for event normalization, and consistent error handling patterns.

## Required Imports and Initialization

Every Lambda function MUST initialize these core utilities:

```python
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize at module level
logger = Logger()
tracer = Tracer()
metrics = Metrics()
```

## Handler Patterns

### Standard API Gateway Handler

Use this pattern for API Gateway Lambda functions:

```python
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Handler description"""
    logger.info("Processing request")
    # Implementation
    return {"statusCode": 200, "body": json.dumps(result)}
```

### Pipeline/Step Functions Handler

For pipeline nodes and Step Functions tasks, use the LambdaMiddleware:

```python
from lambda_middleware import LambdaMiddleware, is_lambda_warmer_event

middleware = LambdaMiddleware(
    event_bus_name=os.getenv("EVENT_BUS_NAME"),
    external_payload_bucket=os.getenv("EXTERNAL_PAYLOAD_BUCKET"),
    assets_table_name=os.getenv("MEDIALAKE_ASSET_TABLE")
)

@middleware
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    # Check for warmer events
    if is_lambda_warmer_event(event):
        return {"warmed": True}
    
    # Event is automatically normalized to {metadata, payload: {data, assets}}
    data = event["payload"]["data"]
    assets = event["payload"]["assets"]
    
    # Process and return result
    return {"result": processed_data}
```

## Event Structure Conventions

### Middleware-Normalized Events

The LambdaMiddleware normalizes all events to this structure:

```python
{
    "metadata": {
        "service": "service-name",
        "stepName": "step-name",
        "pipelineExecutionId": "exec-id",
        "pipelineId": "pipeline-id",
        "pipelineTraceId": "trace-id",
        "stepExternalPayload": "False",  # "True" if payload offloaded to S3
        "stepExternalPayloadLocation": {}
    },
    "payload": {
        "data": {},  # Your business data
        "assets": [],  # Asset records from DynamoDB
        "map": {"item": {}}  # Optional: for Map state iterations
    }
}
```

### Large Payload Handling

The middleware automatically offloads payloads exceeding 240KB to S3 and creates lightweight placeholders. When `stepExternalPayload` is "True", the middleware automatically downloads the full payload from S3 before your handler executes.

## Error Handling

### Use Custom Error Classes

Import and use the error handling utilities:

```python
from lambda_error_handler import (
    check_response_status,
    ResponseError,
    ApiError,
    ValidationError,
    with_error_handling
)

# Check response status
check_response_status(response, "ServiceName", "operation")

# Handle API responses
result = handle_api_response(response, "API Name", "/endpoint")

# Raise validation errors
if not field:
    raise ValidationError("Field is required", field="fieldName", value=None)
```

### Decorator-Based Error Handling

For comprehensive error handling:

```python
@with_error_handling
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    # Automatically handles exceptions and returns formatted error responses
    pass
```

## Logging Standards

### Structured Logging

Always use structured logging with context:

```python
logger.info("Operation completed", extra={
    "operation": "process_asset",
    "asset_id": asset_id,
    "duration_ms": duration
})

logger.error("Operation failed", extra={
    "error_type": type(e).__name__,
    "error_message": str(e),
    "context": additional_context
})
```

### Log Levels

- **DEBUG**: Detailed diagnostic information (disabled in production)
- **INFO**: General informational messages about operation flow
- **WARNING**: Warning messages for recoverable issues
- **ERROR**: Error messages for failures requiring attention

## Metrics and Observability

### Add Custom Metrics

```python
# Count metrics
metrics.add_metric(name="ProcessedAssets", unit=MetricUnit.Count, value=1)

# Timing metrics
metrics.add_metric(name="ProcessingTime", unit=MetricUnit.Milliseconds, value=duration_ms)

# Add dimensions
metrics.add_dimension(name="AssetType", value="video")
```

### Tracing

Use the tracer for method-level tracing:

```python
@tracer.capture_method
def process_asset(asset_id: str) -> Dict[str, Any]:
    # Method execution is automatically traced
    pass
```

## Environment Variables

### Required Variables

Access environment variables with fallbacks:

```python
import os

# Required variables - fail fast if missing
EVENT_BUS_NAME = os.environ["EVENT_BUS_NAME"]
ASSETS_TABLE = os.environ["MEDIALAKE_ASSET_TABLE"]

# Optional variables with defaults
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
TIMEOUT = int(os.getenv("TIMEOUT", "60"))
```

### Configuration Validation

Use the error handler to validate required environment variables:

```python
from lambda_error_handler import check_required_env_vars

check_required_env_vars([
    "EVENT_BUS_NAME",
    "EXTERNAL_PAYLOAD_BUCKET",
    "MEDIALAKE_ASSET_TABLE"
])
```

## AWS Service Integration

### DynamoDB Operations

```python
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

try:
    response = table.get_item(Key={"id": item_id})
    item = response.get("Item")
except ClientError as e:
    logger.error("DynamoDB error", extra={
        "error_code": e.response["Error"]["Code"],
        "error_message": e.response["Error"]["Message"]
    })
    raise
```

### S3 Operations

```python
s3 = boto3.client("s3")

# Upload with error handling
try:
    s3.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=data,
        ContentType="application/json"
    )
except ClientError as e:
    logger.error("S3 upload failed", extra={"bucket": bucket_name, "key": key})
    raise
```

### EventBridge Publishing

```python
events = boto3.client("events")

events.put_events(
    Entries=[{
        "Source": "medialake.service",
        "DetailType": "AssetProcessed",
        "Detail": json.dumps(event_data),
        "EventBusName": event_bus_name
    }]
)
```

## Response Formatting

### API Gateway Responses

```python
def success_response(data: Any, status_code: int = 200) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(data)
    }

def error_response(message: str, status_code: int = 500) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "error": message,
            "requestId": logger.get_correlation_id()
        })
    }
```

## Testing Considerations

### Lambda Warmer Events

Always check for warmer events at the start of your handler:

```python
from lambda_middleware import is_lambda_warmer_event

if is_lambda_warmer_event(event):
    return {"warmed": True}
```

### Mock AWS Services

Use moto or boto3 stubber for testing:

```python
from moto import mock_dynamodb, mock_s3

@mock_dynamodb
def test_lambda_handler():
    # Test implementation
    pass
```

## Performance Optimization

### Connection Reuse

Initialize AWS clients at module level for connection reuse across invocations:

```python
# Module level - reused across invocations
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

def lambda_handler(event, context):
    # Use pre-initialized clients
    pass
```

### Minimize Cold Starts

- Keep deployment packages small
- Use Lambda layers for shared dependencies
- Minimize initialization code
- Use provisioned concurrency for critical functions

## Common Patterns

### Pagination

```python
def paginate_results(table, query_params):
    items = []
    last_evaluated_key = None
    
    while True:
        if last_evaluated_key:
            query_params["ExclusiveStartKey"] = last_evaluated_key
        
        response = table.query(**query_params)
        items.extend(response.get("Items", []))
        
        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break
    
    return items
```

### Retry Logic

```python
import time
from botocore.exceptions import ClientError

def retry_with_backoff(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except ClientError as e:
            if e.response["Error"]["Code"] == "ProvisionedThroughputExceededException":
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Throttled, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
            raise
```

## Constants Usage

Always use constants from `constants.py`:

```python
from constants import Lambda, DynamoDB, S3

# Lambda configuration
memory_size = Lambda.DEFAULT_MEMORY_SIZE
timeout = Lambda.DEFAULT_TIMEOUT_SECONDS

# Table names
table_name = DynamoDB.connector_table_name(environment)

# S3 bucket names
bucket_name = S3.ASSETS_BUCKET_EXPORT
```

## Security Best Practices

- Never log sensitive data (credentials, tokens, PII)
- Use IAM roles, not access keys
- Validate all inputs before processing
- Sanitize data before storing or returning
- Use encryption for sensitive data at rest and in transit
- Follow least-privilege principle for IAM policies

Imports from Same Directory
	•	Use standard imports:
   from my_module import my_function

	•	Keep your module file in the same directory as your handler.
   Imports from Subdirectories
   	•	Add an  __init__.py  (can be empty) in every subfolder involved.
      from subfolder.my_module import my_function



For all Lambdas use AWS Power Tools from the layer, it will be attached automatically and be version controlled

Use the following file directory 

{lambda_root_directory}/handlers/ - routes based off of API routes
{lambda_root_directory}/models/ - models for the lambda
{lambda_root_directory}/services/ - services for the lambda
{lambda_root_directory}/utils/ - utils for the lambda 


For files in the handklers directory, use the following naming convention: 

{lambda_root_directory}/handlers/route_method.py
For example:

{lambda_root_directory}/handlers/users_get.py

If there's a route parameter in the route then use the router parameter name _ID for example:

{lambda_root_directory}/handlers/users_userID_get.py

If there's multiple levels of routes then use _ to seperate between them for example

users_userID_groups_get.py


If this is a Lambda that is handling a API root level resource, then create an openAPI spec that is 3.X compliant and stick it at the root level in YAML format with the name of the route, for example:

{lambda_root_directory}/users_openAPI.yaml

Ensure that you put in all endpoints, request, and response data models including examples.




Always use aws_power_tools for logging, tracing, and metrics.

For Python AWS Lambda functions using AWS Lambda Powertools, best practices for logging include using structured JSON logs, consistently including Lambda context, tagging logs with service names, configuring log level via environment variables, and leveraging Powertools features like correlation IDs and cold start detection[1][2][3].

### Key Logging Best Practices

- **Structured JSON Logging**
  - Use `aws_lambda_powertools.Logger` to ensure logs are output in a structured JSON format by default, which improves downstream parsing in CloudWatch and other analytics tools[1][2].
  - Example:
    ```python
    from aws_lambda_powertools import Logger
    logger = Logger(service="your-service-name")
    logger.info("Processing started")
    ```

- **Include Service and Context**
  - Tag logs with a service name using the logger constructor or environment variable `POWERTOOLS_SERVICE_NAME`[1].
  - Always inject Lambda context with `logger.inject_lambda_context(handler)`. This decorates logs with trace IDs, function name, memory, cold start, and other metadata[2][1].

- **Configurable Log Levels**
  - Set log levels via the `POWERTOOLS_LOG_LEVEL` environment variable for easy deployment control[1].
  - Lower verbosity in production (INFO or WARN); use sampling for DEBUG logs: `POWERTOOLS_LOGGER_SAMPLE_RATE`[2][3].

- **Correlation IDs and Request Metadata**
  - Use Powertools' automatic extraction of correlation IDs from API Gateway and other event sources to tie requests across systems[2][4].
  - Log every incoming event for debugging in development by setting `log_event=True` in the decorator[2].

- **Appending Event-Specific Keys**
  - Add custom keys (like user IDs, payment IDs) using `logger.append_keys()` at runtime[5][4].

### Sample Lambda Handler with Powertools

```python
from aws_lambda_powertools import Logger

logger = Logger(service="orders")

@logger.inject_lambda_context(log_event=True)
def handler(event, context):
    logger.append_keys(order_id=event.get("order_id"))
    logger.info("Order processed")
```
This produces logs like:
```json
{
  "level": "INFO",
  "message": "Order processed",
  "service": "orders",
  "order_id": "12345",
  "timestamp": "2025-10-10T13:50:02.145Z",
  "function_name": "OrderFunction",
  "cold_start": true
}
```


### Additional Recommendations

- Ensure logs always include timestamps and use UTC for consistency
- Never log sensitive data.


A predictable log structure for AWS Lambda functions using AWS Lambda Powertools (Python) is a consistent JSON object that includes standard metadata (like service, context, and event identifiers), custom business keys, a log level, timestamp, and the main log message—all with stable field names and value types

### Example of a Predictable Log Structure

```json
{
  "timestamp": "2025-10-10T20:52:44.126Z",
  "level": "INFO",
  "service": "users_api",
  "message": "File ingested successfully",
  "function_name": "medialake_users_api_handler_dev",
  "function_memory_size": 512,
  "function_arn": "arn:aws:lambda:us-west-2:123456789012:function:medialake_users_api_handler_dev",
  "aws_request_id": "792aeec6-f055-4f5e-a3a7-72bc167df8d8",
  "cold_start": true,
  "correlation_id": "trace-123abc456def",
  "event_source": "S3",
  "file_id": "a1b2c3d4.mp4",
  "user_id": "user-987654"
}
```


### Explanation of Core Fields

- **timestamp:** ISO8601 string, always UTC
- **level:** Log severity (INFO, DEBUG, WARN, ERROR)
- **service:** Application or workflow name (set per Lambda, via Powertools)
- **message:** Human-readable log message, always present
- **function_name / function_memory_size / function_arn / aws_request_id / cold_start:** Lambda context injected by Powertools, enabling traceability and cold start analysis
- **correlation_id:** Trace or request correlation key, for linking across distributed systems
- **event_source:** (custom) Source of the event, such as S3, API Gateway, etc.
- **file_id, user_id:** (custom) Key business/domain fields relevant to the operation

### Predictable Log Structure Guidelines

- Every log entry is a self-contained JSON object.
- All fields use lowercase with underscores.
- Time is always in UTC ISO8601.
- The same structure applies to every log call, regardless of the handler or code path.
- Custom keys can be appended as needed for business context, but core metadata is always present.

This structure supports automated parsing (e.g., CloudWatch Insights), correlates logs across services, and ensures operational consistency for search and analysis