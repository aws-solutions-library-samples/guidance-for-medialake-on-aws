import json
import os
import boto3
from typing import Dict, List
from datetime import datetime

dynamodb = boto3.resource("dynamodb")
integrations_table = dynamodb.Table(os.environ["INTEGRATIONS_TABLE"])
pipelines_nodes_table = dynamodb.Table(os.environ["PIPELINES_NODES_TABLE"])


def format_integration(item: Dict) -> Dict:
    # Extract node name from the Node field (e.g., "node-aws-s3-vector" -> "AWS S3 Vector")
    node_name = item.get("Node", "").replace("node-", "").replace("-", " ").title()

    return {
        "id": item.get("ID", ""),
        "name": node_name,
        "type": item.get("Type", ""),
        "status": item.get("Status", ""),
        "configuration": item.get("Configuration", {}),
        "createdAt": item.get("CreatedDate", datetime.utcnow().isoformat()),
        "updatedAt": item.get("ModifiedDate", datetime.utcnow().isoformat()),
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
