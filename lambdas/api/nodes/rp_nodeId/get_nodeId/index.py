import json
import os
from decimal import Decimal
from typing import Any, Dict

import boto3
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambda_utils import lambda_handler_decorator, logger

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["PIPELINES_NODES_TABLE"])


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def get_unconfigured_nodes():
    """Get nodes with their methods."""
    logger.info("Starting get_unconfigured_nodes")

    # First get all unique node IDs that have methods
    logger.info("Scanning for method items")
    scan_params = {
        "FilterExpression": "begins_with(sk, :method)",
        "ExpressionAttributeValues": {":method": "METHOD#"},
    }
    logger.info(f"Scan parameters: {scan_params}")

    response = table.scan(**scan_params)
    logger.info(
        f"Scan response: {json.dumps(response, cls=DecimalEncoder, default=str)}"
    )

    if not response.get("Items"):
        logger.warning("No method items found in scan")
        return []

    # Group methods by node ID
    node_methods = {}
    for item in response.get("Items", []):
        logger.info(
            f"Processing item: {json.dumps(item, cls=DecimalEncoder, default=str)}"
        )
        node_id = item["pk"].split("#")[1]
        logger.info(f"Extracted node_id: {node_id}")
        if node_id not in node_methods:
            node_methods[node_id] = []
        node_methods[node_id].append(item)

    logger.info(
        f"Grouped methods by node: {json.dumps(node_methods, cls=DecimalEncoder, default=str)}"
    )

    # Get node info and combine with methods
    nodes = []
    for node_id, methods in node_methods.items():
        logger.info(f"Processing node {node_id}")

        # Get node info
        get_item_params = {"Key": {"pk": f"NODE#{node_id}", "sk": "INFO"}}
        logger.info(f"Getting node info with params: {get_item_params}")

        try:
            node_info = table.get_item(**get_item_params).get("Item")
            logger.info(
                f"Node info response: {json.dumps(node_info, cls=DecimalEncoder, default=str)}"
            )

            if not node_info:
                # Try getting the node info directly from the method item
                node_info = {
                    "title": methods[0].get("methodName", "Unknown Method"),
                    "description": methods[0].get("methodDescription", ""),
                    "nodeType": "API",
                    "categories": [],
                    "tags": [],
                    "enabled": True,
                    "createdAt": methods[0].get("createdAt", ""),
                    "updatedAt": methods[0].get("updatedAt", ""),
                }
                logger.info(
                    f"Created node info from method: {json.dumps(node_info, cls=DecimalEncoder, default=str)}"
                )
        except Exception as e:
            logger.error(f"Error getting node info: {str(e)}")
            node_info = None

        if node_info:
            node_data = {
                "nodeId": node_id,
                "info": {
                    "title": node_info.get("title"),
                    "description": node_info.get("description"),
                    "nodeType": node_info.get("nodeType"),
                    "categories": node_info.get("categories", []),
                    "tags": node_info.get("tags", []),
                    "enabled": node_info.get("enabled", True),
                    "createdAt": node_info.get("createdAt"),
                    "updatedAt": node_info.get("updatedAt"),
                },
                "methods": [
                    {
                        "name": method.get("methodName"),
                        "description": method.get("methodDescription"),
                        "config": method.get("methodConfig", {}),
                    }
                    for method in methods
                ],
                "connections": {"incoming": {}, "outgoing": {}},
            }

            # Get connection data for this node
            connection_params = {
                "KeyConditionExpression": "pk = :pk AND begins_with(sk, :connection)",
                "ExpressionAttributeValues": {
                    ":pk": f"NODE#{node_id}",
                    ":connection": "CONNECTION#",
                },
            }
            logger.info(f"Querying connections with params: {connection_params}")

            try:
                connection_response = table.query(**connection_params)
                connection_items = connection_response.get("Items", [])
                logger.info(
                    f"Found {len(connection_items)} connection items for node {node_id}"
                )

                for item in connection_items:
                    # Extract connection type (INCOMING or OUTGOING)
                    if "CONNECTION#INCOMING" in item["sk"]:
                        connection_type = "incoming"
                    elif "CONNECTION#OUTGOING" in item["sk"]:
                        connection_type = "outgoing"
                    else:
                        continue

                    # Extract method ID if present
                    method_id = None
                    if "#" in item["sk"].split("CONNECTION#")[1]:
                        method_id = item["sk"].split("#")[-1]

                    # Remove pk and sk from connection data
                    connection_data = {
                        k: v for k, v in item.items() if k not in ["pk", "sk"]
                    }

                    # Add connection data to the node
                    if method_id:
                        # Method-specific connection
                        if method_id not in node_data["connections"][connection_type]:
                            node_data["connections"][connection_type][method_id] = []
                        node_data["connections"][connection_type][method_id].append(
                            connection_data
                        )
                    else:
                        # Node-level connection
                        node_data["connections"][connection_type][
                            "node"
                        ] = connection_data
            except Exception as e:
                logger.error(
                    f"Error getting connection data for node {node_id}: {str(e)}"
                )

            logger.info(
                f"Created node data: {json.dumps(node_data, cls=DecimalEncoder, default=str)}"
            )
            nodes.append(node_data)
        else:
            logger.warning(f"No node info found for node {node_id}")

    logger.info(
        f"Final nodes list: {json.dumps(nodes, cls=DecimalEncoder, default=str)}"
    )
    return nodes


def get_node_methods(node_id: str):
    """Get methods for a specific node."""
    logger.info(f"Starting get_node_methods for node {node_id}")

    # Get node info
    get_item_params = {"Key": {"pk": f"NODE#{node_id}", "sk": "INFO"}}
    logger.info(f"Getting node info with params: {get_item_params}")

    node_info = table.get_item(**get_item_params).get("Item")
    logger.info(
        f"Node info response: {json.dumps(node_info, cls=DecimalEncoder, default=str)}"
    )

    if not node_info:
        logger.warning(f"No node info found for node {node_id}")
        return None

    # Get all methods for this node
    query_params = {
        "KeyConditionExpression": "pk = :pk AND begins_with(sk, :method)",
        "ExpressionAttributeValues": {
            ":pk": f"NODE#{node_id}",
            ":method": "METHOD#",
        },
    }
    logger.info(f"Querying methods with params: {query_params}")

    methods_response = table.query(**query_params)
    logger.info(
        f"Methods query response: {json.dumps(methods_response, cls=DecimalEncoder, default=str)}"
    )

    # Format response
    node_data = {
        "nodeId": node_id,
        "info": {
            "title": node_info.get("title"),
            "description": node_info.get("description"),
            "nodeType": node_info.get("nodeType"),
            "categories": node_info.get("categories", []),
            "tags": node_info.get("tags", []),
            "enabled": node_info.get("enabled", True),
            "createdAt": node_info.get("createdAt"),
            "updatedAt": node_info.get("updatedAt"),
        },
        "methods": [
            {
                "name": method.get("methodName"),
                "description": method.get("methodDescription"),
                "config": method.get("methodConfig", {}),
            }
            for method in methods_response.get("Items", [])
        ],
        "connections": {"incoming": {}, "outgoing": {}},
    }

    # Get connection data for this node
    connection_params = {
        "KeyConditionExpression": "pk = :pk AND begins_with(sk, :connection)",
        "ExpressionAttributeValues": {
            ":pk": f"NODE#{node_id}",
            ":connection": "CONNECTION#",
        },
    }
    logger.info(f"Querying connections with params: {connection_params}")

    try:
        connection_response = table.query(**connection_params)
        connection_items = connection_response.get("Items", [])
        logger.info(
            f"Found {len(connection_items)} connection items for node {node_id}"
        )

        for item in connection_items:
            # Extract connection type (INCOMING or OUTGOING)
            if "CONNECTION#INCOMING" in item["sk"]:
                connection_type = "incoming"
            elif "CONNECTION#OUTGOING" in item["sk"]:
                connection_type = "outgoing"
            else:
                continue

            # Extract method ID if present
            method_id = None
            if "#" in item["sk"].split("CONNECTION#")[1]:
                method_id = item["sk"].split("#")[-1]

            # Remove pk and sk from connection data
            connection_data = {k: v for k, v in item.items() if k not in ["pk", "sk"]}

            # Add connection data to the node
            if method_id:
                # Method-specific connection
                if method_id not in node_data["connections"][connection_type]:
                    node_data["connections"][connection_type][method_id] = []
                node_data["connections"][connection_type][method_id].append(
                    connection_data
                )
            else:
                # Node-level connection
                node_data["connections"][connection_type]["node"] = connection_data
    except Exception as e:
        logger.error(f"Error getting connection data for node {node_id}: {str(e)}")

    logger.info(
        f"Final node data: {json.dumps(node_data, cls=DecimalEncoder, default=str)}"
    )
    return node_data


def get_node_by_id(node_id: str):
    """Get complete node information including info, auth, and methods."""
    logger.info(f"Starting get_node_by_id for node {node_id}")

    # Get node info
    info_params = {"Key": {"pk": f"NODE#{node_id}", "sk": "INFO"}}
    logger.info(f"Getting node info with params: {info_params}")
    node_info = table.get_item(**info_params).get("Item")

    if not node_info:
        logger.warning(f"No node info found for node {node_id}")
        return None

    # Get node auth
    auth_params = {"Key": {"pk": f"NODE#{node_id}", "sk": "AUTH"}}
    logger.info(f"Getting node auth with params: {auth_params}")
    node_auth = table.get_item(**auth_params).get("Item")

    # Get node methods
    methods_params = {
        "KeyConditionExpression": "pk = :pk AND begins_with(sk, :method)",
        "ExpressionAttributeValues": {":pk": f"NODE#{node_id}", ":method": "METHOD#"},
    }
    logger.info(f"Getting node methods with params: {methods_params}")
    methods_response = table.query(**methods_params)

    # Format response
    node_data = {
        "nodeId": node_id,
        "info": {
            "title": node_info.get("title"),
            "description": node_info.get("description"),
            "nodeType": node_info.get("nodeType"),
            "iconUrl": node_info.get("iconUrl"),
            "categories": list(node_info.get("categories", set())),
            "tags": list(node_info.get("tags", set())),
            "enabled": node_info.get("enabled", True),
            "createdAt": node_info.get("createdAt"),
            "updatedAt": node_info.get("updatedAt"),
            "inputTypes": node_info.get("inputTypes", []),
            "outputTypes": node_info.get("outputTypes", []),
        },
        "connections": {"incoming": {}, "outgoing": {}},
    }

    # Add auth if available
    if node_auth:
        node_data["auth"] = {
            "authMethod": node_auth.get("authMethod"),
            "authConfig": node_auth.get("authConfig", {}),
        }

    # Add methods
    node_data["methods"] = [
        {
            "name": method.get("methodName"),
            "description": method.get("methodDescription"),
            "requestMapping": method.get("methodConfig", {}).get("requestMapping"),
            "responseMapping": method.get("methodConfig", {}).get("responseMapping"),
            "parameters": method.get("methodConfig", {}).get("parameters", []),
        }
        for method in methods_response.get("Items", [])
    ]

    # Get connection data for this node
    connection_params = {
        "KeyConditionExpression": "pk = :pk AND begins_with(sk, :connection)",
        "ExpressionAttributeValues": {
            ":pk": f"NODE#{node_id}",
            ":connection": "CONNECTION#",
        },
    }
    logger.info(f"Querying connections with params: {connection_params}")

    try:
        connection_response = table.query(**connection_params)
        connection_items = connection_response.get("Items", [])
        logger.info(
            f"Found {len(connection_items)} connection items for node {node_id}"
        )

        for item in connection_items:
            # Extract connection type (INCOMING or OUTGOING)
            if "CONNECTION#INCOMING" in item["sk"]:
                connection_type = "incoming"
            elif "CONNECTION#OUTGOING" in item["sk"]:
                connection_type = "outgoing"
            else:
                continue

            # Extract method ID if present
            method_id = None
            if "#" in item["sk"].split("CONNECTION#")[1]:
                method_id = item["sk"].split("#")[-1]

            # Remove pk and sk from connection data
            connection_data = {k: v for k, v in item.items() if k not in ["pk", "sk"]}

            # Add connection data to the node
            if method_id:
                # Method-specific connection
                if method_id not in node_data["connections"][connection_type]:
                    node_data["connections"][connection_type][method_id] = []
                node_data["connections"][connection_type][method_id].append(
                    connection_data
                )
            else:
                # Node-level connection
                node_data["connections"][connection_type]["node"] = connection_data
    except Exception as e:
        logger.error(f"Error getting connection data for node {node_id}: {str(e)}")

    return node_data


@lambda_handler_decorator(cors=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler to process API Gateway events."""
    try:
        logger.info(
            f"Received event: {json.dumps(event, cls=DecimalEncoder, default=str)}"
        )
        path = event.get("path", "")
        logger.info(f"Processing path: {path}")

        # GET /nodes/methods/unconfigured
        if path.endswith("/nodes/methods/unconfigured"):
            nodes = get_unconfigured_nodes()
            response_data = {
                "status": "success",
                "message": "Unconfigured nodes retrieved",
                "data": nodes,
            }

        # GET /nodes/{nodeId}/methods
        elif path.endswith("/methods"):
            node_id = event["pathParameters"]["id"]
            node_methods = get_node_methods(node_id)

            if not node_methods:
                return {
                    "statusCode": 404,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(
                        {
                            "status": "error",
                            "message": f"No methods found for node {node_id}",
                        },
                        cls=DecimalEncoder,
                    ),
                }

            response_data = {
                "status": "success",
                "message": "Node methods retrieved",
                "data": node_methods,
            }

        # GET /nodes/{nodeId}
        else:
            node_id = event["pathParameters"]["id"]
            node_data = get_node_by_id(node_id)

            if not node_data:
                return {
                    "statusCode": 404,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(
                        {"status": "error", "message": f"Node {node_id} not found"},
                        cls=DecimalEncoder,
                    ),
                }

            response_data = {
                "status": "success",
                "message": "Node found",
                "data": [node_data],  # Keeping array format for backward compatibility
            }

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(response_data, cls=DecimalEncoder),
        }

    except Exception as e:
        logger.exception("Error processing request")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {"status": "error", "message": str(e)}, cls=DecimalEncoder
            ),
        }
