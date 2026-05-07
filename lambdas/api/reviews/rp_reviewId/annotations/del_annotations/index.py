from typing import Any, Dict

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize Powertools
logger = Logger()
tracer = Tracer()
app = APIGatewayRestResolver()


@app.delete("/reviews/<review_id>/annotations")
@tracer.capture_method
def delete_annotations(review_id: str) -> Dict[str, Any]:
    """
    Stub handler for deleting annotations from a review
    """
    try:
        logger.info(f"Processing delete annotations request for review: {review_id}")

        # TODO: Implement actual deletion logic

        return {
            "statusCode": 200,
            "body": {
                "message": "Annotations deleted successfully",
                "reviewId": review_id,
            },
        }
    except Exception:
        logger.exception("Error processing delete annotations request")
        raise


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """
    Main Lambda handler
    """
    try:
        return app.resolve(event, context)
    except Exception:
        logger.exception("Error in lambda handler")
        return {"statusCode": 500, "body": {"message": "Internal server error"}}
