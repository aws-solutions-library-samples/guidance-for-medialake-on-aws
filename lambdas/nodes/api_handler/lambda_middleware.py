import os
import json
import time
import uuid
from functools import wraps
from typing import Any, Dict, Optional, Callable, TypeVar, Union
from typing_extensions import ParamSpec

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.middleware_factory import lambda_handler_decorator

# Type variables for better type hinting
P = ParamSpec("P")
R = TypeVar("R")


class LambdaMiddleware:
    """
    Middleware for AWS Lambda functions that provides:
    - EventBridge integration for progress/status updates
    - CloudWatch metrics for monitoring
    - Payload size management with S3 fallback
    - Standardized error handling
    - Input/output payload standardization

    The output is standardized to the following format:

    {
        "metadata": {
            "service": "S3EventIngest",           # Mandatory
            "stepName": "assetRegistration",      # Mandatory
            "stepStatus": "Completed",            # Mandatory - ENUM (Started, InProgress, Completed)
            "stepId": "",                         # Mandatory - UID Generated and logged
            "externalTaskId": "",                 # Optional
            "externalTaskStatus": "",             # Optional enum (completed, inProgress, Started)
            "externalPayload": "",                # Mandatory  (True or False)
            "externalPayloadLocation": {          # Optional, mandatory if externalPayload is set to True
                "bucket": "bucket-name",
                "key": "object-key"
            },
            "stepCost": "",                       # Optional
            "stepResult": "",                     # Optional
            "stepDuration": ""                    # Optional
        },
        "payload": {                            # Mandatory
            "assets": [],
            "rights": [],
            "titles": [],
            "tasks": []
        }
    }
    """

    def __init__(
        self,
        event_bus_name: str,
        metrics_namespace: str = "MediaLake",
        max_event_size: int = 256000,  # EventBridge max size is 256KB
        cleanup_s3: bool = True,
        large_payload_bucket: Optional[str] = None,
        max_retries: int = 3,
        standardize_payloads: bool = True,
        external_payload_bucket: Optional[str] = None,
        max_response_size: int = 240 * 1024,  # 240KB in bytes
    ):
        # Initialize EventBridge and S3 clients
        self.event_bus = boto3.client("events")
        self.event_bus_name = event_bus_name
        self.max_event_size = max_event_size
        self.cleanup_s3 = cleanup_s3
        self.max_retries = max_retries
        self.s3 = boto3.client("s3")
        self.max_response_size = max_response_size

        # Set up large payload handling
        self.large_payload_bucket = large_payload_bucket or os.environ.get("EXTERNAL_PAYLOAD_BUCKET")
        if not self.large_payload_bucket:
            raise ValueError(
                "large_payload_bucket must be provided or EXTERNAL_PAYLOAD_BUCKET environment variable must be set"
            )
            
        # Set up external payload handling
        self.external_payload_bucket = external_payload_bucket or os.environ.get("EXTERNAL_PAYLOAD_BUCKET")
        if not self.external_payload_bucket:
            raise ValueError(
                "external_payload_bucket must be provided or EXTERNAL_PAYLOAD_BUCKET environment variable must be set"
            )

        # Initialize Powertools utilities
        self.service_name = os.getenv("SERVICE_NAME", "undefined_service")
        self.logger = Logger(service=self.service_name)
        self.metrics = Metrics(namespace=metrics_namespace, service=self.service_name)
        self.tracer = Tracer(service=self.service_name)

        # Track temporary S3 objects for cleanup
        self.temp_s3_objects = []
        self.standardize_payloads = standardize_payloads

        # Initialize retry tracking
        self.retry_count = 0
        self.retry_errors = set()

    def should_retry(self, error: Exception) -> bool:
        RETRYABLE_ERRORS = (
            "RequestTimeout",
            "InternalServerError",
            "ServiceUnavailable",
            "ConnectionError",
            "ThrottlingException",
            "TooManyRequestsException",
            "ProvisionedThroughputExceededException",
        )
        error_type = error.__class__.__name__
        self.retry_errors.add(error_type)
        return self.retry_count < self.max_retries and any(err in error_type for err in RETRYABLE_ERRORS)

    def emit_progress(
        self,
        context: LambdaContext,
        progress: float,
        status: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        progress_details = {
            "function_name": context.function_name,
            "request_id": context.aws_request_id,
            "progress": progress,
            "status": status,
            "timestamp": int(time.time()),
        }
        if detail:
            progress_details.update(detail)
        self.emit_event(
            detail_type="FunctionExecutionProgress",
            detail=progress_details,
            resources=[context.invoked_function_arn],
        )

    def standardize_input(self, event: Dict[str, Any]) -> Dict[str, Any]:
        if not self.standardize_payloads:
            return event

        # Check if this is an event with S3 payload reference
        if "s3_bucket" in event and "s3_key" in event:
            try:
                response = self.s3.get_object(Bucket=event["s3_bucket"], Key=event["s3_key"])
                event = json.loads(response["Body"].read().decode("utf-8"))
            except Exception as e:
                self.logger.error(f"Failed to fetch payload from S3: {str(e)}")
                raise

        # Check if the event has an item property with S3 bucket and key information
        if "item" in event and isinstance(event["item"], dict) and "item" in event["item"] and "iteration" in event["item"]:
            try:
                self.logger.info("Detected item with S3 reference and iteration")
                bucket = event["item"]["item"]["bucket"]
                key = event["item"]["item"]["key"]
                iteration = event["item"]["iteration"]
                
                self.logger.info(f"Retrieving payload from S3: bucket={bucket}, key={key}, iteration={iteration}")
                
                # Retrieve the payload from S3
                response = self.s3.get_object(Bucket=bucket, Key=key)
                payload_data = response["Body"].read().decode("utf-8")
                payload_json = json.loads(payload_data)
                
                # Check if the payload has an array that we can index into
                if "externalTaskResults" in payload_json and isinstance(payload_json["externalTaskResults"], list):
                    array_data = payload_json["externalTaskResults"]
                    self.logger.info(f"Found array with {len(array_data)} items in payload")
                    
                    # Use the iteration value to index into the array
                    if 0 <= iteration < len(array_data):
                        self.logger.info(f"Using item at index {iteration} from array")
                        event["item"] = array_data[iteration]
                    else:
                        self.logger.warning(f"Iteration {iteration} is out of bounds for array of length {len(array_data)}")
                else:
                    self.logger.info("No array found in payload, using the entire payload as the item")
                    event["item"] = payload_json
                
                self.logger.info("Successfully processed item with S3 reference and iteration")
            except Exception as e:
                self.logger.error(f"Failed to process item with S3 reference: {str(e)}")
                raise

        # Check if this event has an external payload stored in S3
        if event.get("metadata", {}).get("externalPayload", False):
            try:
                self.logger.info("Detected external payload flag, retrieving payload from S3")
                
                # Check for externalTaskResults first (new format)
                if "payload" in event and "externalTaskResults" in event["payload"] and isinstance(event["payload"]["externalTaskResults"], list) and len(event["payload"]["externalTaskResults"]) > 0:
                    # Handle the new format with item and iteration properties
                    if "item" in event["payload"]["externalTaskResults"][0]:
                        bucket = event["payload"]["externalTaskResults"][0]["item"]["bucket"]
                        key = event["payload"]["externalTaskResults"][0]["item"]["key"]
                    # Handle the old format with direct bucket and key properties
                    else:
                        bucket = event["payload"]["externalTaskResults"][0]["bucket"]
                        key = event["payload"]["externalTaskResults"][0]["key"]
                    self.logger.info(f"Retrieving external payload from externalTaskResults: bucket={bucket}, key={key}")
                # Fall back to externalPayloadLocation (old format)
                elif "payload" in event and "externalPayloadLocation" in event["payload"]:
                    # Handle both array and object formats for backward compatibility
                    if isinstance(event["payload"]["externalPayloadLocation"], list) and len(event["payload"]["externalPayloadLocation"]) > 0:
                        bucket = event["payload"]["externalPayloadLocation"][0]["bucket"]
                        key = event["payload"]["externalPayloadLocation"][0]["key"]
                    else:
                        bucket = event["payload"]["externalPayloadLocation"]["bucket"]
                        key = event["payload"]["externalPayloadLocation"]["key"]
                    self.logger.info(f"Retrieving external payload from externalPayloadLocation: bucket={bucket}, key={key}")
                else:
                    self.logger.error("External payload flag is set but payload location is missing")
                    raise ValueError("External payload flag is set but payload location is missing")
                
                # Retrieve and process the payload
                response = self.s3.get_object(Bucket=bucket, Key=key)
                payload_data = response["Body"].read().decode("utf-8")
                
                # Replace the reference with the actual payload
                event["payload"] = json.loads(payload_data)
                event["metadata"]["externalPayload"] = False
                self.logger.info("Successfully retrieved external payload from S3")
            except Exception as e:
                self.logger.error(f"Failed to retrieve external payload from S3: {str(e)}")
                raise

        if "metadata" not in event:
            event["metadata"] = {}
        event["metadata"].update({"timestamp": int(time.time()), "service": self.service_name})
        return event

    def standardize_output(self, result: Any, original_event: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Wraps the handler result in the standardized output format.
        If InventoryID exists in the event, adds it to the assets array.
        If the payload is too large, stores it in S3 and returns a reference.
        """
        if not self.standardize_payloads:
            return result

        # Ensure the handler's result is a dict; otherwise, wrap it.
        payload_content = result if isinstance(result, dict) else {"data": result}

        # Build metadata according to the required standard.
        metadata = {
            "service": self.service_name,             # e.g., "S3EventIngest"
            "stepName": "assetRegistration",           # Mandatory step name
            "stepStatus": "Completed",                 # Expected to be one of: Started, InProgress, Completed
            "stepId": str(uuid.uuid4()),               # Generate a unique ID
            "externalTaskId": "",                      # Optional: set if applicable
            "externalTaskStatus": "",                  # Optional: e.g., "completed", "inProgress", "Started"
            "externalPayload": False,                  # Mandatory: True or False
            "externalPayloadLocation": None,           # Optional: must be filled if externalPayload is True
            "stepCost": "",                            # Optional cost information
            "stepResult": "",                          # Optional result details
            "stepDuration": ""                         # Optional duration info
        }

        # Preserve existing assets array if it exists, or initialize a new one
        # existing_assets = []
        
        # # Check if there's an existing assets array in the result
        # if "assets" in payload_content:
        #     existing_assets = payload_content["assets"]
        #     self.logger.info(f"Found existing assets in result: {existing_assets}")
        
        # # Initialize assets array if it doesn't exist
        # payload_content["assets"] = existing_assets if isinstance(existing_assets, list) else []

        # Preserve existing assets array if it exists, or initialize a new one
        existing_assets = []

        # Check if there's an existing assets array in the result
        if "assets" in payload_content:
            existing_assets = payload_content["assets"]
            self.logger.info(f"Found existing assets in result: {existing_assets}")
        # If not in the result, check if there's an assets array in the original event's payload
        elif original_event and "payload" in original_event and "assets" in original_event["payload"]:
            existing_assets = original_event["payload"]["assets"]
            self.logger.info(f"Found existing assets in original event: {existing_assets}")

        # Initialize assets array if it doesn't exist
        payload_content["assets"] = existing_assets if isinstance(existing_assets, list) else []
        
        # Check if DigitalSourceAsset ID exists in the original event and add it to assets array
        if original_event and "detail" in original_event:
            detail = original_event.get("detail", {})
            outputs = detail.get("outputs", {})
            input_data = outputs.get("input", {})
            
            asset_id = input_data.get("DigitalSourceAsset", {}).get("ID")
            if asset_id:
                self.logger.info(f"Found DigitalSourceAsset ID in event: {asset_id}")
                # Add DigitalSourceAsset ID to assets array if not already present
                if asset_id not in payload_content["assets"]:
                    payload_content["assets"].append(asset_id)
                    self.logger.info(f"Added DigitalSourceAsset Id to assets array: {asset_id}")
                else:
                    self.logger.info(f"DigitalSourceAsset ID already exists in assets array: {asset_id}")
        
        # Ensure all asset IDs in the array are unique
        if payload_content["assets"]:
            payload_content["assets"] = list(set(payload_content["assets"]))
            self.logger.info(f"Final assets array after deduplication: {payload_content['assets']}")

        output = {
            "metadata": metadata,
            "payload": payload_content
        }
        
        # Check if the output size exceeds the maximum allowed size
        output_size = len(json.dumps(output).encode("utf-8"))
        self.logger.info(f"Output size: {output_size} bytes")
        
        if output_size > self.max_response_size:
            self.logger.info(f"Output size {output_size} exceeds limit {self.max_response_size}, storing payload in S3")
            
            # Generate a unique key for the S3 object
            workflow_id = original_event.get("metadata", {}).get("workflowId", "unknown")
            execution_id = original_event.get("metadata", {}).get("executionId", "unknown")
            step_id = metadata["stepId"]
            s3_key = f"{workflow_id}/{execution_id}/{step_id}-payload.json"
            
            try:
                # Store the payload in S3
                self.s3.put_object(
                    Bucket=self.external_payload_bucket,
                    Key=s3_key,
                    Body=json.dumps(output["payload"])
                )
                self.logger.info(f"Large payload written to S3: {s3_key}")
                
                # Update the output to include a reference to the S3 location
                # Use externalTaskResults to be consistent with the Map state expectations
                output["metadata"]["externalPayload"] = True
                
                # Count the number of items in the payload array if it exists
                item_count = 0
                if isinstance(output["payload"], dict) and "externalTaskResults" in output["payload"] and isinstance(output["payload"]["externalTaskResults"], list):
                    item_count = len(output["payload"]["externalTaskResults"])
                    self.logger.info(f"Found {item_count} items in externalTaskResults array")
                else:
                    # Default to 1 item if we can't determine the count
                    item_count = 1
                    self.logger.info("Could not determine item count, defaulting to 1")
                
                # Create an array of references, one for each item in the original array
                references = []
                for i in range(item_count):
                    references.append({
                        "item": {
                            "bucket": self.external_payload_bucket,
                            "key": s3_key
                        },
                        "iteration": i
                    })
                
                output["payload"] = {
                    "externalTaskResults": references
                }
                
                self.logger.info(f"Created {len(references)} references to S3 object")
            except Exception as e:
                self.logger.error(f"Failed to write payload to S3: {str(e)}")
                raise
        
        return output

    def emit_event(
        self, detail_type: str, detail: Dict[str, Any], resources: Optional[list] = None
    ) -> None:
        try:
            event = {
                "Source": self.service_name,
                "DetailType": detail_type,
                "Detail": json.dumps(detail),
                "EventBusName": self.event_bus_name,
                "Resources": resources or [],
            }
            event_size = len(json.dumps(event).encode("utf-8"))
            if event_size > self.max_event_size:
                self.logger.info(f"Event size {event_size} exceeds limit {self.max_event_size}, using S3")
                key = f"events/{int(time.time())}-{detail_type}.json"
                self.s3.put_object(Bucket=self.large_payload_bucket, Key=key, Body=json.dumps(detail))
                self.temp_s3_objects.append(key)
                event["Detail"] = json.dumps(
                    {"s3_bucket": self.large_payload_bucket, "s3_key": key, "original_size": event_size}
                )
            self.event_bus.put_events(Entries=[event])
        except Exception as e:
            self.logger.error(f"Failed to emit event: {str(e)}")
            self.metrics.add_metric(name="FailedEvents", unit=MetricUnit.Count, value=1)

    def cleanup_temp_s3_objects(self) -> None:
        if not self.cleanup_s3 or not self.temp_s3_objects:
            return
        try:
            self.s3.delete_objects(
                Bucket=self.large_payload_bucket,
                Delete={"Objects": [{"Key": key} for key in self.temp_s3_objects]},
            )
            self.temp_s3_objects = []
        except Exception as e:
            self.logger.error(f"Failed to cleanup S3 objects: {str(e)}")

    def handle_failure(self, error: Exception, context: LambdaContext) -> None:
        error_type = error.__class__.__name__
        error_details = {
            "error_type": error_type,
            "error_message": str(error),
            "function_name": context.function_name,
            "request_id": context.aws_request_id,
            "function_version": context.function_version,
        }
        self.logger.exception("Function execution failed")
        self.emit_event(
            detail_type="FunctionExecutionFailure",
            detail=error_details,
            resources=[context.invoked_function_arn],
        )
        self.metrics.add_metric(name="Errors", unit=MetricUnit.Count, value=1)
        self.metrics.add_metric(name=f"Errors_{error_type}", unit=MetricUnit.Count, value=1)

    def __call__(self, handler: Callable[..., R]) -> Callable[..., R]:
        @lambda_handler_decorator
        def wrapper(inner_handler, event, context):
            start_time = time.time()
            try:
                self.emit_event(
                    detail_type="FunctionExecutionStart",
                    detail={
                        "function_name": context.function_name,
                        "request_id": context.aws_request_id,
                        "remaining_time": context.get_remaining_time_in_millis(),
                    },
                    resources=[context.invoked_function_arn],
                )

                self.metrics.add_dimension(name="FunctionName", value=context.function_name)
                self.metrics.add_dimension(name="Environment", value=os.getenv("ENVIRONMENT", "undefined"))

                processed_event = self.standardize_input(event)
                context.emit_progress = lambda progress, status, detail=None: self.emit_progress(
                    context, progress, status, detail
                )

                self.retry_count = 0
                self.retry_errors.clear()
                
                self.logger.info(f"Middleware before handler execution - function: {context.function_name}, request_id: {context.aws_request_id}")

                while True:
                    try:
                        result = inner_handler(processed_event, context)
                        break
                    except Exception as e:
                        if self.should_retry(e):
                            self.retry_count += 1
                            retry_delay = min(2 ** self.retry_count, 30)
                            self.logger.warning(
                                f"Retrying after error (attempt {self.retry_count}/{self.max_retries})",
                                extra={
                                    "error": str(e),
                                    "error_type": e.__class__.__name__,
                                    "retry_delay": retry_delay,
                                },
                            )
                            self.emit_event(
                                detail_type="FunctionExecutionRetry",
                                detail={
                                    "function_name": context.function_name,
                                    "request_id": context.aws_request_id,
                                    "error": str(e),
                                    "error_type": e.__class__.__name__,
                                    "retry_count": self.retry_count,
                                    "retry_delay": retry_delay,
                                },
                                resources=[context.invoked_function_arn],
                            )
                            time.sleep(retry_delay)
                            continue
                        raise

                if self.retry_count > 0:
                    self.metrics.add_metric(name="RetryAttempts", unit=MetricUnit.Count, value=self.retry_count)
                    for error_type in self.retry_errors:
                        self.metrics.add_metric(name=f"RetryErrors_{error_type}", unit=MetricUnit.Count, value=1)
                
                self.logger.info(f"Middleware after handler execution - function: {context.function_name}, request_id: {context.aws_request_id}")

                processed_result = self.standardize_output(result, event)
                execution_time = (time.time() - start_time) * 1000

                self.metrics.add_metric(name="Invocations", unit=MetricUnit.Count, value=1)
                self.metrics.add_metric(name="ExecutionTime", unit=MetricUnit.Milliseconds, value=execution_time)
                self.metrics.add_metric(name="MemoryUsed", unit=MetricUnit.Megabytes, value=float(context.memory_limit_in_mb))

                if not hasattr(LambdaMiddleware, "_cold_start_recorded"):
                    self.metrics.add_metric(name="ColdStart", unit=MetricUnit.Count, value=1)
                    LambdaMiddleware._cold_start_recorded = True

                self.emit_event(
                    detail_type="FunctionExecutionComplete",
                    detail={
                        "function_name": context.function_name,
                        "request_id": context.aws_request_id,
                        "execution_time_ms": execution_time,
                        "memory_used": context.memory_limit_in_mb,
                    },
                    resources=[context.invoked_function_arn],
                )

                return processed_result

            except Exception as e:
                self.handle_failure(e, context)
                raise

            finally:
                self.cleanup_temp_s3_objects()

        return wrapper(handler)


def lambda_middleware(
    event_bus_name: str,
    metrics_namespace: str = "MediaLake",
    max_event_size: int = 256000,
    cleanup_s3: bool = True,
    large_payload_bucket: Optional[str] = None,
    max_retries: int = 3,
    standardize_payloads: bool = True,
    external_payload_bucket: Optional[str] = None,
    max_response_size: int = 240 * 1024,  # 240KB in bytes
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    middleware = LambdaMiddleware(
        event_bus_name=event_bus_name,
        metrics_namespace=metrics_namespace,
        max_event_size=max_event_size,
        cleanup_s3=cleanup_s3,
        large_payload_bucket=large_payload_bucket,
        max_retries=max_retries,
        standardize_payloads=standardize_payloads,
        external_payload_bucket=external_payload_bucket,
        max_response_size=max_response_size,
    )
    return middleware
