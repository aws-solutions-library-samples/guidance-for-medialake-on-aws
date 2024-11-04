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
from botocore.config import Config
import random
import string

tracer = Tracer()
logger = Logger()
app = APIGatewayRestResolver(enable_validation=True)

# Initialize AWS Clients S3 client - region will be determined per bucket
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
iam_client = boto3.client("iam")


class S3ConnectorConfig(BaseModel):
    bucket: str


class S3Connector(BaseModel):
    configuration: S3ConnectorConfig
    name: str
    type: str


def generate_suffix():
    """Generate a 6-digit alphanumeric suffix"""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=6))


@app.exception_handler(RequestValidationError)
def handle_validation_error(ex: RequestValidationError):
    logger.error(
        "Request failed validation", path=app.current_event.path, errors=ex.errors()
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
    # Track created resources for cleanup in case of failure
    created_resources = []
    try:
        # medialake_tag = os.environ.get('MEDIALAKE_TAG', 'medialake')
        medialake_tag = "medialake"
        # Get deployment configuration from environment variables
        deployment_bucket = os.environ.get("IAC_ASSETS_BUCKET")
        deployment_zip: str | None = os.environ.get("S3_CONNECTOR_LAMBDA")

        # Generate unique ID and timestamps
        connector_id = str(uuid.uuid4())
        current_time = datetime.utcnow().isoformat(timespec="seconds")

        # Get request variables from request body
        s3_bucket = createconnector.configuration.bucket
        connector_name = createconnector.name
        # Generate unique suffix for this deployment
        resource_suffix = generate_suffix()
        # Create resource specific name prefix with suffix
        resource_name_prefix = f"medialake_s3Connector_{s3_bucket}_{resource_suffix}"
        target_function_name = f"medialake_connector_{s3_bucket}_{resource_suffix}"

        # Validate S3 bucket exists and get its region
        try:
            bucket_location = s3_client.get_bucket_location(Bucket=s3_bucket)
            bucket_region = bucket_location["LocationConstraint"]
        except s3_client.exceptions.ClientError:
            return {
                "statusCode": 400,
                "body": {
                    "status": "400",
                    "message": (
                        f"S3 bucket '{s3_bucket}' does not exist or is not "
                        "accessible"
                    ),
                    "data": {},
                },
            }

        # Initialize S3, SQS, and Lambda clients in the bucket's region
        s3 = boto3.client("s3", region_name=bucket_region)
        sqs = boto3.client("sqs", region_name=bucket_region)
        lambda_client = boto3.client(
            "lambda",
            config=Config(
                region_name=bucket_region, s3={"addressing_style": "virtual"}
            ),
        )

        # Create SQS queue in the same region as the bucket
        queue_name = f"{resource_name_prefix}-notifications-{resource_suffix}"
        response = sqs.create_queue(
            QueueName=queue_name,
            Attributes={"VisibilityTimeout": "360"},  # 1.2x Lambda timeout (300s)
        )
        queue_url = response["QueueUrl"]
        created_resources.append(("sqs_queue", queue_url))

        # Get the SQS queue ARN
        response = sqs.get_queue_attributes(
            QueueUrl=queue_url, AttributeNames=["QueueArn"]
        )
        queue_arn = response["Attributes"]["QueueArn"]

        # Deploy lambda if environment variables are set
        try:
            # Get the Lambda environment variable
            ingest_event_bus = os.environ.get("INGEST_EVENT_BUS")
            medialake_asset_table = os.environ.get("MEDIALAKE_ASSET_TABLE")
            layer_arn = os.environ.get("INGEST_MEDIA_PROCESSOR_LAYER")

            # Create Lambda execution, IAM roles for Lambda
            role_name = f"{resource_name_prefix}-role"
            assume_role_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }
            create_role_response = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(assume_role_policy),
                Tags=[{"Key": "medialake", "Value": medialake_tag}],
            )
            lambda_role_arn = create_role_response["Role"]["Arn"]
            created_resources.append(("iam_role", role_name))

            # Add delay to allow IAM role to propagate
            time.sleep(5)

            # Attach policies to the role
            iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            )
            created_resources.append(
                ("role_policy", (role_name, "AWSLambdaBasicExecutionRole"))
            )

            # Create custom policy for SQS permissions
            sqs_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "sqs:ReceiveMessage",
                            "sqs:DeleteMessage",
                            "sqs:GetQueueAttributes",
                            "sqs:ChangeMessageVisibility",
                        ],
                        "Resource": queue_arn,
                    }
                ],
            }

            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=f"{role_name}-sqs-policy-{resource_suffix}",
                PolicyDocument=json.dumps(sqs_policy),
            )
            created_resources.append(
                (
                    "inline_policy",
                    (role_name, f"{role_name}-sqs-policy-{resource_suffix}"),
                )
            )

            # Add delay to allow policy to propagate
            time.sleep(10)

            # Attach policies to the role
            iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            )
            created_resources.append(
                ("role_policy", (role_name, "AWSLambdaBasicExecutionRole"))
            )

            # Create custom policy for SQS permissions
            sqs_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "sqs:ReceiveMessage",
                            "sqs:DeleteMessage",
                            "sqs:GetQueueAttributes",
                            "sqs:ChangeMessageVisibility",
                        ],
                        "Resource": queue_arn,
                    }
                ],
            }

            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=f"{role_name}-sqs-policy-{resource_suffix}",
                PolicyDocument=json.dumps(sqs_policy),
            )
            created_resources.append(
                (
                    "inline_policy",
                    (role_name, f"{role_name}-sqs-policy-{resource_suffix}"),
                )
            )
            # Create custom policy for S3 permissions
            s3_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:PutObjectTagging",
                            "s3:GetObjectTagging",
                            "s3:GetBucketLocation",
                            "s3:GetObject",
                            "s3:ListBucket",
                        ],
                        "Resource": [
                            f"arn:aws:s3:::{s3_bucket}",
                            f"arn:aws:s3:::{s3_bucket}/*",
                        ],
                    }
                ],
            }
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=f"{role_name}-s3-policy-{resource_suffix}",
                PolicyDocument=json.dumps(s3_policy),
            )
            created_resources.append(
                (
                    "inline_policy",
                    (role_name, f"{role_name}-s3-policy-{resource_suffix}"),
                )
            )

            # Create custom policy for EventBridge permissions
            eventbridge_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["events:PutEvents"],
                        "Resource": f"arn:aws:events:{bucket_region}:{boto3.client('sts').get_caller_identity()['Account']}:event-bus/{ingest_event_bus}",
                    }
                ],
            }

            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=f"{role_name}-eventbridge-policy-{resource_suffix}",
                PolicyDocument=json.dumps(eventbridge_policy),
            )
            created_resources.append(
                (
                    "inline_policy",
                    (role_name, f"{role_name}-eventbridge-policy-{resource_suffix}"),
                )
            )

            # Create custom policy for DynamoDB permissions
            dynamodb_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:GetItem",
                            "dynamodb:PutItem",
                            "dynamodb:UpdateItem",
                            "dynamodb:DeleteItem",
                            "dynamodb:Query",
                            "dynamodb:Scan",
                        ],
                        "Resource": medialake_asset_table,
                    }
                ],
            }

            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=f"{role_name}-dynamodb-policy-{resource_suffix}",
                PolicyDocument=json.dumps(dynamodb_policy),
            )
            created_resources.append(
                (
                    "inline_policy",
                    (role_name, f"{role_name}-dynamodb-policy-{resource_suffix}"),
                )
            )

            ingest_event_bus = os.environ.get("INGEST_EVENT_BUS")

            # Deploy the lambda with proper S3 configuration
            create_function_response = lambda_client.create_function(
                FunctionName=target_function_name,
                Runtime="python3.12",
                Role=lambda_role_arn,
                Handler="index.handler",
                Code={"S3Bucket": deployment_bucket, "S3Key": deployment_zip},
                Publish=True,
                Tags={"medialake": medialake_tag},
                Environment={
                    "Variables": {
                        "INGEST_EVENT_BUS": ingest_event_bus,
                        "MEDIALAKE_ASSET_TABLE": medialake_asset_table,
                    }
                },
                Layers=[layer_arn] if layer_arn else [],
                Timeout=300,  # 5 minutes
            )
            logger.info(f"Deployed new lambda function: {target_function_name}")
            lambda_arn = create_function_response["FunctionArn"]
            created_resources.append(("lambda_function", target_function_name))

            # Add SQS trigger to the deployed lambda
            event_source_mapping = lambda_client.create_event_source_mapping(
                EventSourceArn=queue_arn,
                FunctionName=target_function_name,
                Enabled=True,
            )
            created_resources.append(
                ("event_source_mapping", event_source_mapping["UUID"])
            )
            logger.info(f"Added SQS trigger to lambda: {target_function_name}")
        except Exception as e:
            logger.error(f"Failed to deploy/configure lambda: {str(e)}")
            raise

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
                        "ArnLike": {"aws:SourceArn": f"arn:aws:s3:::{s3_bucket}"}
                    },
                }
            ],
        }
        sqs.set_queue_attributes(
            QueueUrl=queue_url, Attributes={"Policy": json.dumps(queue_policy)}
        )
        created_resources.append(("queue_policy", queue_url))

        # Subscribe SQS queue to S3 bucket notifications
        notification_config = {
            "QueueConfigurations": [
                {"QueueArn": queue_arn, "Events": ["s3:ObjectCreated:*"]}
            ]
        }
        s3.put_bucket_notification_configuration(
            Bucket=s3_bucket, NotificationConfiguration=notification_config
        )
        created_resources.append(("bucket_notification", s3_bucket))

        # Save the connector details in DynamoDB
        table_name = os.environ.get("MEDIALAKE_CONNECTOR_TABLE")
        if not table_name:
            return {
                "statusCode": 500,
                "body": {
                    "status": "500",
                    "message": (
                        "MEDIALAKE_CONNECTOR_TABLE environment variable " "is not set"
                    ),
                    "data": {},
                },
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
            "iamRoleArn": lambda_role_arn,
        }
        table.put_item(Item=connector_item)
        created_resources.append(("dynamodb_item", (table_name, connector_id)))

        logger.info(f"Created connector '{connector_name}' for bucket '{s3_bucket}'")

        return {"status": "200", "message": "ok", "data": connector_item}

    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        # Clean up created resources in reverse order
        for resource_type, resource_id in reversed(created_resources):
            try:
                if resource_type == "dynamodb_item":
                    table_name, item_id = resource_id
                    table = dynamodb.Table(table_name)
                    table.delete_item(Key={"id": item_id})
                elif resource_type == "bucket_notification":
                    s3.put_bucket_notification_configuration(
                        Bucket=resource_id, NotificationConfiguration={}
                    )
                elif resource_type == "queue_policy":
                    sqs.set_queue_attributes(
                        QueueUrl=resource_id, Attributes={"Policy": ""}
                    )
                elif resource_type == "event_source_mapping":
                    lambda_client.delete_event_source_mapping(UUID=resource_id)
                elif resource_type == "lambda_function":
                    lambda_client.delete_function(FunctionName=resource_id)
                elif resource_type == "inline_policy":
                    role_name, policy_name = resource_id
                    iam_client.delete_role_policy(
                        RoleName=role_name, PolicyName=policy_name
                    )
                elif resource_type == "role_policy":
                    role_name, policy_name = resource_id
                    iam_client.detach_role_policy(
                        RoleName=role_name,
                        PolicyArn=f"arn:aws:iam::aws:policy/service-role/{policy_name}",
                    )
                elif resource_type == "iam_role":
                    iam_client.delete_role(RoleName=resource_id)
                elif resource_type == "sqs_queue":
                    sqs.delete_queue(QueueUrl=resource_id)
                logger.info(f"Cleaned up {resource_type}: {resource_id}")
            except Exception as cleanup_error:
                logger.error(
                    f"Error cleaning up {resource_type} {resource_id}: {str(cleanup_error)}"
                )

        return {
            "statusCode": 500,
            "body": {"status": "500", "message": "Internal server error", "data": {}},
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
