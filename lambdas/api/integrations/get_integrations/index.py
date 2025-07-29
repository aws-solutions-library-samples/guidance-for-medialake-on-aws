import json
import os
from typing import Dict

import boto3

dynamodb = boto3.resource("dynamodb")
integrations_table = dynamodb.Table(os.environ["INTEGRATIONS_TABLE"])
pipelines_nodes_table = dynamodb.Table(os.environ["PIPELINES_NODES_TABLE"])


def format_integration(item: Dict) -> Dict:
    # Use the stored Name field if available, otherwise generate from nodeId
    stored_name = item.get("Name", "")
    if not stored_name:
        # Generate name from nodeId by replacing underscores with spaces and title-casing
        # Use the actual nodeId value as provided (e.g., "twelve_labs" -> "Twelve Labs")
        stored_name = item.get("Node", "").replace("_", " ").title()

    return {
        "id": item.get("ID", ""),
        "name": stored_name,
        "nodeId": item.get("Node", ""),
        "type": item.get("Type", ""),
        "status": item.get("Status", ""),
        "description": item.get("Description", ""),
        "configuration": item.get("Configuration", {}),
        "createdAt": item.get("CreatedDate", ""),
        "updatedAt": item.get("ModifiedDate", ""),
    }


def lambda_handler(event, context):
    try:
        # Get all integrations
        response = integrations_table.scan()
        integrations = response.get("Items", [])

        # Format each integration
        formatted_integrations = [format_integration(item) for item in integrations]

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(
                {
                    "status": "success",
                    "message": "Integrations retrieved successfully",
                    "data": formatted_integrations,
                }
            ),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(
                {"status": "error", "message": f"Error getting integrations: {str(e)}"}
            ),
        }
