"""
Secrets Manager utilities for integrations API.

Functions to manage API keys in AWS Secrets Manager.
"""

import os
from typing import Optional

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.exceptions import InternalServerError
from botocore.exceptions import ClientError

logger = Logger(service="secrets-utils", level=os.environ.get("LOG_LEVEL", "INFO"))
secretsmanager = boto3.client("secretsmanager")


def store_api_key_secret(api_key: str, integration_id: str) -> str:
    """
    Store API key in Secrets Manager and return the secret ARN.

    Args:
        api_key: The API key to store
        integration_id: Integration ID for naming the secret

    Returns:
        ARN of the created secret

    Raises:
        InternalServerError: If secret creation fails
    """
    try:
        secret_name = f"integration/{integration_id}/api-key"
        response = secretsmanager.create_secret(
            Name=secret_name,
            SecretString=api_key,
            Description=f"API Key for integration {integration_id}",
        )
        logger.info(f"Successfully stored API key for integration {integration_id}")
        return response["ARN"]
    except ClientError as e:
        logger.error(f"Failed to store API key: {str(e)}")
        raise InternalServerError("Failed to store API key")


def update_api_key_secret(
    api_key: str, integration_id: str, existing_secret_arn: Optional[str] = None
) -> str:
    """
    Update API key in Secrets Manager and return the secret ARN.

    Args:
        api_key: The new API key value
        integration_id: Integration ID for naming the secret
        existing_secret_arn: Optional existing secret ARN to update

    Returns:
        ARN of the updated or created secret

    Raises:
        InternalServerError: If secret update/creation fails
    """
    try:
        secret_name = f"integration/{integration_id}/api-key"

        # If there's an existing secret, update it
        if existing_secret_arn:
            secretsmanager.put_secret_value(
                SecretId=existing_secret_arn, SecretString=api_key
            )
            logger.info(
                f"Successfully updated API key for integration {integration_id}"
            )
            return existing_secret_arn
        # Otherwise, create a new secret
        else:
            response = secretsmanager.create_secret(
                Name=secret_name,
                SecretString=api_key,
                Description=f"API Key for integration {integration_id}",
            )
            logger.info(
                f"Successfully created API key for integration {integration_id}"
            )
            return response["ARN"]
    except ClientError as e:
        logger.error(f"Failed to update API key: {str(e)}")
        raise InternalServerError("Failed to update API key")


def delete_api_key_secret(secret_arn: str) -> None:
    """
    Delete API key from Secrets Manager.

    Args:
        secret_arn: ARN of the secret to delete

    Note:
        Continues gracefully if secret deletion fails to avoid blocking
        integration deletion if the secret is already gone.
    """
    try:
        secretsmanager.delete_secret(
            SecretId=secret_arn, ForceDeleteWithoutRecovery=True
        )
        logger.info(f"Successfully deleted API key secret: {secret_arn}")
    except ClientError as e:
        logger.error(f"Failed to delete API key secret: {str(e)}")
        # Continue gracefully - we don't want to block integration deletion
        # if the secret is already gone or inaccessible
