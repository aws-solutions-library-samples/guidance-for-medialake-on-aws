import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.api_gateway import (
    APIGatewayRestResolver,
    CORSConfig,
)
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambda_utils import handle_error

# Initialize AWS services
dynamodb = boto3.resource("dynamodb")
PIPELINES_NODES_TABLE = os.environ["PIPELINES_NODES_TABLE"]

# Initialize Powertools utilities
service_name = os.getenv("SERVICE_NAME", "nodes_service")
logger = Logger(service=service_name, level=os.getenv("LOG_LEVEL", "WARNING"))
tracer = Tracer(service=service_name)
metrics = Metrics(namespace="NodesService", service=service_name)

# CORS configuration
cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=[
        "Content-Type",
        "X-Amz-Date",
        "Authorization",
        "X-Api-Key",
        "X-Amz-Security-Token",
    ],
)

# API Gateway Resolver
app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/api"],
    cors=cors_config,
)


@app.get("/nodes")
def get_nodes() -> Dict[str, Any]:
    """Retrieve all nodes and their related information."""
    try:
        table = dynamodb.Table(PIPELINES_NODES_TABLE)

        # Query to get all nodes with INFO and AUTH data
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("pk").eq("NODES")
            & boto3.dynamodb.conditions.Key("sk").begins_with("NODE#")
        )

        # Log the raw response from DynamoDB
        logger.info(f"DynamoDB query response: {response}")

        items = response.get("Items", [])

        # Process nodes to merge INFO and AUTH data
        nodes = {}
        for item in items:
            node_id = item["sk"].split("#")[1]  # Extract nodeId from sk

            if node_id not in nodes:
                nodes[node_id] = {"nodeId": node_id, "info": {}, "auth": {}}

            if "INFO" in item["sk"]:
                # Remove pk and sk from info data
                info_data = {k: v for k, v in item.items() if k not in ["pk", "sk"]}
                nodes[node_id]["info"] = info_data
            elif "AUTH" in item["sk"]:
                # Remove pk and sk from auth data
                auth_data = {k: v for k, v in item.items() if k not in ["pk", "sk"]}
                nodes[node_id]["auth"] = auth_data

        # Convert nodes dictionary to a list
        data = list(nodes.values())

        return {
            "status": "ok",
            "message": "Nodes retrieved successfully",
            "data": data,
        }

    except Exception as e:
        logger.error(f"Error retrieving nodes: {str(e)}")
        return handle_error(e)


@tracer.capture_lambda_handler
@logger.inject_lambda_context
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler to process API Gateway events."""
    return app.resolve(event, context)
