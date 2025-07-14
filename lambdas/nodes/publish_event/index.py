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
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default-event-bus")


@lambda_middleware(
    event_bus_name=EVENT_BUS_NAME,
)
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    logger.debug("Received event: %s", json.dumps(event))

    # Pull pipelineName from the new payload shape
    input_payload = event.get("payload", {}).get("event", {}).get("input", {}) or {}
    pipeline_name = input_payload.get("pipelineName", "Default Image Pipeline")

    detail = {"pipelineName": pipeline_name, "status": "SUCCESS", "outputs": event}

    entries = [
        {
            "Source": "medialake.pipeline",
            "DetailType": "Pipeline Execution Completed",
            "Detail": json.dumps(detail),
            "EventBusName": EVENT_BUS_NAME,
            "Time": datetime.utcnow(),
        }
    ]

    response = eventbridge.put_events(Entries=entries)
    logger.debug("PutEvents response: %s", json.dumps(response))

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"message": "Event sent to EventBridge", "response": response}
        ),
    }
