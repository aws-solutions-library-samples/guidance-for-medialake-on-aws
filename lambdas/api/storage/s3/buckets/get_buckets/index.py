import boto3
import json
import os


def get_medialake_buckets_from_ddb():
    """
    Retrieve the list of MediaLake buckets from DynamoDB system settings table.
    """
    try:
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('SYSTEM_SETTINGS_TABLE_NAME')
        
        if not table_name:
            print("SYSTEM_SETTINGS_TABLE_NAME environment variable not set")
            return []
        
        table = dynamodb.Table(table_name)
        
        # Query for MediaLake buckets setting using composite key (PK, SK)
        response = table.get_item(
            Key={
                'PK': 'SYSTEM_SETTINGS',
                'SK': 'medialake_buckets'
            }
        )
        
        if 'Item' in response and 'setting_value' in response['Item']:
            buckets_data = response['Item']['setting_value']
            if isinstance(buckets_data, list):
                return buckets_data
            elif isinstance(buckets_data, str):
                # If stored as JSON string, parse it
                import json
                return json.loads(buckets_data)
        
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
        
        # Filter out MediaLake buckets
        filtered_buckets = [
            bucket for bucket in all_buckets
            if bucket not in medialake_buckets
        ]

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(
                {"status": "200", "message": "ok", "data": {"buckets": filtered_buckets}}
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
