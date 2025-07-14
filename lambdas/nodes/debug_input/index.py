import json

from aws_lambda_powertools import Logger, Tracer

# Initialize Powertools
logger = Logger()
tracer = Tracer()


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        # Log the entire event for debugging
        logger.info("Received event", extra={"event": event})

        # Return the event as the response for debugging purposes
        return {
            "statusCode": 200,
            "body": json.dumps(
                {"message": "Debug input Lambda executed successfully", "input": event},
                default=str,
            ),  # default=str handles non-serializable objects
        }

    except Exception as e:
        error_message = f"Error in debug_input Lambda: {str(e)}"
        logger.exception(error_message)
        return {"statusCode": 500, "body": json.dumps({"error": error_message})}
