from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger

from config import PIPELINES_TABLE

# Initialize logger
logger = Logger()


def get_pipeline_by_id(pipeline_id: str) -> Optional[Dict[str, Any]]:
    """
    Get pipeline record from DynamoDB by ID.

    Args:
        pipeline_id: ID of the pipeline to look up

    Returns:
        Pipeline record if found, None otherwise
    """
    logger.info(f"Looking up pipeline with ID: {pipeline_id}")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(PIPELINES_TABLE)

    try:
        response = table.get_item(Key={"id": pipeline_id})
        pipeline = response.get("Item")
        if pipeline:
            logger.info(f"Found pipeline with ID {pipeline_id}")
            return pipeline
        logger.info(f"No pipeline found with ID {pipeline_id}")
        return None
    except Exception as e:
        logger.error(f"Error looking up pipeline by ID: {e}")
        return None


def get_pipeline_by_name(pipeline_name: str) -> Optional[Dict[str, Any]]:
    """
    Get pipeline record from DynamoDB by name.

    Args:
        pipeline_name: Name of the pipeline to look up

    Returns:
        Pipeline record if found, None otherwise
    """
    logger.info(f"Looking up pipeline with name: {pipeline_name}")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(PIPELINES_TABLE)

    try:
        # Scan for items with matching name
        response = table.scan(
            FilterExpression="#n = :name",
            ExpressionAttributeNames={"#n": "name"},
            ExpressionAttributeValues={":name": pipeline_name},
        )
        items = response.get("Items", [])
        if items:
            pipeline = items[0]
            logger.info(f"Found pipeline with name {pipeline_name}")
            return pipeline
        logger.info(f"No pipeline found with name {pipeline_name}")
        return None
    except Exception as e:
        logger.error(f"Error looking up pipeline by name: {e}")
        return None


def delete_pipeline_from_dynamodb(pipeline_id: str) -> bool:
    """
    Delete pipeline record from DynamoDB.

    Args:
        pipeline_id: ID of the pipeline to delete

    Returns:
        True if deletion was successful, False otherwise
    """
    logger.info(f"Deleting pipeline with ID: {pipeline_id}")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(PIPELINES_TABLE)

    try:
        table.delete_item(Key={"id": pipeline_id})
        logger.info(f"Successfully deleted pipeline with ID {pipeline_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting pipeline: {e}")
        return False
