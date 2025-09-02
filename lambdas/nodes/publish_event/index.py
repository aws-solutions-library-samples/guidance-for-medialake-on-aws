import json
import os
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambda_middleware import lambda_middleware

logger = Logger()
tracer = Tracer()
eventbridge = boto3.client("events")
# Get event bus name from ARN if available, otherwise use EVENT_BUS_NAME
EVENTBUS_ARN = os.environ.get("EVENTBUS_ARN")
if EVENTBUS_ARN:
    # Extract event bus name from ARN (format: arn:aws:events:region:account:event-bus/name)
    EVENT_BUS_NAME = EVENTBUS_ARN.split("/")[-1]
else:
    EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default-event-bus")


@lambda_middleware(
    event_bus_name=EVENT_BUS_NAME,
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    logger.debug("Received event: %s", json.dumps(event))
    logger.info(f"Using event bus: {EVENT_BUS_NAME}")

    # Pull pipelineName from the new payload shape
    input_payload = event.get("payload", {}).get("event", {}).get("input", {}) or {}
    pipeline_name = input_payload.get("pipelineName", "Default Image Pipeline")

    # Extract configurable parameters from environment variables first, then input payload as fallback
    source = os.environ.get("SOURCE", input_payload.get("source", "medialake.pipeline"))
    detail_type = os.environ.get(
        "DETAIL_TYPE", input_payload.get("detail_type", "AssetIngested")
    )
    # Use the configured event bus name, allow override from input payload
    event_bus_name = input_payload.get("EventBusName", EVENT_BUS_NAME)

    detail = {"pipelineName": pipeline_name, "status": "SUCCESS", "outputs": event}

    entries = [
        {
            "Source": source,
            "DetailType": detail_type,
            "Detail": json.dumps(detail),
            "EventBusName": event_bus_name,
            "Time": datetime.utcnow(),
        }
    ]

    logger.info(f"Sending event to EventBridge bus: {event_bus_name}")
    response = eventbridge.put_events(Entries=entries)
    logger.debug("PutEvents response: %s", json.dumps(response))

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"message": "Event sent to EventBridge", "response": response}
        ),
    }
