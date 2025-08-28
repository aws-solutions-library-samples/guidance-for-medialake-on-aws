import datetime
import os
import traceback
from decimal import Decimal
from typing import Any, Dict

import boto3
import yaml
from aws_lambda_powertools.utilities.data_classes import (
    CloudFormationCustomResourceEvent,
)
from aws_lambda_powertools.utilities.typing import LambdaContext
from crhelper import CfnResource
from lambda_utils import logger, metrics

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


def process_node_file(
    bucket: str, key: str, node_data: Dict[str, Any] = None
) -> Dict[str, list]:
    """Process a single node definition file from S3 and return items for DynamoDB."""
    try:
        if node_data is None:
            # Only fetch from S3 if node_data wasn't provided
            response = s3_client.get_object(Bucket=bucket, Key=key)
            content = response["Body"].read().decode("utf-8")
            logger.info(f"Processing file content from {key}")
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
                            "requestMapping": method_details.get("x-requestMapping"),
                            "responseMapping": method_details.get("x-responseMapping"),
                        },
                        "gsi2pk": f"METHOD#{node_id}",
                        "gsi2sk": f"METHOD#{method_id}",
                        "entityType": "NODE",
                        "nodeId": f"NODE#{node_id}",
                        "methodInfo": True,
                    }
                    items.append(method_item)

        # Category and Tag GSI entries
        for category in info_item["categories"]:
            items.append(
                {
                    "pk": f"NODE#{node_id}",
                    "sk": f"CAT#{category}",
                    "gsi3pk": f"CAT#{category}",
                    "gsi3sk": f"NODE#{node_id}",
                }
            )

        for tag in info_item["tags"]:
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


def list_node_template_files(bucket: str) -> list:
    """Recursively list all YAML files under node_templates directory."""
    files = []
    paginator = s3_client.get_paginator("list_objects_v2")

    try:
        # The trailing slash in the prefix is optional since S3 uses prefix matching
        for page in paginator.paginate(Bucket=bucket, Prefix="node_templates"):
            if "Contents" in page:
                for obj in page["Contents"]:
                    key = obj["Key"]
                    # Log all files we're looking at for debugging
                    logger.debug(f"Examining file: {key}")

                    # Check if it's a YAML file (case insensitive)
                    if key.lower().endswith((".yaml", ".yml")):
                        files.append(key)
                        logger.info(f"Found template file: {key}")
    except Exception as e:
        logger.error(
            f"Error listing template files: {str(e)}",
            extra={"error": str(e), "traceback": traceback.format_exc()},
        )
        raise  # Re-raise the exception to ensure errors are properly handled

    logger.info(f"Total template files found: {len(files)}")
    return files


def process_node_template(bucket: str, key: str) -> Dict[str, list]:
    """Process a node template file and determine its integration."""
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        node_data = yaml.safe_load(content)

        logger.info(
            f"Processing node template: {key}",
            extra={
                "node_id": node_data.get("node", {}).get("id"),
                "node_type": node_data.get("node", {}).get("type"),
                "integration": node_data.get("node", {}).get("integration"),
            },
        )

        if not node_data.get("node"):
            raise ValueError(f"Invalid node template format in {key}")

        node_type = node_data["node"].get("type")
        integration = node_data["node"].get("integration", {})

        if node_type == "api":
            return process_api_node(bucket, node_data, integration)
        elif node_type == "integration":
            return process_integration_node(bucket, node_data, integration)
        else:
            return process_standard_node(node_data)

    except Exception as e:
        logger.error(
            f"Error processing template {key}: {str(e)}",
            extra={"error": str(e), "traceback": traceback.format_exc()},
        )
        return None


def process_integration_node(
    bucket: str, node_data: dict, integration: dict
) -> Dict[str, list]:
    """Process an INTEGRATION node by fetching and processing its OpenINTEGRATION spec."""
    try:
        spec_path = integration.get("api", {}).get("open_api_spec_path")
        if not spec_path:
            raise ValueError("Missing open_api_spec_path in INTEGRATION api config")

        logger.info(f"Fetching OpenINTEGRATION spec from: {spec_path}")

        # Fetch and process OpenINTEGRATION spec
        spec_response = s3_client.get_object(Bucket=bucket, Key=spec_path)
        spec_content = spec_response["Body"].read().decode("utf-8")
        spec_data = yaml.safe_load(spec_content)

        # Combine node metadata with OpenINTEGRATION spec
        combined_data = {
            "x-medialake-nodeId": node_data["node"]["id"],
            "x-node-type": "INTEGRATION",
            "info": {
                "title": node_data["node"]["title"],
                "description": node_data["node"]["description"],
                "version": node_data["node"]["version"],
            },
            "paths": spec_data.get("paths", {}),
            "components": spec_data.get("components", {}),
            "servers": spec_data.get("servers", []),
            "tags": spec_data.get("tags", []),
        }

        # Process the combined data using process_node_file
        return process_node_file(bucket, spec_path, combined_data)

    except Exception as e:
        logger.error(
            f"Error processing INTEGRATION node: {str(e)}",
            extra={"traceback": traceback.format_exc()},
        )
        raise


def process_api_node(
    bucket: str, node_data: dict, integration: dict
) -> Dict[str, list]:
    """Process an API node by fetching and processing its OpenAPI spec."""
    try:
        spec_path = integration.get("api", {}).get("open_api_spec_path")
        if not spec_path:
            raise ValueError("Missing open_api_spec_path in API integration config")

        logger.info(f"Fetching OpenAPI spec from: {spec_path}")

        # Fetch and process OpenAPI spec
        spec_response = s3_client.get_object(Bucket=bucket, Key=spec_path)
        spec_content = spec_response["Body"].read().decode("utf-8")
        spec_data = yaml.safe_load(spec_content)

        # Combine node metadata with OpenAPI spec
        combined_data = {
            "x-medialake-nodeId": node_data["node"]["id"],
            "x-node-type": "API",
            "info": {
                "title": node_data["node"]["title"],
                "description": node_data["node"]["description"],
                "version": node_data["node"]["version"],
            },
            "paths": spec_data.get("paths", {}),
            "components": spec_data.get("components", {}),
            "servers": spec_data.get("servers", []),
            "tags": spec_data.get("tags", []),
        }

        # Process the combined data using process_node_file
        return process_node_file(bucket, spec_path, combined_data)

    except Exception as e:
        logger.error(
            f"Error processing API node: {str(e)}",
            extra={"traceback": traceback.format_exc()},
        )
        raise


def process_standard_node(node_data: dict) -> Dict[str, list]:
    """Process a non-API node (trigger, utility, etc.) using standard schema."""
    try:
        node_id = node_data["node"]["id"]
        timestamp = Decimal(str(int(datetime.datetime.now().timestamp())))

        items = []

        # Create base node info item
        info_item = {
            "pk": f"NODE#{node_id}",
            "sk": "INFO",
            "title": node_data["node"]["title"],
            "description": node_data["node"]["description"],
            "nodeType": node_data["node"]["type"].upper(),
            "categories": ["Integration"],
            "tags": [],
            "enabled": True,
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "gsi1pk": "NODES",
            "gsi1sk": f"NODE#{node_id}",
            "entityType": "NODE",
            "nodeId": f"NODE#{node_id}",
            "methodInfo": True,
            "version": node_data["node"]["version"],
        }
        items.append(info_item)

        # Process actions as methods if they exist
        actions = node_data.get("actions", {})
        for action_name, action_details in actions.items():
            method_id = action_name
            method_item = {
                "pk": f"NODE#{node_id}",
                "sk": f"METHOD#{method_id}",
                "methodName": action_name,
                "methodDescription": action_details.get("description", ""),
                "methodConfig": {
                    "summary": action_details.get("summary", ""),
                    "parameters": action_details.get("parameters", {}),
                },
                "gsi2pk": f"METHOD#{node_id}",
                "gsi2sk": f"METHOD#{method_id}",
                "entityType": "NODE",
                "nodeId": f"NODE#{node_id}",
                "methodInfo": True,
            }
            items.append(method_item)

            # Process connections if they exist in the action
            if "connections" in action_details:
                # Process incoming connections
                if "incoming" in action_details["connections"]:
                    incoming_conn = action_details["connections"]["incoming"]
                    incoming_item = {
                        "pk": f"NODE#{node_id}",
                        "sk": f"CONNECTION#INCOMING#{method_id}",
                        "methodId": method_id,
                        "connectionType": "INCOMING",
                        "connectionConfig": incoming_conn,
                        "entityType": "NODE",
                        "nodeId": f"NODE#{node_id}",
                    }
                    items.append(incoming_item)

                # Process outgoing connections
                if "outgoing" in action_details["connections"]:
                    outgoing_conn = action_details["connections"]["outgoing"]
                    outgoing_item = {
                        "pk": f"NODE#{node_id}",
                        "sk": f"CONNECTION#OUTGOING#{method_id}",
                        "methodId": method_id,
                        "connectionType": "OUTGOING",
                        "connectionConfig": outgoing_conn,
                        "entityType": "NODE",
                        "nodeId": f"NODE#{node_id}",
                    }
                    items.append(outgoing_item)

        # Also check for connections at the node level in case they're not in actions
        if "connections" in node_data:
            logger.info(f"Processing node-level connections for {node_id}")
            # Process incoming connections
            if "incoming" in node_data["connections"]:
                incoming_conn = node_data["connections"]["incoming"]
                incoming_item = {
                    "pk": f"NODE#{node_id}",
                    "sk": "CONNECTION#INCOMING",
                    "connectionType": "INCOMING",
                    "connectionConfig": incoming_conn,
                    "entityType": "NODE",
                    "nodeId": f"NODE#{node_id}",
                }
                items.append(incoming_item)

            # Process outgoing connections
            if "outgoing" in node_data["connections"]:
                outgoing_conn = node_data["connections"]["outgoing"]
                outgoing_item = {
                    "pk": f"NODE#{node_id}",
                    "sk": "CONNECTION#OUTGOING",
                    "connectionType": "OUTGOING",
                    "connectionConfig": outgoing_conn,
                    "entityType": "NODE",
                    "nodeId": f"NODE#{node_id}",
                }
                items.append(outgoing_item)

        # Process Lambda layers if they exist in the node configuration
        if (
            "integration" in node_data.get("node", {})
            and "config" in node_data["node"]["integration"]
        ):
            lambda_config = node_data["node"]["integration"]["config"].get("lambda", {})
            if "layers" in lambda_config and isinstance(lambda_config["layers"], list):
                # Create a layers item to store the layer ARNs
                layers_item = {
                    "pk": f"NODE#{node_id}",
                    "sk": "LAYERS",
                    "layers": {},
                    "entityType": "NODE",
                    "nodeId": f"NODE#{node_id}",
                }

                # For each layer in the YAML, get the ARN from environment variables
                for layer_name in lambda_config["layers"]:
                    env_var_name = f"{layer_name.upper()}_LAYER_ARN"
                    layer_arn = os.environ.get(env_var_name)
                    if layer_arn:
                        layers_item["layers"][layer_name] = layer_arn
                        logger.info(
                            f"Adding layer {layer_name} with ARN {layer_arn} to node {node_id}"
                        )
                    else:
                        logger.warning(
                            f"Layer {layer_name} specified in YAML but environment variable {env_var_name} not found"
                        )

                # Only add the layers item if we found at least one layer ARN
                if layers_item["layers"]:
                    items.append(layers_item)
                    logger.info(
                        f"Added layers item for node {node_id} with {len(layers_item['layers'])} layers"
                    )

        return {"items": items}

    except Exception as e:
        logger.error(
            f"Error processing standard node: {str(e)}",
            extra={"traceback": traceback.format_exc()},
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
        template_files = list_node_template_files(NODES_BUCKET)
        logger.info(f"Found {len(template_files)} template files to process")

        for template_file in template_files:
            try:
                logger.info(f"Starting to process template: {template_file}")
                node_items = process_node_template(NODES_BUCKET, template_file)
                if node_items:
                    logger.info(
                        f"Successfully processed template {template_file}, storing in DynamoDB"
                    )
                    store_node_in_dynamodb(node_items)
                else:
                    logger.warning(f"No items generated for template {template_file}")
            except Exception as e:
                logger.error(
                    f"Failed to process template {template_file}: {str(e)}",
                    extra={"traceback": traceback.format_exc()},
                )
                continue

    except Exception as e:
        logger.error(
            f"Error in create/update handler: {str(e)}",
            extra={"traceback": traceback.format_exc()},
        )
        raise


@helper.delete
def handle_delete(
    event: CloudFormationCustomResourceEvent, context: LambdaContext
) -> None:
    """Handle Delete events from CloudFormation"""
    logger.info("Delete event received - no cleanup required")


@logger.inject_lambda_context
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event, context):
    # print(event)
    # print(context)
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
