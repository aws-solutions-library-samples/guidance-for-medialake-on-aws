import os

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace=os.environ.get("METRICS_NAMESPACE", "MediaLake"))

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")
system_settings_table = dynamodb.Table(os.environ.get("SYSTEM_SETTINGS_TABLE"))

# Initialize API Gateway resolver
app = APIGatewayRestResolver()


@app.get("/settings/system")
@tracer.capture_method
def get_system_settings():
    """
    Get all system settings
    """
    try:
        # Get search provider settings
        search_provider_response = system_settings_table.get_item(
            Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDER"}
        )

        search_provider = search_provider_response.get("Item", {})

        # Remove DynamoDB specific attributes
        if search_provider:
            search_provider.pop("PK", None)
            search_provider.pop("SK", None)

        # Prepare response
        response = {
            "status": "success",
            "message": "System settings retrieved successfully",
            "data": {"searchProvider": search_provider if search_provider else None},
        }

        return response
    except Exception as e:
        logger.exception("Error retrieving system settings")
        return {
            "status": "error",
            "message": f"Error retrieving system settings: {str(e)}",
            "data": {},
        }


@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Lambda handler for system settings API
    """
    # Verify origin if needed
    # secret_value = get_secret(os.environ.get("X_ORIGIN_VERIFY_SECRET_ARN"))

    return app.resolve(event, context)
