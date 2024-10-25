import json
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")
s3 = boto3.client("s3")

DYNAMODB_TABLE_NAME = "S3Connectors"
QUEUE_NAME = "S3EventQueue"


def lambda_handler(event, context):
    # Extract connector information from the event
    connector_info = json.loads(event["body"])
    bucket_name = connector_info["bucket"]
    connector_name = connector_info["name"]
    connector_type = connector_info["type"]

    # Save connector information to DynamoDB
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    try:
        table.put_item(
            Item={
                "name": connector_name,
                "type": connector_type,
                "bucket": bucket_name,
                "createdDate": connector_info.get("createdDate", ""),
            }
        )
    except ClientError as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    # Create an SQS queue
    try:
        response = sqs.create_queue(QueueName=QUEUE_NAME)
        queue_url = response["QueueUrl"]
    except ClientError as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    # Get the queue ARN
    queue_attributes = sqs.get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=["QueueArn"]
    )
    queue_arn = queue_attributes["Attributes"]["QueueArn"]

    # Set S3 event notification to send events to the SQS queue
    try:
        s3.put_bucket_notification_configuration(
            Bucket=bucket_name,
            NotificationConfiguration={
                "QueueConfigurations": [
                    {"QueueArn": queue_arn, "Events": ["s3:ObjectCreated:*"]}
                ]
            },
        )
    except ClientError as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"message": "Connector saved and SQS queue created successfully"}
        ),
    }
