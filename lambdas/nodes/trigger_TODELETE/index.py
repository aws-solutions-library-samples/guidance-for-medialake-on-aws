import json
import os
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
asset_table = dynamodb.Table(os.environ["MEDIALAKE_ASSET_TABLE"])
pipeline_nodes_table = dynamodb.Table(os.environ["PIPELINE_NODES_TABLE"])


def process_event(event, context):
    # Get the asset ID from the event
    asset_id = event["asset_id"]

    # Get the asset details from the asset table
    asset = asset_table.get_item(Key={"id": asset_id})["Item"]

    # Get the trigger node configuration
    trigger_config = pipeline_nodes_table.query(
        IndexName="NameIndex", KeyConditionExpression=Key("name").eq("trigger_node")
    )["Items"][0]["props"]

    # Check if the asset matches the file type
    if asset["file_type"] != trigger_config["file_type"]:
        return {
            "status": "skipped",
            "reason": f"File type {asset['file_type']} does not match required type {trigger_config['file_type']}",
        }

    # Check metadata filters if they exist
    if "metadata_filters" in trigger_config:
        for key, value in trigger_config["metadata_filters"].items():
            if key not in asset["metadata"] or asset["metadata"][key] != value:
                return {
                    "status": "skipped",
                    "reason": f"Metadata filter {key}={value} not satisfied",
                }

    # If all checks pass, return success
    return {
        "status": "success",
        "message": "Asset passed all trigger conditions",
        "asset_id": asset_id,
    }


def lambda_handler(event, context):
    try:
        result = process_event(event, context)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "error", "message": str(e)}),
        }
