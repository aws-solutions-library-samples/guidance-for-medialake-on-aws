import json

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

# Initialize powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()


@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event, context):
    """Lambda handler for Asset Sync Job Event Processor"""
    try:
        logger.info(f"Received SQS event: {json.dumps(event)}")

        # Process each SQS record
        for record in event.get("Records", []):
            try:
                # Parse the SQS message body
                message_body = json.loads(record["body"])

                # The EventBridge event will be in the message body
                if "detail" in message_body:
                    # This is an EventBridge event
                    event_source = message_body.get("source")
                    detail_type = message_body.get("detail-type")
                    detail = message_body.get("detail", {})
                    event_name = detail.get("eventName")
                    event_source_detail = detail.get("eventSource")

                    logger.info(
                        f"Processing S3 CloudTrail event - Source: {event_source}, DetailType: {detail_type}, EventSource: {event_source_detail}, EventName: {event_name}"
                    )
                    logger.info(f"Event detail: {json.dumps(detail, indent=2)}")

                    # Record metric for event processing
                    metrics.add_metric(
                        name="JobEventProcessed", unit=MetricUnit.Count, value=1
                    )

                    if event_name:
                        metrics.add_metric(
                            name=f"JobEvent_{event_name}",
                            unit=MetricUnit.Count,
                            value=1,
                        )

                    # TODO: Add actual job event processing logic here
                    # For now, just log the event details

                else:
                    logger.warning(
                        f"Unexpected message format: {json.dumps(message_body)}"
                    )

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse SQS message body: {str(e)}")
                metrics.add_metric(
                    name="JobEventProcessingErrors", unit=MetricUnit.Count, value=1
                )
            except Exception as e:
                logger.error(f"Error processing SQS record: {str(e)}", exc_info=True)
                metrics.add_metric(
                    name="JobEventProcessingErrors", unit=MetricUnit.Count, value=1
                )

        return {
            "statusCode": 200,
            "body": json.dumps("Successfully processed job events"),
        }

    except Exception as e:
        logger.error(f"Error in lambda handler: {str(e)}", exc_info=True)
        metrics.add_metric(
            name="JobEventProcessingErrors", unit=MetricUnit.Count, value=1
        )
        raise
