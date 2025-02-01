import os
import json
import boto3
import yaml
import datetime
from decimal import Decimal
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
        logger.info(f"Node data structure: {list(node_data.keys())}")

        # Validate YAML structure
        validate_node_yaml(node_data, key)
        logger.info("YAML validation passed")

        # Extract required fields
        node_id = node_data["x-medialake-nodeId"]
        node_type = node_data.get("x-node-type", "API").upper()
        info = node_data.get("info", {})

        logger.info(
            f"Creating INFO item for node",
            extra={
                "node_id": node_id,
                "node_type": node_type,
                "info_keys": list(info.keys()),
            },
        )

        # Convert timestamp to Decimal for DynamoDB compatibility
        timestamp = Decimal(str(int(datetime.datetime.now().timestamp())))

        # Basic Info Item
        info_item = {
            "pk": f"NODE#{node_id}",
            "sk": "INFO",
            "title": info.get("title"),
            "description": info.get("description"),
            "iconUrl": "",
            "nodeType": node_type,
            "categories": ["Video Understanding", "Embeddings"],
            "tags": [tag.get("name") for tag in node_data.get("tags", [])],
            "enabled": True,
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "gsi1pk": "NODES",
            "gsi1sk": f"NODE#{node_id}",
            "entityType": "NODE",
            "nodeId": f"NODE#{node_id}",
            "methodInfo": True,
            "version": info.get("version"),
            "servers": node_data.get("servers", []),
        }

        logger.info(
            "Created info_item",
            extra={
                "pk": info_item["pk"],
                "sk": info_item["sk"],
                "title": info_item["title"],
                "timestamp_type": type(timestamp).__name__,
            },
        )

        items = [info_item]

        # Auth Item
        security_schemes = node_data.get("components", {}).get("securitySchemes", {})
        if security_schemes:
            auth_method = next(iter(security_schemes.keys()))
            auth_item = {
                "pk": f"NODE#{node_id}",
                "sk": "AUTH",
                "authMethod": auth_method,
                "authConfig": security_schemes[auth_method],
            }
            items.append(auth_item)

        # Method Items
        paths = node_data.get("paths", {})
        for path, methods in paths.items():
            for method_name, method_details in methods.items():
                if isinstance(method_details, dict):
                    method_id = f"{path}/{method_name}".replace("/", "_").strip("_")
                    method_item = {
                        "pk": f"NODE#{node_id}",
                        "sk": f"METHOD#{method_id}",
                        "methodName": method_name,
                        "methodDescription": method_details.get("summary", ""),
                        "methodConfig": {
                            "path": path,
                            "operationId": method_details.get("operationId"),
                            "parameters": method_details.get("parameters", {}),
                            "inputMapping": method_details.get("x-inputMapping"),
                            "outputMapping": method_details.get("x-outputMapping"),
                        },
                        "gsi2pk": f"METHOD#{node_id}",
                        "gsi2sk": f"METHOD#{method_id}",
                        "entityType": "NODE",  # For GSI3 partition key
                        "nodeId": f"NODE#{node_id}",  # For GSI3 sort key
                        "methodInfo": True,  # For GSI3 filtering
                    }
                    items.append(method_item)

        # Category and Tag GSI entries
        categories = set()
        for category in categories:
            items.append(
                {
                    "pk": f"NODE#{node_id}",
                    "sk": f"CAT#{category}",
                    "gsi3pk": f"CAT#{category}",
                    "gsi3sk": f"NODE#{node_id}",
                }
            )

        for tag in items[0]["tags"]:
            items.append(
                {
                    "pk": f"NODE#{node_id}",
                    "sk": f"TAG#{tag}",
                    "gsi4pk": f"TAG#{tag}",
                    "gsi4sk": f"NODE#{node_id}",
                }
            )

        logger.info(f"Total items generated: {len(items)}")
        return {"items": items}
    except Exception as e:
        logger.error(f"Error processing file {key}: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise


def store_node_in_dynamodb(node_data: Dict[str, list]) -> None:
    """Store node data in DynamoDB using individual writes for debugging."""
    try:
        table = dynamodb.Table(NODES_TABLE)
        logger.info(
            f"Starting DynamoDB writes",
            extra={
                "table": NODES_TABLE,
                "item_count": len(node_data.get("items", [])),
            },
        )

        # Process all items
        for item in node_data.get("items", []):
            logger.info(
                "Writing DynamoDB item",
                extra={
                    "pk": item.get("pk"),
                    "sk": item.get("sk"),
                    "item_keys": list(item.keys()),
                },
            )

            try:
                # Convert any float values to Decimal without using json serialization
                def convert_floats_to_decimal(obj):
                    if isinstance(obj, float):
                        return Decimal(str(obj))
                    elif isinstance(obj, dict):
                        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_floats_to_decimal(v) for v in obj]
                    return obj

                # Convert the item
                converted_item = convert_floats_to_decimal(item)

                response = table.put_item(Item=converted_item)
                logger.info(
                    "Successfully wrote item",
                    extra={"pk": item.get("pk"), "sk": item.get("sk")},
                )
            except Exception as e:
                logger.error(
                    "Failed to write item",
                    extra={
                        "pk": item.get("pk"),
                        "sk": item.get("sk"),
                        "error": str(e),
                        "item_type": str(type(item)),
                    },
                )
                raise

    except Exception as e:
        logger.error(
            f"Error in store_node_in_dynamodb",
            extra={"error": str(e), "traceback": traceback.format_exc()},
        )
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
