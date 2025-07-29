from typing import Any, Dict

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize Logger and Tracer
logger = Logger(service="get_review_by_id")
tracer = Tracer(service="get_review_by_id")
app = APIGatewayRestResolver()


@app.get("/reviews/<review_id>")
@tracer.capture_method
def get_review(review_id: str) -> Dict[str, Any]:
    """
    Get review by ID endpoint
    Args:
        review_id (str): The ID of the review to retrieve
    Returns:
        Dict[str, Any]: API response with status code and body
    """
    try:
        logger.info(f"Retrieving review with ID: {review_id}")

        # Stub response for development
        return {
            "statusCode": 200,
            "body": {
                "message": "Review retrieval endpoint stub",
                "review_id": review_id,
                "status": "success",
            },
        }

    except Exception as e:
        logger.exception(f"Error retrieving review: {str(e)}")
        return {
            "statusCode": 500,
            "body": {"message": "Internal server error", "status": "error"},
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """
    Lambda handler for the get review endpoint
    Args:
        event (APIGatewayProxyEvent): API Gateway event
        context (LambdaContext): Lambda context
    Returns:
        Dict[str, Any]: Lambda response
    """
    return app.resolve(event, context)
