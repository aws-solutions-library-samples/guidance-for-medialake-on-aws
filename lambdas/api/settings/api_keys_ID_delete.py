"""Handler for DELETE /settings/api-keys/{id} endpoint."""

import os

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger(child=True)
tracer = Tracer()

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")
secretsmanager = boto3.client("secretsmanager")


def register_route(app):
    """Register DELETE /settings/api-keys/{id} route"""

    @app.delete("/settings/api-keys/<id>")
    @tracer.capture_method
    def settings_api_keys_ID_delete(id: str):
        """Delete an API key"""
        try:
            api_keys_table = dynamodb.Table(os.environ.get("API_KEYS_TABLE_NAME"))

            # Get API key from DynamoDB to retrieve the secret ARN
            response = api_keys_table.get_item(Key={"keyId": id})

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
            api_keys_table.delete_item(Key={"keyId": id})

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
