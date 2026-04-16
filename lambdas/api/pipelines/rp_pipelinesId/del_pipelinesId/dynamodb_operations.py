from datetime import datetime
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
        response = table.scan(
            FilterExpression="#n = :name",
            ExpressionAttributeNames={"#n": "name"},
            ExpressionAttributeValues={":name": pipeline_name},
        )
        items = response.get("Items", [])
        if items:
            # Skip pipelines that have been deleted — allow name reuse
            active_items = [
                item
                for item in items
                if item.get("deploymentStatus") not in ("DELETED", "DELETING")
            ]
            if not active_items:
                logger.info(
                    f"Found pipeline(s) with name {pipeline_name} but all are deleted/deleting"
                )
                return None
            pipeline = active_items[0]
            logger.info(f"Found pipeline with name {pipeline_name}")
            return pipeline
        logger.info(f"No pipeline found with name {pipeline_name}")
        return None
    except Exception as e:
        logger.error(f"Error looking up pipeline by name: {e}")
        return None


def update_pipeline_deployment_status(
    pipeline_id: str,
    deployment_status: str,
    cleanup_results: Optional[Dict[str, Any]] = None,
    error_details: Optional[str] = None,
) -> None:
    """
    Update the deployment status of a pipeline in DynamoDB.

    Args:
        pipeline_id: ID of the pipeline to update
        deployment_status: New deployment status (e.g. DELETING, DELETED, DELETE_FAILED)
        cleanup_results: Optional cleanup results to store
        error_details: Optional error message to store
    """
    logger.info(
        f"Updating pipeline {pipeline_id} deployment status to {deployment_status}"
    )
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(PIPELINES_TABLE)
    now_iso = datetime.utcnow().isoformat()

    update_expr = "SET #status = :status, #up = :updated"
    expr_values: Dict[str, Any] = {
        ":status": deployment_status,
        ":updated": now_iso,
    }
    expr_names = {
        "#status": "deploymentStatus",
        "#up": "updatedAt",
    }

    if cleanup_results is not None:
        update_expr += ", #cr = :cr"
        expr_values[":cr"] = cleanup_results
        expr_names["#cr"] = "cleanupResults"

    if error_details is not None:
        update_expr += ", #err = :err"
        expr_values[":err"] = error_details
        expr_names["#err"] = "deleteError"

    try:
        table.update_item(
            Key={"id": pipeline_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names,
        )
        logger.info(
            f"Successfully updated pipeline {pipeline_id} status to {deployment_status}"
        )
    except Exception as e:
        logger.exception(
            f"Failed to update pipeline {pipeline_id} status to {deployment_status}: {e}"
        )
        raise


def conditionally_set_deleting_status(pipeline_id: str) -> None:
    """
    Atomically set deploymentStatus to DELETING only if the current status
    is not already DELETING or DELETED.

    Raises:
        botocore.exceptions.ClientError: With code
            ``ConditionalCheckFailedException`` when the pipeline is already
            in a terminal delete state (DELETING / DELETED).
    """
    logger.info(
        f"Attempting atomic status transition to DELETING for pipeline {pipeline_id}"
    )
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(PIPELINES_TABLE)
    now_iso = datetime.utcnow().isoformat()

    table.update_item(
        Key={"id": pipeline_id},
        UpdateExpression="SET #status = :new_status, #up = :updated",
        ConditionExpression="#status <> :deleting AND #status <> :deleted",
        ExpressionAttributeNames={
            "#status": "deploymentStatus",
            "#up": "updatedAt",
        },
        ExpressionAttributeValues={
            ":new_status": "DELETING",
            ":deleting": "DELETING",
            ":deleted": "DELETED",
            ":updated": now_iso,
        },
    )
    logger.info(f"Successfully set pipeline {pipeline_id} status to DELETING (atomic)")
