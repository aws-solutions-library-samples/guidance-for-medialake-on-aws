import os
import uuid
import json
import time
import boto3
from datetime import datetime
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.event_handler import (
    APIGatewayRestResolver,
    Response,
    content_types,
)
from aws_lambda_powertools.event_handler.openapi.exceptions import (
    RequestValidationError,
)
from pydantic import BaseModel

tracer = Tracer()
logger = Logger()
app = APIGatewayRestResolver(enable_validation=True)

# Initialize S3 client - region will be determined per bucket
s3_client = boto3.client("s3")

# Initialize DynamoDB in Lambda's region
dynamodb = boto3.resource('dynamodb')

# Initialize Lambda client
lambda_client = boto3.client('lambda')
iam_client = boto3.client('iam')


class S3ConnectorConfig(BaseModel):
    bucket: str


class S3Connector(BaseModel):
    configuration: S3ConnectorConfig
    name: str
    type: str


@app.exception_handler(RequestValidationError)
def handle_validation_error(ex: RequestValidationError):
    logger.error(
        "Request failed validation",
        path=app.current_event.path,
        errors=ex.errors()
    )

    return Response(
        status_code=422,
        content_type=content_types.APPLICATION_JSON,
        body={
            "status": "422",
            "message": "Invalid data",
            "data": {
                "details": ex.errors(),
            },
        },
    )


@app.post("/connectors/s3")
def create_connector(createconnector: S3Connector) -> dict:
    try:
        # medialake_tag = os.environ.get('MEDIALAKE_TAG', 'medialake')
        medialake_tag = 'medialake'
        # Get deployment configuration from environment variables
        deployment_bucket = os.environ.get('IAC_ASSETS_BUCKET')
        deployment_zip = os.environ.get('S3_CONNECTOR_LAMBDA')
        # target_function_name = os.environ.get('TARGET_FUNCTION_NAME')

        # deployment_bucket = "medialake-iac-assets-us-east-1"
        # deployment_zip = "lambda/s3-connector.zip"
        target_function_name = "test_connector"
        # target_function_name = f{}
        
        # Generate unique ID and timestamps
        connector_id = str(uuid.uuid4())
        current_time = datetime.utcnow().isoformat(timespec='seconds')

        # Validate request body
        s3_bucket = createconnector.confi   guration.bucket
        connector_name = createconnector.name

        target_function_name = f"medialake_connector_{s3_bucket}"
        
        # Validate S3 bucket exists and get its region
        try:
            bucket_location = s3_client.get_bucket_location(Bucket=s3_bucket)
            bucket_region = bucket_location['LocationConstraint']
            bucket_region = bucket_region or 'us-east-1'
        except s3_client.exceptions.ClientError:
            return {
                "statusCode": 400,
                "body": {
                    "status": "400",
                    "message": (
                        f"S3 bucket '{s3_bucket}' does not exist or is not "
                        "accessible"
                    ),
                    "data": {}
                }
            }

        # Initialize S3 and SQS clients in the bucket's region
        s3 = boto3.client('s3', region_name=bucket_region)
        sqs = boto3.client('sqs', region_name=bucket_region)

        # Create SQS queue in the same region as the bucket
        queue_name = f"{s3_bucket}-notifications"
        response = sqs.create_queue(QueueName=queue_name)
        queue_url = response["QueueUrl"]

        # Get the SQS queue ARN
        response = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=["QueueArn"]
        )
        queue_arn = response["Attributes"]["QueueArn"]

        # Deploy lambda if environment variables are set
        try:
            # Get the INGEST_EVENT_BUS environment variable
        ingest_event_bus = os.environ.get('INGEST_EVENT_BUS')
        
        # Create IAM role for Lambda
        role_name = f"{target_function_name}-role"
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }
        
        create_role_response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
            Tags=[{'Key': 'medialake', 'Value': medialake_tag}]
        )
        lambda_role_arn = create_role_response['Role']['Arn']
        
        # Attach policies to the role
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
        )
        
        # Create custom policy for SQS permissions
        sqs_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:GetQueueAttributes",
                    "sqs:ChangeMessageVisibility"
                ],
                "Resource": queue_arn
            }]
        }
        
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}-sqs-policy",
            PolicyDocument=json.dumps(sqs_policy)
        )
        
        # Create custom policy for EventBridge permissions
        eventbridge_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "events:PutEvents"
                ],
                "Resource": ingest_event_bus
            }]
        }
        
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}-eventbridge-policy",
            PolicyDocument=json.dumps(eventbridge_policy)
        )
            
            ingest_event_bus = os.environ.get('INGEST_EVENT_BUS')
            
            # Deploy the lambda
            create_function_response = lambda_client.create_function(
                FunctionName=target_function_name,
                Runtime='python3.12',
                Role=lambda_role_arn,
                Handler='index.handler',
                Code={
                    'S3Bucket': deployment_bucket,
                    'S3Key': deployment_zip
                },
                Publish=True,
                Tags={'medialake': medialake_tag},
                Environment={
                    'Variables': {
                        'INGEST_EVENT_BUS': ingest_event_bus
                    }
                }
            )
            logger.info(f"Deployed new lambda function: {target_function_name}")
            lambda_arn = create_function_response['FunctionArn']
            
            # Add SQS trigger to the deployed lambda
            lambda_client.create_event_source_mapping(
                EventSourceArn=queue_arn,
                FunctionName=target_function_name,
                Enabled=True
            )
            logger.info(
                f"Added SQS trigger to lambda: {target_function_name}"
            )
        except Exception as e:
            logger.error(f"Failed to deploy/configure lambda: {str(e)}")

        # Set up SQS queue policy
        queue_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "s3.amazonaws.com"},
                    "Action": "sqs:SendMessage",
                    "Resource": queue_arn,
                    "Condition": {
                        "ArnLike": {
                            "aws:SourceArn": f"arn:aws:s3:::{s3_bucket}"
                        }
                    }
                }
            ]
        }
        sqs.set_queue_attributes(
            QueueUrl=queue_url,
            Attributes={'Policy': json.dumps(queue_policy)}
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

        # Save the connector details in DynamoDB
        table_name = os.environ.get("MEDIALAKE_CONNECTOR_TABLE")
        if not table_name:
            return {
                "statusCode": 500,
                "body": {
                    "status": "500",
                    "message": (
                        "MEDIALAKE_CONNECTOR_TABLE environment variable "
                        "is not set"
                    ),
                    "data": {}
                }
            }

        table = dynamodb.Table(table_name)
        connector_item = {
            "id": connector_id,
            "name": connector_name,
            "type": createconnector.type,
            "createdAt": current_time,
            "updatedAt": current_time,
            "storageIdentifier": s3_bucket,
            "sqsArn": queue_arn,
            "region": bucket_region,
            "queueUrl": queue_url,
            "lambdaArn": lambda_arn,
            "iamRoleArn": lambda_role_arn
        }
        table.put_item(Item=connector_item)

        logger.info(
            f"Created connector '{connector_name}' for bucket '{s3_bucket}'"
        )

        return {
            "status": "200",
            "message": "ok",
            "data": connector_item
        }

    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        return {
            "statusCode": 500,
            "body": {
                "status": "500",
                "message": "Internal server error",
                "data": {}
            }
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
