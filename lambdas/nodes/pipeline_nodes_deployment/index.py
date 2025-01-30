import os
import json
import boto3
import yaml
import datetime
import traceback
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


def validate_node_yaml(node_data: dict, key: str) -> None:
    """Validate the required fields in the node YAML."""
    required_fields = ["x-medialake-nodeId", "info", "paths"]
    for field in required_fields:
        if field not in node_data:
            raise ValueError(f"Missing required field '{field}' in file {key}")

    if "title" not in node_data["info"]:
        raise ValueError(f"Missing required field 'info.title' in file {key}")


def process_node_file(bucket: str, key: str) -> Dict[str, list]:
    """Process a single node definition file from S3 and return items for DynamoDB."""
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        logger.info(f"Processing file content from {key}")

        # Parse YAML content
        node_data = yaml.safe_load(content)
        logger.info(f"Parsed YAML data: {json.dumps(node_data, default=str)}")

        # Validate YAML structure
        validate_node_yaml(node_data, key)
        logger.info("YAML validation passed")

        # Extract required fields
        node_id = node_data["x-medialake-nodeId"]
        node_type = node_data.get("x-node-type", "API").upper()
        info = node_data.get("info", {})
        tags = [tag["name"] for tag in node_data.get("tags", [])]
        categories = set()
        timestamp = int(datetime.datetime.now().timestamp())

        logger.info(f"Extracted fields - node_id: {node_id}, node_type: {node_type}")
        logger.info(f"Info: {info}")
        logger.info(f"Tags: {tags}")

        # Create items for DynamoDB
        items = []

        # Basic Info Item
        info_item = {
            "pk": "NODES",
            "sk": f"NODE#{node_id}#INFO",
            "title": info.get("title"),
            "description": info.get("description"),
            "iconUrl": "",
            "nodeType": node_type,
            "categories": list(categories) if categories else [],  # Convert set to list
            "tags": list(tags) if tags else [],  # Ensure tags is a list
            "enabled": True,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
        logger.info(f"Created info_item: {json.dumps(info_item, default=str)}")
        items.append(info_item)

        # Auth Item - Add if security schemes exist
        security_schemes = node_data.get("components", {}).get("securitySchemes", {})
        if security_schemes:
            auth_method = next(iter(security_schemes.keys()))
            auth_item = {
                "pk": "NODES",
                "sk": f"NODE#{node_id}#AUTH",
                "authMethod": auth_method,
                "authConfig": {
                    "type": security_schemes[auth_method]["type"],
                    "parameters": security_schemes[auth_method],
                },
            }
            logger.info(f"Created auth_item: {json.dumps(auth_item, default=str)}")
            items.append(auth_item)

        # Method Items
        paths = node_data.get("paths", {})
        for path, methods in paths.items():
            for method_name, method_details in methods.items():
                if isinstance(method_details, dict):
                    method_id = method_details.get(
                        "operationId", f"{method_name}_{path}"
                    )
                    method_item = {
                        "pk": f"NODE#{node_id}",
                        "sk": f"METHOD#{method_id}",
                        "methodName": method_name,
                        "methodDescription": method_details.get("summary", ""),
                        "methodConfig": {
                            "path": path,
                            "inputMapping": method_details.get("x-inputMapping"),
                            "outputMapping": method_details.get("x-outputMapping"),
                        },
                    }
                    logger.info(
                        f"Created method_item: {json.dumps(method_item, default=str)}"
                    )
                    items.append(method_item)

        # GSI entries
        items.append(
            {
                "pk": f"TYPE#{node_type}",
                "sk": f"NODE#{node_id}",
            }
        )

        for tag in tags:
            items.append(
                {
                    "pk": f"TAG#{tag}",
                    "sk": f"NODE#{node_id}",
                }
            )

        logger.info(f"Total items generated: {len(items)}")
        logger.info(f"Items to be stored: {json.dumps(items, default=str)}")

        return {"items": items}
    except Exception as e:
        logger.error(f"Error processing file {key}: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise


def store_node_in_dynamodb(node_data: Dict[str, list]) -> None:
    """Store node data in DynamoDB using individual writes for debugging."""
    try:
        table = dynamodb.Table(NODES_TABLE)
        logger.info(f"Starting individual writes to DynamoDB table: {NODES_TABLE}")

        # Check if there are any items to process
        if not node_data.get("items"):
            logger.warning("No items to store in DynamoDB")
            return

        # Extract node_id from the first INFO item
        node_id = None
        for item in node_data["items"]:
            if item.get("sk", "").endswith("#INFO"):
                node_id = item["sk"].split("#")[1]
                break

        # Process all items
        for item in node_data["items"]:
            logger.info(f"Writing item to DynamoDB: {item}")
            try:
                response = table.put_item(Item=item)
                logger.info(f"PutItem response: {response}")
            except Exception as e:
                logger.error(f"Error writing item to DynamoDB: {str(e)}")

        if node_id:
            logger.info(
                f"Successfully attempted to store node {node_id} items in DynamoDB"
            )
        else:
            logger.warning("Processed items but could not determine node ID")

    except Exception as e:
        logger.error(f"Error storing node items: {str(e)}")
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
                        node_items = process_node_file(NODES_BUCKET, key)
                        store_node_in_dynamodb(node_items)
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
