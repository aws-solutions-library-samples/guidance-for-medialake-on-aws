import os
import uuid
import json
import time
import string
import random
import boto3
import traceback
from datetime import datetime
from typing import List, Any, Optional
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
from pydantic import BaseModel, field_validator
from botocore.config import Config
from botocore.exceptions import ClientError

tracer = Tracer()
logger = Logger()
app = APIGatewayRestResolver(enable_validation=True)

# Get required env vars
MEDIALAKE_CONNECTOR_TABLE = os.environ["MEDIALAKE_CONNECTOR_TABLE"]
IAC_ASSETS_BUCKET = os.environ["IAC_ASSETS_BUCKET"]
S3_CONNECTOR_LAMBDA = os.environ["S3_CONNECTOR_LAMBDA"]
INGEST_MEDIA_PROCESSOR_LAYER = os.environ["INGEST_MEDIA_PROCESSOR_LAYER"]
INGEST_EVENT_BUS = os.environ["INGEST_EVENT_BUS"]
MEDIALAKE_ASSET_TABLE = os.environ["MEDIALAKE_ASSET_TABLE"]
MEDIALAKE_ASSET_TABLE_FILE_HASH_INDEX = os.environ[
    "MEDIALAKE_ASSET_TABLE_FILE_HASH_INDEX"
]
MEDIALAKE_ASSET_TABLE_ASSET_ID_INDEX = os.environ[
    "MEDIALAKE_ASSET_TABLE_ASSET_ID_INDEX"
]
MEDIALAKE_ASSET_TABLE_S3_PATH_INDEX = os.environ[
    "MEDIALAKE_ASSET_TABLE_S3_PATH_INDEX"
]
RESOURCE_PREFIX = os.environ["RESOURCE_PREFIX"]
RESOURCE_APPLICATION_TAG = os.environ["RESOURCE_APPLICATION_TAG"]


# Initialize AWS Clients S3 client - region will be determined per bucket
s3_client_default_region = boto3.client("s3")  # Keep one for region listing etc.
dynamodb = boto3.resource("dynamodb")
iam_client = boto3.client("iam")
pipes = boto3.client("pipes")
lambda_client = boto3.client("lambda")


class S3ConnectorConfig(BaseModel):
    # Make bucket optional initially, will be validated based on bucketType
    bucket: Optional[str] = None
    s3IntegrationMethod: str
    objectPrefix: list[str] | None = None
    # Add fields for new bucket creation
    bucketType: str  # 'new' or 'existing'
    region: Optional[str] = None  # Required if bucketType is 'new'

    @field_validator("bucket")
    @classmethod
    def bucket_required_for_existing(cls, v, values):
        if values.data.get("bucketType") == "existing" and not v:
            raise ValueError("Bucket name is required for existing buckets.")
        return v

    @field_validator("bucket")
    @classmethod
    def bucket_required_for_new(cls, v, values):
        if values.data.get("bucketType") == "new" and not v:
            raise ValueError("Bucket name is required for new buckets.")
        # Add basic S3 bucket name validation (can be more comprehensive)
        if v and (len(v) < 3 or len(v) > 63 or not v.islower() or v.startswith('-') or v.endswith('-')):
            raise ValueError("Invalid S3 bucket name format.")
        return v

    @field_validator("region")
    @classmethod
    def region_required_for_new(cls, v, values):
        if values.data.get("bucketType") == "new" and not v:
            raise ValueError("Region is required when creating a new bucket.")
        return v


class S3Connector(BaseModel):
    configuration: S3ConnectorConfig
    name: str
    type: str  # Should always be 's3' for this endpoint
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
    s3_bucket: str, bucket_region: str, created_resources: list, object_prefix: list[str] | None
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

    # Sanitize the bucket name for use in queue name (remove invalid chars)
    sanitized_bucket = ''.join(c for c in s3_bucket if c.isalnum() or c in '-_')
    
    # Create FIFO SQS queue with queue-level throughput limit
    # Ensure the queue name with .fifo suffix is 80 chars or less
    # Reserve 5 chars for suffix (.fifo)
    max_queue_name_length = 75  # 80 - 5 (.fifo)
    base_name = f"medialake-connector-{sanitized_bucket}-eventbridge"
    if len(base_name) > max_queue_name_length:
        base_name = base_name[:max_queue_name_length]
    
    queue_name = f"{base_name}.fifo"
    
    logger.info(f"Creating FIFO queue with name: {queue_name}")
    
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
    # Truncate rule name if it exceeds 63 characters (AWS limit is 64)
    if len(rule_name) > 63:
        rule_name = rule_name[:63]
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
    if object_prefix and len(object_prefix) > 0:
        # Create prefix filters for each prefix in the list
        prefixes = []
        for prefix in object_prefix:
            formatted_prefix = prefix if prefix.endswith('/') else f"{prefix}/"
            prefixes.append({"prefix": formatted_prefix})
        
        if prefixes:
            event_pattern["detail"]["object"]["key"] = prefixes

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
    
def update_bucket_notifications(s3: Any, s3_bucket: str, connector_id: str, queue_arn: str, object_prefix: list[str] | None) -> List[str]:
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
        
        # Initialize QueueConfigurations if it doesn't exist
        if 'QueueConfigurations' not in new_config:
            new_config['QueueConfigurations'] = []
        
        # Remove any existing configurations with our prefix
        prefix_id_base = f"{os.environ.get('RESOURCE_PREFIX')}_notifications_{connector_id}"
        new_config['QueueConfigurations'] = [
            config for config in new_config.get('QueueConfigurations', [])
            if not config.get('Id', '').startswith(prefix_id_base)
        ]
        
        # Common events for all configurations
        events = [
            "s3:ObjectCreated:*",
            "s3:ObjectRemoved:*",
            "s3:ObjectRestore:*",
            "s3:ObjectTagging:*",
            "s3:ObjectAcl:Put",
        ]
        
        # Add filter if object_prefix is provided
        if object_prefix and len(object_prefix) > 0:
            # Create a separate notification configuration for each prefix
            for i, prefix in enumerate(object_prefix):
                new_queue_config = {
                    "Id": f"{prefix_id_base}_{i}",
                    "QueueArn": queue_arn,
                    "Events": events,
                    "Filter": {
                        "Key": {
                            "FilterRules": [
                                {
                                    "Name": "prefix",
                                    "Value": prefix if prefix.endswith('/') else f"{prefix}/"
                                }
                            ]
                        }
                    }
                }
                new_config['QueueConfigurations'].append(new_queue_config)
            
            logger.info(f"Created {len(object_prefix)} S3 notification configurations for different prefixes")
        else:
            # No prefix - create a configuration without filter
            new_queue_config = {
                "Id": prefix_id_base,
                "QueueArn": queue_arn,
                "Events": events
            }
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


def get_bucket_region(bucket_name):
    """Get the AWS region for a given S3 bucket."""
    try:
        response = s3_client_default_region.get_bucket_location(Bucket=bucket_name)
        region = response.get("LocationConstraint")
        # Buckets in us-east-1 return None, handle this
        return region if region is not None else "us-east-1"
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchBucket":
            logger.error(f"Bucket {bucket_name} does not exist.")
            raise ValueError(f"Bucket {bucket_name} does not exist.")
        elif e.response["Error"]["Code"] == "AccessDenied":
            logger.error(f"Access denied when trying to get location for bucket {bucket_name}. Assuming default region.")
            # Fallback or re-raise depending on requirements
            # For now, let's assume the lambda region if access denied, though this is not ideal
            return os.environ.get("AWS_REGION", "us-east-1")
        else:
            logger.error(f"Error getting bucket location for {bucket_name}: {e}")
            raise


def create_s3_bucket(bucket_name: str, region: str):
    """Creates an S3 bucket with secure defaults."""
    s3_regional_client = boto3.client("s3", region_name=region)
    try:
        logger.info(f"Attempting to create bucket '{bucket_name}' in region '{region}'")
        create_bucket_config = {}
        # us-east-1 does not require LocationConstraint
        if region != "us-east-1":
            create_bucket_config = {"CreateBucketConfiguration": {"LocationConstraint": region}}

        s3_regional_client.create_bucket(
            Bucket=bucket_name,
            **create_bucket_config,
            # ACL='private', # Default is private, explicit setting often not needed/recommended
            # ObjectLockEnabledForBucket=False # Default is false
        )
        logger.info(f"Successfully created bucket '{bucket_name}'")

        # Wait briefly for bucket to become available for policy application
        time.sleep(5)

        # Apply Block Public Access
        logger.info(f"Applying Block Public Access settings to '{bucket_name}'")
        s3_regional_client.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                'BlockPublicAcls': True,
                'IgnorePublicAcls': True,
                'BlockPublicPolicy': True,
                'RestrictPublicBuckets': True
            }
        )
        logger.info(f"Applied Block Public Access to '{bucket_name}'")

        # Apply Default Encryption (SSE-S3)
        logger.info(f"Applying default SSE-S3 encryption to '{bucket_name}'")
        s3_regional_client.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration={
                'Rules': [
                    {
                        'ApplyServerSideEncryptionByDefault': {
                            'SSEAlgorithm': 'AES256'
                        }
                    },
                ]
            }
        )
        logger.info(f"Applied default encryption to '{bucket_name}'")

        return True

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "BucketAlreadyOwnedByYou":
            logger.warning(
                f"Bucket '{bucket_name}' already exists and is owned by you. Proceeding."
            )
            # Verify region matches if possible
            try:
                existing_region = get_bucket_region(bucket_name)
                if existing_region != region:
                     logger.error(f"Existing bucket '{bucket_name}' is in region '{existing_region}', but requested region was '{region}'")
                     raise ValueError(f"Bucket exists in a different region ({existing_region}).")
                # Optionally check encryption and public access block status here
                return True # Treat as success if it exists and is owned by you in the correct region
            except Exception as check_err:
                 logger.error(f"Could not verify existing bucket '{bucket_name}' details: {check_err}")
                 raise ValueError(f"Could not verify existing bucket '{bucket_name}'.")

        elif error_code == "BucketAlreadyExists":
            logger.error(
                f"Bucket name '{bucket_name}' is already taken by another account."
            )
            raise ValueError(
                f"Bucket name '{bucket_name}' is unavailable. Please choose a different name."
            )
        else:
            logger.error(f"Failed to create or configure bucket '{bucket_name}': {e}")
            raise


@app.post("/connectors/s3")
def create_connector(createconnector: S3Connector) -> dict:
    """Creates an S3 connector, optionally creating the S3 bucket first."""
    request_body = createconnector.model_dump()
    logger.info(f"Received request to create S3 connector: {request_body}")

    connector_id = str(uuid.uuid4())
    connector_name = request_body["name"]
    connector_description = request_body.get("description", "")
    config = request_body["configuration"]
    s3_bucket = config["bucket"]
    integration_method = config["s3IntegrationMethod"]
    bucket_type = config["bucketType"]
    region = config.get("region")
    object_prefix = config.get("objectPrefix") or [] # Ensure it's a list

    created_resources = [] # Keep track of resources created for potential rollback
    # Initialize variables that might not be assigned before use in finally/except
    bucket_region = None
    queue_arn = None
    lambda_arn = None
    iam_role_arn = None
    event_source_arn = None 
    event_source_type = None

    try:
        # ---- Bucket Handling ----
        if bucket_type == "new":
            if not region:
                 # This should be caught by pydantic, but double-check
                 raise ValueError("Region is required to create a new bucket.")
            if not s3_bucket:
                # This should be caught by pydantic, but double-check
                raise ValueError("Bucket name is required to create a new bucket.")

            logger.info(f"Request to create a new bucket: {s3_bucket} in region {region}")
            # Call the create_s3_bucket function
            create_s3_bucket(s3_bucket, region)
            # Bucket creation includes secure defaults (Block Public Access, SSE-S3)
            created_resources.append(("s3_bucket", s3_bucket))
            bucket_region = region # Use the specified region
            logger.info(f"Successfully created and configured new bucket: {s3_bucket}")

        elif bucket_type == "existing":
            if not s3_bucket:
                 # This should be caught by pydantic, but double-check
                 raise ValueError("Bucket name is required for existing buckets.")
            logger.info(f"Request for existing bucket: {s3_bucket}")
            # Get region for existing bucket
            bucket_region = get_bucket_region(s3_bucket)
            logger.info(f"Determined region for existing bucket '{s3_bucket}': {bucket_region}")
            # Check if connector already exists for this bucket
            existing = check_existing_connector(s3_bucket)
            if existing:
                logger.warning(
                    f"Connector already exists for bucket {s3_bucket} with ID: {existing['id']}"
                )
                return {
                    "statusCode": 409,
                    "body": json.dumps(
                        {
                            "message": "Connector already exists for this S3 bucket",
                            "connector_id": existing["id"],
                        }
                    ),
                }
        else:
             raise ValueError(f"Invalid bucketType specified: {bucket_type}")

        # Re-initialize clients with the determined/specified region for regional operations
        logger.info(f"Initializing regional clients for region: {bucket_region}")
        s3_regional_client = boto3.client("s3", region_name=bucket_region)
        sqs_regional_client = boto3.client("sqs", region_name=bucket_region)
        lambda_regional_client = boto3.client("lambda", region_name=bucket_region)
        pipes_regional_client = boto3.client("pipes", region_name=bucket_region)

        # ---- IAM Role Creation ----
        # Define role name based on prefix, bucket, and connector ID
        base_role_name = f"{RESOURCE_PREFIX}-{s3_bucket}-{connector_id[:8]}"
        iam_role_name = (base_role_name[:63] + "R") if len(base_role_name) > 63 else base_role_name

        logger.info(f"Creating IAM role: {iam_role_name}")
        kms_key_arn = get_bucket_kms_key(s3_regional_client, s3_bucket)
        iam_role_arn = create_lambda_iam_role(iam_client, iam_role_name, kms_key_arn)
        created_resources.append(("iam_role", iam_role_name))
        logger.info(f"Successfully created IAM role: {iam_role_arn}")

        # Wait for IAM role propagation
        if not wait_for_iam_role_propagation(iam_client, iam_role_name):
            raise Exception(f"IAM role {iam_role_name} did not propagate in time.")

        # ---- Event Notification Setup ----
        if integration_method == "eventbridge":
            logger.info(f"Setting up EventBridge notifications for bucket: {s3_bucket}")
            queue_url, queue_arn = setup_eventbridge_notifications(
                s3_bucket, bucket_region, created_resources, object_prefix
            )
            logger.info(f"EventBridge setup complete. Queue URL: {queue_url}")

            # Attach policy allowing SQS read/delete to the Lambda role
            sqs_policy_document = {
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
            policy_name = f"{iam_role_name}-SQSPolicy"
            iam_client.put_role_policy(
                RoleName=iam_role_name,
                PolicyName=policy_name,
                PolicyDocument=json.dumps(sqs_policy_document),
            )
            created_resources.append(("iam_role_policy", (iam_role_name, policy_name)))
            logger.info(f"Attached SQS policy '{policy_name}' to role '{iam_role_name}'")

        elif integration_method == "s3Notifications":
            logger.info(f"Setting up S3 Event Notifications for bucket: {s3_bucket}")
            # Check for existing notifications that might conflict
            if check_existing_s3_notifications(s3_regional_client, s3_bucket):
                 logger.warning(f"Bucket {s3_bucket} already has S3 event notifications configured. Overwriting/adding is not directly supported via this method. Manual check advised.")
                 # Decide how to handle this - error out, or attempt to merge (complex)
                 # For now, let's raise an error to prevent unexpected behavior
                 raise ValueError("Bucket already has S3 event notifications. Cannot automatically configure.")

            # Create SQS queue for S3 notifications
            sanitized_bucket = ''.join(c for c in s3_bucket if c.isalnum() or c in '-_')
            max_queue_name_length = 75 # 80 - 5 (.fifo)
            base_queue_name = f"medialake-connector-{sanitized_bucket}-s3notif"
            if len(base_queue_name) > max_queue_name_length:
                base_queue_name = base_queue_name[:max_queue_name_length]
            queue_name = f"{base_queue_name}.fifo"

            logger.info(f"Creating FIFO queue for S3 Notifications: {queue_name}")
            queue_response = sqs_regional_client.create_queue(
                QueueName=queue_name,
                Attributes={
                    "VisibilityTimeout": "360",
                    "FifoQueue": "true",
                    "ContentBasedDeduplication": "true",
                    "DeduplicationScope": "queue",
                    "FifoThroughputLimit": "perQueue",
                },
            )
            queue_url = queue_response["QueueUrl"]
            queue_attributes = sqs_regional_client.get_queue_attributes(
                QueueUrl=queue_url, AttributeNames=["QueueArn"]
            )
            queue_arn = queue_attributes["Attributes"]["QueueArn"]
            created_resources.append(("sqs_queue", queue_url))
            logger.info(f"Created SQS Queue for S3 Notifications: {queue_url}")

            # Add policy to SQS queue to allow S3 to send messages
            account_id = boto3.client("sts").get_caller_identity()["Account"]
            sqs_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "s3.amazonaws.com"},
                        "Action": "sqs:SendMessage",
                        "Resource": queue_arn,
                        "Condition": {
                            "ArnLike": {"aws:SourceArn": f"arn:aws:s3:::{s3_bucket}"},
                            "StringEquals": {"aws:SourceAccount": account_id},
                        },
                    }
                ],
            }
            sqs_regional_client.set_queue_attributes(
                QueueUrl=queue_url, Attributes={"Policy": json.dumps(sqs_policy)}
            )
            created_resources.append(("queue_policy", queue_url))
            logger.info(f"Set SQS policy for queue: {queue_url}")

            # Update bucket notifications to send to the SQS queue
            update_bucket_notifications(s3_regional_client, s3_bucket, connector_id, queue_arn, object_prefix)
            created_resources.append(("s3_notification_config", s3_bucket))
            logger.info(f"Configured S3 bucket notifications for: {s3_bucket}")

            # Attach policy allowing SQS read/delete to the Lambda role (same as EventBridge)
            sqs_policy_document = {
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
            policy_name = f"{iam_role_name}-SQSPolicy"
            iam_client.put_role_policy(
                RoleName=iam_role_name,
                PolicyName=policy_name,
                PolicyDocument=json.dumps(sqs_policy_document),
            )
            created_resources.append(("iam_role_policy", (iam_role_name, policy_name)))
            logger.info(f"Attached SQS policy '{policy_name}' to role '{iam_role_name}'")

        else:
            raise ValueError(f"Unsupported integration method: {integration_method}")


        # ---- Lambda Function Deployment ----
        # Generate a unique suffix for the Lambda function name
        def generate_suffix(length=8):
            return "".join(
                random.choices(string.ascii_lowercase + string.digits, k=length)
            )

        # Define Lambda function name based on prefix, bucket, and suffix
        base_lambda_name = f"{RESOURCE_PREFIX}-s3-connector-{s3_bucket}"
        lambda_suffix = generate_suffix()
        lambda_function_name = f"{base_lambda_name[:55]}-{lambda_suffix}" # Keep under 64 chars

        logger.info(f"Creating Lambda function: {lambda_function_name}")
        lambda_env_vars = {
            "MEDIALAKE_ASSET_TABLE": MEDIALAKE_ASSET_TABLE,
            "MEDIALAKE_ASSET_TABLE_FILE_HASH_INDEX": MEDIALAKE_ASSET_TABLE_FILE_HASH_INDEX,
            "MEDIALAKE_ASSET_TABLE_ASSET_ID_INDEX": MEDIALAKE_ASSET_TABLE_ASSET_ID_INDEX,
            "MEDIALAKE_ASSET_TABLE_S3_PATH_INDEX": MEDIALAKE_ASSET_TABLE_S3_PATH_INDEX,
            "POWERTOOLS_SERVICE_NAME": "s3-connector",
            "LOG_LEVEL": "INFO",
            "INGEST_EVENT_BUS": INGEST_EVENT_BUS,
            "CONNECTOR_ID": connector_id, # Pass connector ID
            "S3_BUCKET_NAME": s3_bucket, # Pass bucket name
        }

        lambda_response = lambda_regional_client.create_function(
            FunctionName=lambda_function_name,
            Runtime="python3.11",
            Role=iam_role_arn,
            Handler="index.lambda_handler",
            Code={"S3Bucket": IAC_ASSETS_BUCKET, "S3Key": S3_CONNECTOR_LAMBDA},
            Description=f"MediaLake S3 connector function for {s3_bucket}",
            Timeout=300,
            MemorySize=256,
            Publish=True,
            Environment={"Variables": lambda_env_vars},
            Layers=[INGEST_MEDIA_PROCESSOR_LAYER],
            Architectures=["arm64"],
            Tags={RESOURCE_APPLICATION_TAG: "medialake"},
            EphemeralStorage={'Size': 1024} # Add ephemeral storage
        )
        lambda_arn = lambda_response["FunctionArn"]
        created_resources.append(("lambda_function", lambda_function_name))
        logger.info(f"Successfully created Lambda function: {lambda_arn}")

        # ---- Event Source Mapping / Pipe Creation ----
        if integration_method == "eventbridge":
             # Using Pipes for EventBridge -> Lambda
            logger.info(f"Creating EventBridge Pipe for {queue_arn} -> {lambda_arn}")
            pipe_name_prefix = f"{RESOURCE_PREFIX}-s3-connector-{s3_bucket}"
            pipe_name, pipe_arn = create_eventbridge_pipe(
                pipe_name_prefix,
                queue_arn,
                lambda_arn,
                bucket_region,
                created_resources,
            )
            logger.info(f"Created EventBridge Pipe: {pipe_arn}")
            event_source_arn = pipe_arn # Store pipe ARN as event source
            event_source_type = "Pipe"

        elif integration_method == "s3Notifications":
             # Using Lambda Event Source Mapping for SQS -> Lambda
            logger.info(f"Creating Lambda Event Source Mapping for {queue_arn} -> {lambda_arn}")
            esm_response = lambda_regional_client.create_event_source_mapping(
                EventSourceArn=queue_arn,
                FunctionName=lambda_arn,
                Enabled=True,
                BatchSize=10, # Process up to 10 messages at once
                MaximumBatchingWindowInSeconds=1, # Wait up to 1 second
                FunctionResponseTypes=['ReportBatchItemFailures'] # Enable partial batch failure reporting
            )
            esm_uuid = esm_response["UUID"]
            created_resources.append(("event_source_mapping", esm_uuid))
            logger.info(f"Created Event Source Mapping: {esm_uuid}")
            event_source_arn = queue_arn # Store queue ARN as event source
            event_source_type = "SQS"

        # ---- Store Connector in DynamoDB ----
        connector_table = dynamodb.Table(MEDIALAKE_CONNECTOR_TABLE)
        item = {
            "id": connector_id,
            "name": connector_name,
            "description": connector_description,
            "type": "s3",
            "configuration": {
                "bucket": s3_bucket,
                "region": bucket_region,
                "s3IntegrationMethod": integration_method,
                "objectPrefix": object_prefix,
                "queueArn": queue_arn,
                "lambdaArn": lambda_arn,
                "iamRoleArn": iam_role_arn,
                "eventSourceArn": event_source_arn, # Store pipe or queue arn
                "eventSourceType": event_source_type, # Store type (Pipe or SQS)
            },
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat(),
            "status": "active", # Set status
        }
        logger.info(f"Storing connector details in DynamoDB: {item}")
        connector_table.put_item(Item=item)

        logger.info(f"Successfully created connector {connector_id} for bucket {s3_bucket}")
        return {
            "statusCode": 201,
            "body": json.dumps(
                {
                    "message": "Connector created successfully",
                    "connector_id": connector_id,
                    "details": item, # Return full details
                }
            ),
        }

    except (ClientError, ValueError, Exception) as e:
        logger.error(f"Error creating connector: {traceback.format_exc()}")
        # ---- Rollback Logic ----
        logger.warning(f"Initiating rollback due to error: {e}")
        
        # Initialize cleanup clients if region was determined
        s3_cleanup_client = None
        sqs_cleanup_client = None
        lambda_cleanup_client = None
        eventbridge_cleanup = None
        pipes_cleanup_client = None
        if 'bucket_region' in locals() and bucket_region: # Check if bucket_region was set
            logger.info(f"Initializing cleanup clients for region: {bucket_region}")
            s3_cleanup_client = boto3.client("s3", region_name=bucket_region)
            sqs_cleanup_client = boto3.client("sqs", region_name=bucket_region)
            lambda_cleanup_client = boto3.client("lambda", region_name=bucket_region)
            eventbridge_cleanup = boto3.client("events", region_name=bucket_region)
            pipes_cleanup_client = boto3.client("pipes", region_name=bucket_region)
        else:
            # Use default region clients if bucket_region wasn't set (e.g., error occurred before region determination)
             logger.warning("Bucket region not determined before error, using default region clients for cleanup.")
             s3_cleanup_client = s3_client_default_region
             # Note: Other regional clients might fail if the error happened very early
             # and the required region is not the default.
             # Consider adding region info to created_resources tuples if possible.
             sqs_cleanup_client = boto3.client("sqs")
             lambda_cleanup_client = boto3.client("lambda")
             eventbridge_cleanup = boto3.client("events")
             pipes_cleanup_client = boto3.client("pipes")

        # Reverse the order of created_resources for proper cleanup
        for resource_type, resource_identifier in reversed(created_resources):
            try:
                logger.info(f"Attempting to delete {resource_type}: {resource_identifier}")
                if resource_type == "s3_bucket":
                    # Only delete if bucketType was 'new'
                    if bucket_type == 'new':
                        # Check if bucket is empty before deleting (best practice)
                        # Use the s3_cleanup_client initialized above
                        if not s3_cleanup_client:
                             logger.error("S3 cleanup client not initialized, cannot delete bucket.")
                             continue
                        # If creating a new bucket, region is known
                        s3_new_bucket_cleanup_client = boto3.client("s3", region_name=region) 
                        try:
                             # List objects - if any exist, deletion will fail unless forced/emptied
                            response = s3_new_bucket_cleanup_client.list_objects_v2(Bucket=resource_identifier, MaxKeys=1)
                            if 'Contents' in response and len(response['Contents']) > 0:
                                logger.warning(f"Bucket {resource_identifier} is not empty. Skipping deletion.")
                            else:
                                s3_new_bucket_cleanup_client.delete_bucket(Bucket=resource_identifier)
                                logger.info(f"Deleted S3 bucket: {resource_identifier}")
                        except ClientError as bucket_del_err:
                             logger.error(f"Failed to delete bucket {resource_identifier} during rollback: {bucket_del_err}")
                    else:
                        logger.info(f"Skipping deletion of existing S3 bucket: {resource_identifier}")

                elif resource_type == "iam_role":
                    role_name = resource_identifier
                    # Detach policies first
                    try:
                        attached_policies = iam_client.list_attached_role_policies(RoleName=role_name).get('AttachedPolicies', [])
                        for policy in attached_policies:
                            iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy['PolicyArn'])
                        inline_policies = iam_client.list_role_policies(RoleName=role_name).get('PolicyNames', [])
                        for policy_name in inline_policies:
                            iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
                    except ClientError as policy_err:
                         logger.error(f"Failed to detach/delete policies for role {role_name}: {policy_err}")
                    # Delete role
                    iam_client.delete_role(RoleName=role_name)
                    logger.info(f"Deleted IAM role: {role_name}")

                elif resource_type == "iam_role_policy":
                     # Policy deletion handled by role deletion
                     pass

                elif resource_type == "eventbridge_config":
                    bucket_name = resource_identifier
                    # Use the s3_cleanup_client initialized above
                    if not s3_cleanup_client:
                        logger.error("S3 cleanup client not initialized, cannot remove EventBridge config.")
                        continue
                    try:
                        config = s3_cleanup_client.get_bucket_notification_configuration(Bucket=bucket_name)
                        config.pop('ResponseMetadata', None)
                        config.pop('EventBridgeConfiguration', None) # Remove EB config
                        if not any(config.values()): # If no other configs exist, delete
                            s3_cleanup_client.delete_bucket_notification(Bucket=bucket_name)
                        else: # Otherwise, put back config without EB
                            s3_cleanup_client.put_bucket_notification_configuration(Bucket=bucket_name, NotificationConfiguration=config)
                        logger.info(f"Removed EventBridge config from bucket: {bucket_name}")
                    except ClientError as eb_config_err:
                         logger.error(f"Failed to remove EventBridge config from {bucket_name}: {eb_config_err}")

                elif resource_type == "sqs_queue":
                    queue_url = resource_identifier
                    # Use the sqs_cleanup_client initialized above
                    if not sqs_cleanup_client:
                        logger.error("SQS cleanup client not initialized, cannot delete queue.")
                        continue
                    sqs_cleanup_client.delete_queue(QueueUrl=queue_url)
                    logger.info(f"Deleted SQS queue: {queue_url}")

                elif resource_type == "eventbridge_rule":
                    rule_name = resource_identifier
                    # Use the eventbridge_cleanup client initialized above
                    if not eventbridge_cleanup:
                         logger.error("EventBridge cleanup client not initialized, cannot delete rule.")
                         continue
                    # Remove targets first
                    targets = eventbridge_cleanup.list_targets_by_rule(Rule=rule_name).get('Targets', [])
                    if targets:
                        eventbridge_cleanup.remove_targets(Rule=rule_name, Ids=[t['Id'] for t in targets])
                    eventbridge_cleanup.delete_rule(Name=rule_name)
                    logger.info(f"Deleted EventBridge rule: {rule_name}")

                # queue_policy is attached to SQS, deleted with queue
                # eventbridge_target deleted with rule

                elif resource_type == "s3_notification_config":
                    bucket_name = resource_identifier
                    # Use the s3_cleanup_client initialized above
                    if not s3_cleanup_client:
                        logger.error("S3 cleanup client not initialized, cannot handle S3 notification config.")
                        continue
                    # Attempt to remove the specific configuration added by this connector
                    # This is complex if other configs exist. Simple deletion might be too aggressive.
                    logger.warning(f"Rollback: Manual removal of S3 notification config for connector on bucket {bucket_name} might be needed.")
                    # try:
                    #     s3_cleanup_client.delete_bucket_notification(Bucket=bucket_name) # This deletes ALL notifications
                    #     logger.info(f"Deleted S3 notification config for bucket: {bucket_name}")
                    # except ClientError as s3_notif_err:
                    #     logger.error(f"Failed to delete S3 notification config for {bucket_name}: {s3_notif_err}")

                elif resource_type == "lambda_function":
                    function_name = resource_identifier
                    # Use the lambda_cleanup_client initialized above
                    if not lambda_cleanup_client:
                         logger.error("Lambda cleanup client not initialized, cannot delete function.")
                         continue
                    lambda_cleanup_client.delete_function(FunctionName=function_name)
                    logger.info(f"Deleted Lambda function: {function_name}")

                elif resource_type == "event_source_mapping":
                    esm_uuid = resource_identifier
                    # Use the lambda_cleanup_client initialized above
                    if not lambda_cleanup_client:
                         logger.error("Lambda cleanup client not initialized, cannot delete ESM.")
                         continue
                    lambda_cleanup_client.delete_event_source_mapping(UUID=esm_uuid)
                    logger.info(f"Deleted Event Source Mapping: {esm_uuid}")

                elif resource_type == "pipe":
                    pipe_name = resource_identifier
                    # Use the pipes_cleanup_client initialized above
                    if not pipes_cleanup_client:
                         logger.error("Pipes cleanup client not initialized, cannot delete pipe.")
                         continue
                    # Stop pipe first if running
                    try:
                        pipe_info = pipes_cleanup_client.describe_pipe(Name=pipe_name)
                        if pipe_info.get('CurrentState') == 'RUNNING':
                            pipes_cleanup_client.stop_pipe(Name=pipe_name)
                            time.sleep(5) # Allow time to stop
                    except ClientError as desc_err:
                        logger.warning(f"Could not describe pipe {pipe_name} before deletion: {desc_err}")
                    pipes_cleanup_client.delete_pipe(Name=pipe_name)
                    logger.info(f"Deleted Pipe: {pipe_name}")

            except ClientError as rollback_err:
                logger.error(
                    f"Failed to delete {resource_type} {resource_identifier} during rollback: {rollback_err}"
                )
        # End Rollback Loop

        # Return error response
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "message": f"Failed to create connector: {str(e)}",
                    "error": traceback.format_exc()
                 }
            ),
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler function"""
    # logger.info(f"Received event: {json.dumps(event)}")
    return app.resolve(event, context)
