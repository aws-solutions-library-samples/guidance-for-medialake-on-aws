from typing import Any, Dict

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize Powertools
logger = Logger()
tracer = Tracer()
app = APIGatewayRestResolver()


@app.put("/reviews/<review_id>")
@tracer.capture_method
def update_review(review_id: str) -> Dict[str, Any]:
    """
    Stub handler for updating a review.

    Args:
        review_id (str): The ID of the review to update

    Returns:
        Dict[str, Any]: API response with 200 status code
    """
    try:
        logger.info(f"Processing update request for review ID: {review_id}")

        return {
            "statusCode": 200,
            "body": {"message": "Success", "reviewId": review_id},
        }
    except Exception:
        logger.exception("Error processing review update")
        raise


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Main Lambda handler function.

    Args:
        event (Dict[str, Any]): Lambda event
        context (LambdaContext): Lambda context

    Returns:
        Dict[str, Any]: API Gateway response
    """
    try:
        return app.resolve(event, context)
    except Exception:
        logger.exception("Error in lambda handler")
        return {"statusCode": 500, "body": {"message": "Internal server error"}}
