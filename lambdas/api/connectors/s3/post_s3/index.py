import os
import uuid
import boto3
import json
from datetime import datetime
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.validation import validator
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.event_handler import (
    APIGatewayRestResolver,
    Response,
    content_types,
)
from aws_lambda_powertools.event_handler.openapi.exceptions import (
    RequestValidationError,
)
from pydantic import BaseModel, Field, constr
from typing import Dict, Any

tracer = Tracer()
logger = Logger()
app = APIGatewayRestResolver(enable_validation=True)

s3_client = boto3.client("s3")


class S3Connector(BaseModel):
    bucket: str


class S3Connector(BaseModel):
    configuration: S3Connector
    name: str
    type: str


@app.exception_handler(RequestValidationError)
def handle_validation_error(ex: RequestValidationError):
    logger.error(
        "Request failed validation", path=app.current_event.path, errors=ex.errors()
    )

    return Response(
        status_code=422,
        content_type=content_types.APPLICATION_JSON,
        body={
            "status": "error",
            "message": "Invalid data",
            "data": {
                "code": "422",
                "details": ex.errors(),
            },
        },
    )


@app.post("/connectors/s3")
def create_connector(createconnector: S3Connector) -> dict:
    try:
        # Validate request body
        s3_bucket = createconnector.configuration.bucket
        connector_name = createconnector.name

        # Validate S3 bucket exists and get its region
        try:
            bucket_location = s3_client.get_bucket_location(Bucket=s3_bucket)
            bucket_region = bucket_location['LocationConstraint']
            # If bucket_region is None, it means the bucket is in us-east-1
            bucket_region = bucket_region or 'us-east-1'
        except s3_client.exceptions.ClientError:
            raise ValueError(
                f"S3 bucket '{s3_bucket}' does not exist or is not accessible"
            )

        # Initialize clients in the bucket's region
        s3 = boto3.client('s3', region_name=bucket_region)
        sqs = boto3.client('sqs', region_name=bucket_region)
        dynamodb = boto3.resource('dynamodb', region_name=bucket_region)

        # Create SQS queue in the same region as the bucket
        queue_name = f"{s3_bucket}-notifications"
        response = sqs.create_queue(QueueName=queue_name)
        queue_url = response["QueueUrl"]

        # Get the SQS queue ARN
        response = sqs.get_queue_attributes(
            QueueUrl=queue_url, AttributeNames=["QueueArn"]
        )
        queue_arn = response["Attributes"]["QueueArn"]

        # Set up SQS queue policy to allow S3 notifications
        queue_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "s3.amazonaws.com"},
                    "Action": "sqs:SendMessage",
                    "Resource": queue_arn,
                    "Condition": {
                        "ArnLike": {"aws:SourceArn": f"arn:aws:s3:::{s3_bucket}"}
                    }
                }
            ]
        }
        sqs.set_queue_attributes(
            QueueUrl=queue_url,
            Attributes={
                'Policy': json.dumps(queue_policy)
            }
        )

        # Subscribe SQS queue to S3 bucket notifications
        notification_config = {
            "QueueConfigurations": [
                {"QueueArn": queue_arn, "Events": ["s3:ObjectCreated:*"]}
            ]
        }
        s3.put_bucket_notification_configuration(
            Bucket=s3_bucket, 
            NotificationConfiguration=notification_config
        )

        # Generate a unique ID for the connector
        connector_id = str(uuid.uuid4())

        # Get the current timestamp
        creation_time = datetime.now().isoformat()

        # Save the connector details in DynamoDB
        table_name = os.environ.get("MEDIALAKE_CONNECTOR_TABLE")
        if not table_name:
            raise ValueError("MEDIALAKE_CONNECTOR_TABLE environment variable is not set")

        table = dynamodb.Table(table_name)
        item = {
            "ConnectorId": connector_id,
            "ConnectorName": connector_name,
            "SQSArn": queue_arn,
            "S3Bucket": s3_bucket,
            "CreationTime": creation_time,
            "BucketRegion": bucket_region
        }
        table.put_item(Item=item)

        logger.info(
            f"Successfully created SQS queue '{queue_name}' in region '{bucket_region}'"
            f", subscribed it to S3 bucket '{s3_bucket}', and saved connector details"
        )

        return {
            "statusCode": 200,
            "body": {
                "connectorId": connector_id,
                "creationTime": creation_time,
                "region": bucket_region
            },
        }

    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}")
        return {"statusCode": 400, "body": {"error": str(ve)}}
    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        return {"statusCode": 500, "body": {"error": "Internal server error"}}


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
