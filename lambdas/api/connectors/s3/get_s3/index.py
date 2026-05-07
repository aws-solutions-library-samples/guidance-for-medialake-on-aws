import json
import os

import boto3


def get_medialake_buckets_from_ddb():
    """
    Retrieve the list of MediaLake buckets from DynamoDB system settings table.
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table_name = os.environ.get("SYSTEM_SETTINGS_TABLE_NAME")

        if not table_name:
            print("SYSTEM_SETTINGS_TABLE_NAME environment variable not set")
            return []

        table = dynamodb.Table(table_name)

        # Query for MediaLake buckets setting using composite key (PK, SK)
        response = table.get_item(
            Key={"PK": "SYSTEM_SETTINGS", "SK": "MEDIALAKE_BUCKETS"}
        )

        if "Item" in response and "setting_value" in response["Item"]:
            buckets_data = response["Item"]["setting_value"]
            print(f"Retrieved buckets_data: {buckets_data}")

            # Handle DynamoDB List format - when using boto3 resource, it should auto-convert
            if isinstance(buckets_data, list):
                return buckets_data
            elif isinstance(buckets_data, str):
                # If stored as JSON string, parse it
                import json

                return json.loads(buckets_data)
        else:
            print(f"No item found or no setting_value. Response: {response}")

        return []

    except Exception as e:
        print(f"Error retrieving MediaLake buckets from DDB: {str(e)}")
        return []


def lambda_handler(event, context):
    try:
        # Create an S3 client
        s3_client = boto3.client("s3")

        # Get list of buckets
        response = s3_client.list_buckets()

        # Extract bucket names from response
        all_buckets = [bucket["Name"] for bucket in response["Buckets"]]

        # Get MediaLake buckets from DynamoDB
        medialake_buckets = get_medialake_buckets_from_ddb()
        print(f"MediaLake buckets to filter: {medialake_buckets}")
        print(f"All S3 buckets: {all_buckets}")

        # Filter out MediaLake buckets
        filtered_buckets = [
            bucket for bucket in all_buckets if bucket not in medialake_buckets
        ]
        print(f"Filtered buckets: {filtered_buckets}")

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(
                {
                    "status": "200",
                    "message": "ok",
                    "data": {"buckets": filtered_buckets},
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
                {"status": "500", "message": str(e), "data": {"buckets": []}}
            ),
        }
