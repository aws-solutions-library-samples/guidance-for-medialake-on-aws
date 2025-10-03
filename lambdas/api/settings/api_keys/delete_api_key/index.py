import os

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
api_keys_table = dynamodb.Table(os.environ.get("API_KEYS_TABLE"))
secretsmanager = boto3.client("secretsmanager")

# Initialize API Gateway resolver
app = APIGatewayRestResolver()


@app.delete("/settings/api-keys/{id}")
@tracer.capture_method
def delete_api_key(id: str):
    """
    Delete an API key
    """
    try:
        # Get API key from DynamoDB to retrieve the secret ARN
        response = api_keys_table.get_item(Key={"id": id})

        if "Item" not in response:
            return {
                "status": "error",
                "message": f"API key with ID {id} not found",
                "data": {},
            }

        item = response["Item"]
        secret_arn = item.get("secretArn")

        # Delete the secret from Secrets Manager
        if secret_arn:
            try:
                secretsmanager.delete_secret(
                    SecretId=secret_arn,
                    ForceDeleteWithoutRecovery=True,  # Immediate deletion
                )
                logger.info(f"Deleted secret {secret_arn} for API key {id}")
            except Exception as e:
                logger.error(f"Error deleting secret {secret_arn}: {str(e)}")
                # Continue with DynamoDB deletion even if secret deletion fails

        # Delete the API key from DynamoDB
        api_keys_table.delete_item(Key={"id": id})

        logger.info(f"Deleted API key {id}")

        return {
            "status": "success",
            "message": "API key deleted successfully",
            "data": {"id": id},
        }

    except Exception as e:
        logger.exception(f"Error deleting API key {id}")
        return {
            "status": "error",
            "message": f"Error deleting API key: {str(e)}",
            "data": {},
        }


@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Lambda handler for API key deletion endpoint
    """
    return app.resolve(event, context)
