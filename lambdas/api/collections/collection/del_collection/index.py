from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()
router = APIGatewayRestResolver()


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
def handler(event: dict, context: LambdaContext) -> dict:
    try:
        return router.resolve(event, context)
    except Exception:
        logger.exception("Error processing request")
        raise


@router.delete("/collections/<collection_id>")
@tracer.capture_method
def delete_collection(collection_id: str):
    try:
        # Here you would implement your collection deletion logic
        # For example, calling DynamoDB, S3, or other AWS services

        logger.info(f"Deleting collection with ID: {collection_id}")

        # Implement your deletion logic here

        return {
            "statusCode": 200,
            "body": {"message": f"Collection {collection_id} successfully deleted"},
        }
    except Exception:
        logger.exception(f"Failed to delete collection {collection_id}")
        return {
            "statusCode": 500,
            "body": {"message": "Internal server error while deleting collection"},
        }
