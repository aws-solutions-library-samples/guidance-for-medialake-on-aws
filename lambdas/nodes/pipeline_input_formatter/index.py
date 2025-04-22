import os
import json
from typing import Dict, Any
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext

# Import the lambda_middleware
from lambda_middleware import lambda_middleware

# Initialize utilities
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="PipelineInputFormatter")

# Get environment variables
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default")
EXTERNAL_PAYLOAD_BUCKET = os.environ.get("EXTERNAL_PAYLOAD_BUCKET")

@lambda_middleware(
    event_bus_name=EVENT_BUS_NAME,
    metrics_namespace="PipelineInputFormatter",
    standardize_payloads=True,
    external_payload_bucket=EXTERNAL_PAYLOAD_BUCKET
)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Format the trigger input event to the middleware payload format.
    This Lambda is designed to be the first step in a Step Function,
    placed after a trigger, to standardize the event format.
    
    Args:
        event: The input event from the trigger
        context: Lambda context
        
    Returns:
        Formatted event in the middleware payload format
    """
    logger.info("Processing trigger event", extra={"event": event})
    
    # Create a standardized payload structure
    # The middleware will handle most of the standardization,
    # but we need to ensure the event is in the right format first
    
    # For EventBridge triggers, extract relevant fields
    formatted_event = {
        "metadata": {
            "service": context.function_name,
            "stepName": context.function_name,
            "stepStatus": "InProgress",
            "stepId": context.aws_request_id,
            "pipelineAssets": []
        },
        "payload": {
            # Include the original event data
            "originalEvent": event,
            
            # Extract specific fields if they exist
            "detail": event.get("detail", {}),
            "source": event.get("source", ""),
            "detailType": event.get("detailType", ""),
            "time": event.get("time", ""),
            "triggerNode": event.get("triggerNode", ""),
            "pipelineName": event.get("pipelineName", "")
        }
    }
    
    # Extract asset information if available
    if "detail" in event and "DigitalSourceAsset" in event.get("detail", {}):
        digital_source_asset = event["detail"]["DigitalSourceAsset"]
        asset_id = digital_source_asset.get("ID")
        
        if asset_id:
            logger.info(f"Found DigitalSourceAsset ID: {asset_id}")
            formatted_event["metadata"]["pipelineAssets"].append({
                "assetId": asset_id
            })
    
    logger.info("Formatted event", extra={"formatted_event": formatted_event})
    return formatted_event