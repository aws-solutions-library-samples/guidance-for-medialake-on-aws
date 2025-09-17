import os
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace=os.environ.get("METRICS_NAMESPACE", "MediaLake"))

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")
system_settings_table = dynamodb.Table(os.environ.get("SYSTEM_SETTINGS_TABLE"))
secretsmanager = boto3.client("secretsmanager")

# Initialize API Gateway resolver
app = APIGatewayRestResolver()


@app.delete("/settings/system/search")
@tracer.capture_method
def delete_search_provider():
    """
    Delete search provider configuration and reset to default state
    """
    try:
        # Check if search provider exists
        existing_provider = system_settings_table.get_item(
            Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDER"}
        ).get("Item")

        if not existing_provider:
            return {
                "status": "error",
                "message": "Search provider not found.",
                "data": {},
            }

        # Delete the secret if it exists
        secret_arn = existing_provider.get("secretArn")
        if secret_arn:
            try:
                secretsmanager.delete_secret(
                    SecretId=secret_arn, ForceDeleteWithoutRecovery=True
                )
            except Exception as e:
                logger.warning(f"Failed to delete secret {secret_arn}: {str(e)}")
                # Continue with provider deletion even if secret deletion fails

        # Delete the search provider record
        system_settings_table.delete_item(
            Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDER"}
        )

        # Reset embedding store to default
        embedding_store_item = {
            "PK": "SYSTEM_SETTINGS",
            "SK": "EMBEDDING_STORE",
            "type": "opensearch",
            "isEnabled": False,
            "updatedAt": datetime.utcnow().isoformat(),
        }

        # Check if embedding store exists to preserve createdAt
        existing_embedding_store = system_settings_table.get_item(
            Key={"PK": "SYSTEM_SETTINGS", "SK": "EMBEDDING_STORE"}
        ).get("Item")

        if existing_embedding_store:
            embedding_store_item["createdAt"] = existing_embedding_store.get(
                "createdAt", embedding_store_item["updatedAt"]
            )
        else:
            embedding_store_item["createdAt"] = embedding_store_item["updatedAt"]

        # Update embedding store
        system_settings_table.put_item(Item=embedding_store_item)

        # Prepare response with default state
        return {
            "status": "success",
            "message": "Search provider deleted successfully",
            "data": {
                "searchProvider": {
                    "name": "TwelveLabs API",
                    "type": "twelvelabs-api",
                    "isConfigured": False,
                    "isEnabled": False,
                },
                "embeddingStore": {
                    "type": "opensearch",
                    "isEnabled": False,
                },
            },
        }
    except Exception as e:
        logger.exception("Error deleting search provider")
        return {
            "status": "error",
            "message": f"Error deleting search provider: {str(e)}",
            "data": {},
        }


@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Lambda handler for search provider API
    """
    # Verify origin if needed
    # secret_value = get_secret(os.environ.get("X_ORIGIN_VERIFY_SECRET_ARN"))

    return app.resolve(event, context)
