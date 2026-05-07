import json
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


@app.put("/reviews/<review_id>/annotations")
@tracer.capture_method
def put_annotations(review_id: str) -> Dict[str, Any]:
    """
    Stub handler for putting annotations for a review
    """
    try:
        logger.info(f"Processing put annotations request for review ID: {review_id}")

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Success", "reviewId": review_id}),
        }
    except Exception:
        logger.exception("Error processing put annotations request")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Internal server error"}),
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    """
    Main Lambda handler
    """
    return app.resolve(event, context)
