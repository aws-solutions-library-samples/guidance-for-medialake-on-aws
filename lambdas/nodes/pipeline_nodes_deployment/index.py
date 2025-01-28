import os
import json
import boto3
import yaml
import datetime
from typing import Dict, Any
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import (
    event_source,
    CloudFormationCustomResourceEvent,
)
from crhelper import CfnResource
from lambda_utils import lambda_handler_decorator, logger, metrics, tracer, handle_error

helper = CfnResource(json_logging=True, log_level="DEBUG", boto_level="CRITICAL")
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

NODES_TABLE = os.environ["NODES_TABLE"]
NODES_BUCKET = os.environ["NODES_BUCKET"]


def process_node_file(bucket: str, key: str) -> Dict[str, Any]:
    """Process a single node definition file from S3."""
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")

        # Parse YAML content
        node_data = yaml.safe_load(content)

        # Extract required fields
        node_id = node_data.get("x-medialake-nodeId")
        if not node_id:
            raise ValueError(f"Missing required x-medialake-nodeId in file {key}")

        # Extract additional OpenAPI fields
        info = node_data.get("info", {})
        security_schemes = node_data.get("components", {}).get("securitySchemes", {})

        # Create standardized node record
        node_record = {
            "nodeId": node_id,
            "specFile": key,
            "spec": node_data,
            "type": "API",  # Default to API type
            "status": "ACTIVE",
            "createdAt": int(datetime.datetime.now().timestamp()),
            "updatedAt": int(datetime.datetime.now().timestamp()),
            "title": info.get("title"),
            "description": info.get("description"),
            "securitySchemes": security_schemes,
        }

        return node_record
    except Exception as e:
        logger.error(f"Error processing file {key}: {str(e)}")
        raise


def store_node_in_dynamodb(node_data: Dict[str, Any]) -> None:
    """Store node data in DynamoDB."""
    try:
        table = dynamodb.Table(NODES_TABLE)
        table.put_item(Item=node_data)
        logger.info(f"Successfully stored node {node_data['nodeId']} in DynamoDB")
    except Exception as e:
        logger.error(f"Error storing node {node_data.get('nodeId')}: {str(e)}")
        raise


@helper.create
@helper.update
def handle_create_update(
    event: CloudFormationCustomResourceEvent, context: LambdaContext
) -> None:
    """Handle Create and Update events from CloudFormation"""
    logger.info("Processing nodes for Create/Update event")
    try:
        # List all objects in the nodes bucket
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=NODES_BUCKET):
            if "Contents" in page:
                for obj in page["Contents"]:
                    key = obj["Key"]
                    if key.endswith((".yaml", ".yml")):
                        logger.info(f"Processing node file: {key}")
                        node_data = process_node_file(NODES_BUCKET, key)
                        store_node_in_dynamodb(node_data)
                        logger.info(
                            f"Successfully processed node: {node_data.get('nodeId')}"
                        )
    except Exception as e:
        logger.error(f"Error processing nodes: {str(e)}")
        raise


@helper.delete
def handle_delete(
    event: CloudFormationCustomResourceEvent, context: LambdaContext
) -> None:
    """Handle Delete events from CloudFormation"""
    logger.info("Delete event received - no cleanup required")
    pass


@logger.inject_lambda_context
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event, context):
    print(event)
    print(context)
    """
    Lambda handler to process CloudFormation Custom Resource events
    """
    try:
        # Validate that this is a CloudFormation Custom Resource event
        if not isinstance(event, dict) or "RequestType" not in event:
            raise ValueError(
                "Invalid event structure - not a CloudFormation Custom Resource event"
            )

        # Log the event type
        logger.info(f"Received CloudFormation {event['RequestType']} event")

        # Process the event using the helper
        helper(event, context)
    except Exception as e:
        logger.error(f"Failed to process event: {str(e)}")
        # Ensure we send a failure response to CloudFormation
        if hasattr(helper, "send_failure_signal"):
            helper.send_failure_signal(e)
        raise
