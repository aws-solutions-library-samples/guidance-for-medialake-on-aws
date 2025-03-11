import os
import uuid
import json
import time
import string
import random
import boto3
import traceback
from datetime import datetime
from typing import List, Any
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
from botocore.exceptions import ClientError

tracer = Tracer()
logger = Logger()
app = APIGatewayRestResolver(enable_validation=True)

# Initialize AWS Clients S3 client - region will be determined per bucket
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
iam_client = boto3.client("iam")
pipes = boto3.client("pipes")


class S3ConnectorConfig(BaseModel):
    bucket: str
    s3IntegrationMethod: str
    objectPrefix: str | None = None


class S3Connector(BaseModel):
    configuration: S3ConnectorConfig
    name: str
    type: str
    description: str | None = None


def wait_for_iam_role_propagation(iam_client, role_name, max_retries=5, base_delay=5):
    for attempt in range(max_retries):
        try:
            iam_client.get_role(RoleName=role_name)
            time.sleep(base_delay)
            return True
        except iam_client.exceptions.NoSuchEntityException:
            delay = (2**attempt) * base_delay
            time.sleep(delay)
    return False


def wait_for_policy_attachment(
    iam_client, role_name, policy_arn, max_retries=5, base_delay=10
):
    for attempt in range(max_retries):
        try:
            attached_policies = iam_client.list_attached_role_policies(
                RoleName=role_name
            )["AttachedPolicies"]
            if any(policy["PolicyArn"] == policy_arn for policy in attached_policies):
                time.sleep(base_delay)
                return True
            delay = (2**attempt) * base_delay
            time.sleep(delay)
        except iam_client.exceptions.NoSuchEntityException:
            delay = (2**attempt) * base_delay
            time.sleep(delay)
    return False


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


def setup_eventbridge_notifications(
    s3_bucket: str, bucket_region: str, created_resources: list, object_prefix: str
) -> tuple[str, str]:
    """Set up EventBridge notifications and return queue URL and ARN"""

    eventbridge = boto3.client("events", region_name=bucket_region)
    sqs = boto3.client("sqs", region_name=bucket_region)
    s3 = boto3.client("s3", region_name=bucket_region)

    # Get existing notification configuration
    try:
        existing_config = s3.get_bucket_notification_configuration(Bucket=s3_bucket)
    except ClientError as e:
        logger.error(
            f"Failed to get existing bucket notification configuration: {str(e)}"
        )
        raise

    # Remove ResponseMetadata and add EventBridge configuration
    updated_config = {
        k: v for k, v in existing_config.items() if k != "ResponseMetadata"
    }
    updated_config["EventBridgeConfiguration"] = {}

    # Enable EventBridge notifications on the S3 bucket
    try:
        s3.put_bucket_notification_configuration(
            Bucket=s3_bucket,
            NotificationConfiguration=updated_config,
        )
        logger.info(f"Enabled EventBridge notifications for bucket {s3_bucket}")
        created_resources.append(("eventbridge_config", s3_bucket))
    except ClientError as e:
        logger.error(f"Failed to enable EventBridge notifications: {str(e)}")
        raise

    # Create FIFO SQS queue with queue-level throughput limit
    queue_name = f"medialake-connector-{s3_bucket}-eventbridge.fifo"
    response = sqs.create_queue(
        QueueName=queue_name,
        Attributes={
            "VisibilityTimeout": "360",
            "FifoQueue": "true",
            "ContentBasedDeduplication": "true",
            "DeduplicationScope": "queue",
            "FifoThroughputLimit": "perQueue",
        },
    )
    queue_url = response["QueueUrl"]
    created_resources.append(("sqs_queue", queue_url))

    # Get queue ARN
    response = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])
    queue_arn = response["Attributes"]["QueueArn"]

    # Get account ID
    account_id = boto3.client("sts").get_caller_identity()["Account"]

    # Create EventBridge rule with comprehensive event pattern
    rule_name = f"medialake-{s3_bucket}-s3-events"
    event_pattern = {
        "source": ["aws.s3"],
        "detail-type": [
            "Object Created",
            "Object Deleted",
            "Object Restore Completed",
            "Object Restore Initiated",
            "Object Restore Expired",
            "Object Tags Added",
            "Object Tags Deleted",
            "Object ACL Updated",
            "Object Storage Class Changed",
        ],
        "detail": {
            "bucket": {"name": [s3_bucket]},
            "object": {"key": [{"anything-but": ""}]},
        },
    }
    
    # Add prefix filter if object_prefix is provided
    if object_prefix:
        # Ensure prefix ends with '/'
        prefix = object_prefix if object_prefix.endswith('/') else f"{object_prefix}/"
        event_pattern["detail"]["object"]["key"] = [
            {
                "prefix": prefix
            }
        ]

    eventbridge.put_rule(
        Name=rule_name,
        EventPattern=json.dumps(event_pattern),
        State="ENABLED",
        Description=f"Rule for S3 bucket {s3_bucket} object creation events",
    )
    created_resources.append(("eventbridge_rule", rule_name))

    # Set up SQS queue policy to allow EventBridge
    queue_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowEventBridgeSendMessage",
                "Effect": "Allow",
                "Principal": {"Service": "events.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": queue_arn,
                "Condition": {
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:events:{bucket_region}:{account_id}:rule/{rule_name}"
                    }
                },
            }
        ],
    }
    sqs.set_queue_attributes(
        QueueUrl=queue_url, Attributes={"Policy": json.dumps(queue_policy)}
    )
    created_resources.append(("queue_policy", queue_url))

    # Add SQS as target for the EventBridge rule
    target_id = f"SQSTarget-{s3_bucket}"
    eventbridge.put_targets(
        Rule=rule_name,
        Targets=[
            {
                "Id": target_id,
                "Arn": queue_arn,
                "SqsParameters": {
                    "MessageGroupId": "s3events"  # Required for FIFO queues
                },
            }
        ],
    )
    created_resources.append(("eventbridge_target", (rule_name, target_id)))

    return queue_url, queue_arn


def create_eventbridge_role(
    bucket_region: str, queue_arn: str, rule_name: str, created_resources: list
) -> str:
    """Create IAM role for EventBridge to send events to SQS"""

    iam = boto3.client("iam")
    # Truncate role name if it exceeds 64 characters
    role_name = f"medialake-eb-{rule_name}"
    if len(role_name) > 64:
        role_name = role_name[:64]

    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "events.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    role = iam.create_role(
        RoleName=role_name, AssumeRolePolicyDocument=json.dumps(assume_role_policy)
    )
    created_resources.append(("iam_role", role_name))

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Action": "sqs:SendMessage", "Resource": queue_arn}
        ],
    }

    iam.put_role_policy(
        RoleName=role_name,
        PolicyName=f"{role_name}-policy",
        PolicyDocument=json.dumps(policy),
    )
    created_resources.append(("inline_policy", (role_name, f"{role_name}-policy")))

    return role["Role"]["Arn"]


def check_existing_connector(s3_bucket: str) -> dict | None:
    """
    Check if a connector already exists for the given S3 bucket

    Args:
        s3_bucket: The name of the S3 bucket to check

    Returns:
        dict: The existing connector details if found, None otherwise
    """
    try:
        table_name = os.environ.get("MEDIALAKE_CONNECTOR_TABLE")
        if not table_name:
            raise ValueError(
                "MEDIALAKE_CONNECTOR_TABLE environment variable is not set"
            )

        table = dynamodb.Table(table_name)

        # Scan the table for matching storage identifier
        # Note: In production, you might want to create a GSI on storageIdentifier for better performance
        response = table.scan(
            FilterExpression="storageIdentifier = :bucket",
            ExpressionAttributeValues={":bucket": s3_bucket},
        )

        if response["Items"]:
            return response["Items"][0]

        return None

    except Exception as e:
        logger.error(f"Error checking for existing connector: {str(e)}")
        raise


def get_bucket_kms_key(s3_client, bucket_name):
    try:
        encryption = s3_client.get_bucket_encryption(Bucket=bucket_name)
        rules = encryption["ServerSideEncryptionConfiguration"]["Rules"]
        for rule in rules:
            if rule["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"] == "aws:kms":
                return rule["ApplyServerSideEncryptionByDefault"]["KMSMasterKeyID"]
    except s3_client.exceptions.ClientError as e:
        logger.error(f"Failed to get bucket encryption: {str(e)}")
        return None


def create_lambda_iam_role(iam_client, role_name, kms_key_arn=None):
    # Truncate role name if it exceeds 64 characters
    if len(role_name) > 64:
        role_name = role_name[:64]

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
    role = iam_client.create_role(
        RoleName=role_name, AssumeRolePolicyDocument=json.dumps(assume_role_policy)
    )
    # Attach the basic execution role policy
    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )
    if kms_key_arn:
        # Create and attach a policy for the KMS key
        kms_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "kms:Encrypt",
                        "kms:Decrypt",
                        "kms:ReEncrypt*",
                        "kms:GenerateDataKey*",
                        "kms:DescribeKey",
                    ],
                    "Resource": kms_key_arn,
                }
            ],
        }
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}-kms-policy",
            PolicyDocument=json.dumps(kms_policy),
        )
    return role["Role"]["Arn"]


def check_existing_s3_notifications(s3_client, bucket_name):
    try:
        response = s3_client.get_bucket_notification_configuration(Bucket=bucket_name)
        return any(
            [
                response.get("TopicConfigurations"),
                response.get("QueueConfigurations"),
                response.get("LambdaFunctionConfigurations"),
            ]
        )
    except s3_client.exceptions.ClientError as e:
        logger.error(f"Error checking S3 notifications: {str(e)}")
        return False
    
def update_bucket_notifications(s3: Any, s3_bucket: str, connector_id: str, queue_arn: str, object_prefix: str) -> List[str]:
    errors: List[str] = []
    try:
        # Get existing configuration
        current_config = s3.get_bucket_notification_configuration(Bucket=s3_bucket)
        
        # Create new configuration starting with existing config
        new_config = current_config.copy()
        
        # Remove ResponseMetadata from the configuration
        new_config = {
            k: v for k, v in current_config.items() 
            if k != 'ResponseMetadata'
        }
        
        # Prepare new queue configuration
        new_queue_config = {
            "Id": f"{os.environ.get('RESOURCE_PREFIX')}_notifications_{connector_id}",
            "QueueArn": queue_arn,
            "Events": [
                "s3:ObjectCreated:*",
                "s3:ObjectRemoved:*",
                "s3:ObjectRestore:*",
                "s3:ObjectTagging:*",
                "s3:ObjectAcl:Put",
            ]
        }

        # Add filter if object_prefix is provided
        if object_prefix:
            new_queue_config["Filter"] = {
                "Key": {
                    "FilterRules": [
                        {
                            "Name": "prefix",
                            "Value": object_prefix if object_prefix.endswith('/') else f"{object_prefix}/"
                        }
                    ]
                }
            }
            
        # Update QueueConfigurations
        new_config['QueueConfigurations'] = [
            config for config in new_config.get('QueueConfigurations', [])
            if config.get('Id') != new_queue_config['Id']
        ]
        new_config['QueueConfigurations'].append(new_queue_config)


        # Apply the updated configuration
        s3.put_bucket_notification_configuration(
            Bucket=s3_bucket,
            NotificationConfiguration=new_config
        )
        
        logger.info(f"Updated bucket notifications for bucket: {s3_bucket}")
        return []
        
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchBucket":
            error_msg = f"Error updating S3 bucket notifications: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error updating bucket notifications: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)
    
    return errors


def create_eventbridge_pipe(
    resource_name_prefix: str,
    queue_arn: str,
    lambda_arn: str,
    bucket_region: str,
    created_resources: list,
) -> tuple[str, str]:
    """Create EventBridge Pipe between SQS and Lambda"""

    # Truncate pipe role name if it exceeds 64 characters
    pipe_role_name = f"{resource_name_prefix}-pipe-role"
    if len(pipe_role_name) > 64:
        pipe_role_name = pipe_role_name[:64]

    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "pipes.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    pipe_role = iam_client.create_role(
        RoleName=pipe_role_name, AssumeRolePolicyDocument=json.dumps(assume_role_policy)
    )
    created_resources.append(("iam_role", pipe_role_name))
    pipe_role_arn = pipe_role["Role"]["Arn"]

    # Create policy for source (SQS) permissions
    source_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:GetQueueAttributes",
                ],
                "Resource": queue_arn,
            }
        ],
    }

    iam_client.put_role_policy(
        RoleName=pipe_role_name,
        PolicyName=f"{pipe_role_name}-source-policy",
        PolicyDocument=json.dumps(source_policy),
    )
    created_resources.append(
        ("inline_policy", (pipe_role_name, f"{pipe_role_name}-source-policy"))
    )

    # Create policy for target (Lambda) permissions
    target_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["lambda:InvokeFunction"],
                "Resource": lambda_arn,
            }
        ],
    }

    iam_client.put_role_policy(
        RoleName=pipe_role_name,
        PolicyName=f"{pipe_role_name}-target-policy",
        PolicyDocument=json.dumps(target_policy),
    )
    created_resources.append(
        ("inline_policy", (pipe_role_name, f"{pipe_role_name}-target-policy"))
    )

    # Wait for role and policies to propagate
    if not wait_for_iam_role_propagation(iam_client, pipe_role_name):
        raise Exception(f"IAM role {pipe_role_name} did not propagate in time")

    # Create the pipe
    pipe_name = f"{resource_name_prefix}-pipe"
    response = pipes.create_pipe(
        Name=pipe_name,
        RoleArn=pipe_role_arn,
        Source=queue_arn,
        Target=lambda_arn,
        SourceParameters={
            "SqsQueueParameters": {
                "BatchSize": 10
                # Removed MaximumBatchingWindowInSeconds for FIFO queue
            }
        },
        TargetParameters={
            "LambdaFunctionParameters": {"InvocationType": "FIRE_AND_FORGET"}
        },
    )
    created_resources.append(("eventbridge_pipe", pipe_name))
    pipe_arn = response["Arn"]

    return pipe_arn, pipe_role_arn


@app.post("/connectors/s3")
def create_connector(createconnector: S3Connector) -> dict:
    created_resources = []
    try:
        s3_bucket = createconnector.configuration.bucket

        # Check for existing connector
        existing_connector = check_existing_connector(s3_bucket)
        if existing_connector:
            return {
                "status": "400",
                "message": f"Connector already exists for bucket {s3_bucket}",
                "data": {},
            }

        # medialake_tag = os.environ.get('MEDIALAKE_TAG', 'medialake')
        medialake_tag = "medialake"
        # Get deployment configuration from environment variables
        deployment_bucket = os.environ.get("IAC_ASSETS_BUCKET")
        deployment_zip: str | None = os.environ.get("S3_CONNECTOR_LAMBDA")

        # Generate unique ID and timestamps
        connector_id = str(uuid.uuid4())
        current_time = datetime.utcnow().isoformat(timespec="seconds")

        def generate_suffix():
            """Generate a 6-digit alphanumeric suffix"""
            return "".join(random.choices(string.ascii_lowercase + string.digits, k=6))

        # Get request variables from request body
        connector_name = createconnector.name
        connector_description = createconnector.description
        integration_method = createconnector.configuration.s3IntegrationMethod
        object_prefix = createconnector.configuration.objectPrefix

        suffix = generate_suffix()

        # Create resource specific name prefix
        resource_name_prefix = (
            f"{os.environ.get('RESOURCE_PREFIX')}_connector_{s3_bucket}"
        )
        # Ensure the total length does not exceed 64 characters
        max_prefix_length = 64 - len(suffix) - 1
        if len(resource_name_prefix) > max_prefix_length:
            resource_name_prefix = resource_name_prefix[:max_prefix_length]

        target_function_name = f"{resource_name_prefix}_{suffix}"

        # Validate S3 bucket exists and get its region
        try:
            bucket_location = s3_client.get_bucket_location(Bucket=s3_bucket)
            bucket_region = bucket_location["LocationConstraint"]
            bucket_region = bucket_region or "us-east-1"
        except s3_client.exceptions.ClientError:
            return {
                "status": "400",
                "message": (
                    f"S3 bucket '{s3_bucket}' does not exist or is not accessible"
                ),
                "data": {},
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

        # Set up notifications based on integration method
        queue_url = None
        queue_arn = None
        if integration_method == "eventbridge":
            queue_url, queue_arn = setup_eventbridge_notifications(
                s3_bucket, bucket_region, created_resources, object_prefix
            )
        elif integration_method in ["s3Notifications"]:
            # Set up S3 event notifications
            # Create SQS queue in the same region as the bucket
            queue_name = f"-connector-{s3_bucket}-notifications"
            response = sqs.create_queue(
                QueueName=queue_name, Attributes={"VisibilityTimeout": "360"}
            )
            queue_url = response["QueueUrl"]
            created_resources.append(("sqs_queue", queue_url))

            # Get queue ARN
            response = sqs.get_queue_attributes(
                QueueUrl=queue_url, AttributeNames=["QueueArn"]
            )
            queue_arn = response["Attributes"]["QueueArn"]

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

            errors = update_bucket_notifications(
                s3=s3_client,
                s3_bucket=s3_bucket,
                connector_id=connector_id,
                queue_arn=queue_arn,
                object_prefix=object_prefix
            )
            if not errors:
                created_resources.append(("bucket_notification", s3_bucket))
            else:
                logger.info(f"Encountered errors: {errors}")
                raise Exception(
                    f"Error: Failed to set up notifications for bucket {s3_bucket}: {errors}"
                )

            created_resources.append(("bucket_notification", s3_bucket))
        else:
            raise ValueError(f"Invalid integration method: {integration_method}")

        if queue_url is None or queue_arn is None:
            raise ValueError(
                f"Failed to set up notifications: queue_url or queue_arn is None for integration method {integration_method}"
            )

        # Deploy lambda if environment variables are set
        try:
            # Get the Lambda environment variable
            ingest_event_bus = os.environ.get("INGEST_EVENT_BUS")
            medialake_asset_table = os.environ.get("MEDIALAKE_ASSET_TABLE")
            asset_table_file_hash_index_arn = os.environ.get(
                "MEDIALAKE_ASSET_TABLE_FILE_HASH_INDEX"
            )
            asset_table_asset_id_index_arn = os.environ.get(
                "MEDIALAKE_ASSET_TABLE_ASSET_ID_INDEX"
            )
            layer_arn = os.environ.get("INGEST_MEDIA_PROCESSOR_LAYER")

            # Create Lambda execution, IAM roles for Lambda
            role_name = f"{resource_name_prefix}-role"
            bucket_kms_key = get_bucket_kms_key(s3_client, s3_bucket)
            lambda_role_arn = create_lambda_iam_role(
                iam_client, role_name, bucket_kms_key
            )
            created_resources.append(("iam_role", role_name))

            # Wait for role to be available

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

            # Define the policy ARN
            policy_arn = (
                "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            )

            # Attach policies to the role
            iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)

            # Attach policies to the role
            iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
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
                PolicyName=f"{role_name}-sqs-policy",
                PolicyDocument=json.dumps(sqs_policy),
            )
            created_resources.append(
                ("inline_policy", (role_name, f"{role_name}-sqs-policy"))
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
                PolicyName=f"{role_name}-s3-policy",
                PolicyDocument=json.dumps(s3_policy),
            )
            created_resources.append(
                ("inline_policy", (role_name, f"{role_name}-s3-policy"))
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
                PolicyName=f"{role_name}-eventbridge-policy",
                PolicyDocument=json.dumps(eventbridge_policy),
            )
            created_resources.append(
                ("inline_policy", (role_name, f"{role_name}-eventbridge-policy"))
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
                        "Resource": [
                            medialake_asset_table,
                            asset_table_file_hash_index_arn,
                            asset_table_asset_id_index_arn,
                        ],
                    }
                ],
            }

            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=f"{role_name}-dynamodb-policy",
                PolicyDocument=json.dumps(dynamodb_policy),
            )
            created_resources.append(
                ("inline_policy", (role_name, f"{role_name}-dynamodb-policy"))
            )

            ingest_event_bus = os.environ.get("INGEST_EVENT_BUS")

            # Get current AWS account ID
            account_id = boto3.client("sts").get_caller_identity()["Account"]
            # Construct AWS SDK Python layer ARN using current account
            aws_sdk_layer_arn = f"arn:aws:lambda:{bucket_region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-x86_64:2"
            # Get any existing layers
            layers = [layer_arn] if layer_arn else []
            # Add AWS SDK layer
            layers.append(aws_sdk_layer_arn)
            # Wait for policy attachment to propagate
            if not wait_for_iam_role_propagation(iam_client, role_name):
                raise Exception(f"IAM role {role_name} did not propagate in time")

            if not wait_for_policy_attachment(iam_client, role_name, policy_arn):
                raise Exception(
                    f"Policy {policy_arn} did not attach to role {role_name} in time"
                )

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
                        "POWERTOOLS_SERVICE_NAME": "asset-processor",
                        "POWERTOOLS_METRICS_NAMESPACE": "AssetProcessor",
                        "ASSETS_TABLE": medialake_asset_table,
                        "EVENT_BUS_NAME": ingest_event_bus,
                    }
                },
                Layers=layers,  # Updated to include both custom and AWS SDK layers
                Timeout=300,  # 5 minutes
            )
            logger.info(f"Deployed new lambda function: {target_function_name}")
            lambda_arn = create_function_response["FunctionArn"]
            created_resources.append(("lambda_function", target_function_name))

            # Instead of creating event source mapping, create EventBridge Pipe
            pipe_arn, pipe_role_arn = create_eventbridge_pipe(
                resource_name_prefix,
                queue_arn,
                lambda_arn,
                bucket_region,
                created_resources,
            )
            logger.info(f"Created EventBridge Pipe: {pipe_arn} with role: {pipe_role_arn}")
        except Exception as e:
            logger.error(f"Failed to deploy/configure lambda: {str(e)}")
            raise

        # Save the connector details in DynamoDB
        table_name = os.environ.get("MEDIALAKE_CONNECTOR_TABLE")
        if not table_name:
            return {
                "status": "500",
                "message": (
                    "MEDIALAKE_CONNECTOR_TABLE environment variable is not set"
                ),
                "data": {},
            }

        table = dynamodb.Table(table_name)
        connector_item = {
            "id": connector_id,
            "name": connector_name,
            "status": "active",
            "description": connector_description,
            "type": createconnector.type,
            "createdAt": current_time,
            "updatedAt": current_time,
            "storageIdentifier": s3_bucket,
            "integrationMethod": integration_method,
            "sqsArn": queue_arn,
            "region": bucket_region,
            "queueUrl": queue_url,
            "lambdaArn": lambda_arn,
            "iamRoleArn": lambda_role_arn,
            "objectPrefix": object_prefix,
            "pipeArn": pipe_arn,
            "pipeRoleArn": pipe_role_arn
        }

        table.put_item(Item=connector_item)
        created_resources.append(("dynamodb_item", (table_name, connector_id)))

        logger.info(f"Created connector '{connector_name}' for bucket '{s3_bucket}'")

        return {"status": "200", "message": "ok", "data": connector_item}

    except Exception as e:
        eventbridge = boto3.client("events")
        pipes_client = boto3.client("pipes")
        logger.exception(f"Unexpected error: {str(e)}")
        error_traceback = traceback.format_exc()

        # Clean up created resources in reverse order
        for resource_type, resource_id in reversed(created_resources):
            try:
                if resource_type == "eventbridge_pipe":
                    pipes_client.delete_pipe(Name=resource_id)
                    logger.info(f"Deleted EventBridge Pipe: {resource_id}")
                elif resource_type == "eventbridge_target":
                    rule_name, target_id = resource_id
                    eventbridge.remove_targets(Rule=rule_name, Ids=[target_id])
                elif resource_type == "eventbridge_rule":
                    eventbridge.delete_rule(Name=resource_id)
                elif resource_type == "eventbridge_config":
                    # Remove EventBridge configuration from bucket
                    s3.put_bucket_notification_configuration(
                        Bucket=resource_id, NotificationConfiguration={}
                    )
                elif resource_type == "dynamodb_item":
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
            "status": "400",
            "message": str(e),
            "data": {
                "traceback": error_traceback,
                "created_resources": created_resources,
            },
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
