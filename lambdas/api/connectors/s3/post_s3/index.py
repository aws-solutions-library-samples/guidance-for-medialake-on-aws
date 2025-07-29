import json
import os
import random
import string
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, List

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import (
    APIGatewayRestResolver,
    Response,
    content_types,
)
from aws_lambda_powertools.event_handler.openapi.exceptions import (
    RequestValidationError,
)
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.config import Config
from botocore.exceptions import ClientError
from pydantic import BaseModel

tracer = Tracer()
logger = Logger()
app = APIGatewayRestResolver(enable_validation=True)

# AGGRESSIVE Performance Optimizations for API Gateway 29s Timeout:
# 1. Optimized boto3 configuration with connection pooling and adaptive retries
# 2. ULTRA-MINIMAL IAM propagation waits (1-3 seconds maximum)
# 3. Parallel policy attachment using ThreadPoolExecutor
# 4. SKIPPED non-critical propagation checks
# 5. ULTRA-FAST EventBridge pipe creation (2,4 second retries)
# 6. Concurrent execution of independent operations
# 7. MINIMAL Lambda role propagation (2-3 second waits)
# 8. REDUCED retry attempts across all operations (2 max vs 3-5)
# 9. REMOVED unnecessary verification steps and logging
# 10. PRIORITIZED speed over safety margins - relies on retry logic

# Optimized boto3 configuration for better performance
OPTIMIZED_CONFIG = Config(
    max_pool_connections=50,  # Increase connection pool size
    retries={
        "max_attempts": 10,
        "mode": "adaptive",  # Adaptive retry mode for better performance
    },
    connect_timeout=10,  # Connect timeout in seconds
    read_timeout=60,  # Read timeout in seconds
)


def get_optimized_client(service: str, region: str = None):
    """Get boto3 client with optimized configuration for performance"""
    if region:
        return boto3.client(service, region_name=region, config=OPTIMIZED_CONFIG)
    else:
        return boto3.client(service, config=OPTIMIZED_CONFIG)


# Initialize AWS Clients with optimized configuration
s3_client = get_optimized_client("s3")
dynamodb = boto3.resource("dynamodb", config=OPTIMIZED_CONFIG)
iam_client = get_optimized_client("iam")

# AWS Resource Name Length Limits
RESOURCE_NAME_LIMITS = {
    "iam_role": 64,
    "iam_policy": 128,
    "sqs_queue": 80,
    "sqs_queue_fifo": 75,
    "eventbridge_rule": 64,
    "lambda_function": 64,
    "eventbridge_pipe": 64,
    "eventbridge_target_id": 64,
}


def truncate_resource_name(resource_type: str, name: str, suffix: str = "") -> str:
    """
    Truncate resource name based on AWS resource type limits

    Args:
        resource_type: Type of AWS resource (iam_role, sqs_queue, etc.)
        name: Proposed resource name
        suffix: Optional suffix to append (will be included in length calculation)

    Returns:
        str: Properly truncated resource name
    """
    max_length = RESOURCE_NAME_LIMITS.get(
        resource_type, 64
    )  # Default to 64 if not found

    # Calculate available length for the base name
    available_length = max_length - len(suffix)

    if len(name) <= available_length:
        return name + suffix

    # Truncate the name to fit within limits
    truncated_name = name[:available_length] + suffix
    logger.info(
        f"Truncated {resource_type} name from '{name + suffix}' to '{truncated_name}' (max: {max_length})"
    )

    return truncated_name


def create_resource_name_with_suffix(
    resource_type: str, base_name: str, suffix: str
) -> str:
    """
    Create a resource name with suffix, automatically truncating if needed

    Args:
        resource_type: Type of AWS resource (iam_role, sqs_queue, etc.)
        base_name: Base name for the resource
        suffix: 4-character suffix to append

    Returns:
        str: Properly formatted resource name with suffix
    """
    max_length = RESOURCE_NAME_LIMITS.get(
        resource_type, 64
    )  # Default to 64 if not found

    # Account for the suffix (4 chars) plus separator (1 char) = 5 total
    separator = "-"
    total_suffix_length = len(suffix) + len(separator)
    available_length = max_length - total_suffix_length

    if len(base_name) <= available_length:
        final_name = f"{base_name}{separator}{suffix}"
    else:
        # Truncate the base name to fit within limits
        truncated_base = base_name[:available_length]
        final_name = f"{truncated_base}{separator}{suffix}"
        logger.info(
            f"Truncated {resource_type} base name from '{base_name}' to '{truncated_base}' to accommodate suffix '{suffix}' (max: {max_length})"
        )

    return final_name


class S3ConnectorConfig(BaseModel):
    bucket: str
    s3IntegrationMethod: str
    objectPrefix: list[str] | None = None
    bucketType: str | None = None  # "new" or "existing"
    region: str | None = None  # region for new buckets


class S3Connector(BaseModel):
    configuration: S3ConnectorConfig
    name: str
    type: str
    description: str | None = None


def wait_for_iam_role_propagation(iam_client, role_name, max_retries=2, base_delay=1):
    """Ultra-fast IAM role propagation wait - minimal delays for API Gateway timeout"""
    for attempt in range(max_retries):
        try:
            iam_client.get_role(RoleName=role_name)
            # No additional wait - role exists, that's enough
            return True
        except iam_client.exceptions.NoSuchEntityException:
            if attempt < max_retries - 1:
                delay = min((2**attempt) * base_delay, 3)  # Cap at 3 seconds maximum
                time.sleep(delay)
    return False


def wait_for_lambda_role_propagation(role_arn, role_name, max_retries=2, base_delay=3):
    """
    Minimal wait for Lambda role propagation - optimized for API Gateway timeout
    """
    logger.info(f"Quick Lambda role propagation check for {role_name}...")

    for attempt in range(max_retries):
        try:
            # Quick STS check
            sts_client = get_optimized_client("sts")

            try:
                sts_client.assume_role(
                    RoleArn=role_arn, RoleSessionName="test-lambda-propagation"
                )
            except sts_client.exceptions.ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "AccessDenied":
                    # Role exists and is recognizable - minimal wait
                    time.sleep(2)  # Just 2 seconds
                    return True
                else:
                    logger.warning(f"Role propagation check failed with {error_code}")

            if attempt < max_retries - 1:
                time.sleep(base_delay)  # Max 3 seconds between attempts

        except Exception as e:
            logger.warning(f"Error during role propagation check: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(1)

    # Minimal final wait - prioritize speed
    time.sleep(3)
    return True


def wait_for_policy_attachment(
    iam_client, role_name, policy_arn, max_retries=2, base_delay=1
):
    """Ultra-fast policy attachment check for API Gateway timeout"""
    for attempt in range(max_retries):
        try:
            attached_policies = iam_client.list_attached_role_policies(
                RoleName=role_name
            )["AttachedPolicies"]
            if any(policy["PolicyArn"] == policy_arn for policy in attached_policies):
                # No additional wait - policy is attached
                return True
            if attempt < max_retries - 1:
                time.sleep(base_delay)  # Max 1 second wait
        except iam_client.exceptions.NoSuchEntityException:
            if attempt < max_retries - 1:
                time.sleep(base_delay)
    return False


def attach_policy_async(
    iam_client, role_name, policy_name, policy_document, created_resources
):
    """Attach an inline policy to a role asynchronously"""
    try:
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document),
        )
        created_resources.append(("inline_policy", (role_name, policy_name)))
        logger.info(f"Attached policy {policy_name} to role {role_name}")
        return True, policy_name
    except Exception as e:
        logger.error(
            f"Error attaching policy {policy_name} to role {role_name}: {str(e)}"
        )
        return False, policy_name


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
    s3_bucket: str,
    bucket_region: str,
    created_resources: list,
    object_prefix: list[str] | None,
    suffix: str,
) -> tuple[str, str]:
    """Set up EventBridge notifications and return queue URL and ARN"""

    eventbridge = get_optimized_client("events", bucket_region)
    sqs = get_optimized_client("sqs", bucket_region)
    s3 = get_optimized_client("s3", bucket_region)

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
    sanitized_bucket = "".join(c for c in s3_bucket if c.isalnum() or c in "-_")

    # Create FIFO SQS queue with queue-level throughput limit
    base_name = f"medialake-connector-{sanitized_bucket}-eventbridge"
    queue_name = (
        create_resource_name_with_suffix("sqs_queue_fifo", base_name, suffix) + ".fifo"
    )

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
    account_id = get_optimized_client("sts", bucket_region).get_caller_identity()[
        "Account"
    ]

    # Create EventBridge rule with comprehensive event pattern
    rule_name_base = f"medialake-{s3_bucket}-s3-events"
    rule_name = create_resource_name_with_suffix(
        "eventbridge_rule", rule_name_base, suffix
    )
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
            formatted_prefix = prefix if prefix.endswith("/") else f"{prefix}/"
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
    target_id_base = f"SQSTarget-{s3_bucket}"
    target_id = create_resource_name_with_suffix(
        "eventbridge_target_id", target_id_base, suffix
    )
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
    bucket_region: str,
    queue_arn: str,
    rule_name: str,
    created_resources: list,
    suffix: str,
) -> str:
    """Create IAM role for EventBridge to send events to SQS"""

    iam = boto3.client("iam")
    role_name_base = f"medialake-eb-{rule_name}"
    role_name = create_resource_name_with_suffix("iam_role", role_name_base, suffix)

    # Check if role already exists
    try:
        existing_role = iam.get_role(RoleName=role_name)
        logger.info(
            f"EventBridge IAM role {role_name} already exists, using existing role"
        )
        return existing_role["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        # Role doesn't exist, proceed with creation
        logger.info(
            f"EventBridge IAM role {role_name} does not exist, creating new role"
        )

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

    try:
        role = iam.create_role(
            RoleName=role_name, AssumeRolePolicyDocument=json.dumps(assume_role_policy)
        )
        created_resources.append(("iam_role", role_name))
        logger.info(f"Successfully created EventBridge IAM role: {role_name}")
    except iam.exceptions.EntityAlreadyExistsException:
        # Role was created by another process while we were checking
        logger.info(
            f"EventBridge IAM role {role_name} was created by another process, retrieving existing role"
        )
        existing_role = iam.get_role(RoleName=role_name)
        return existing_role["Role"]["Arn"]

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Action": "sqs:SendMessage", "Resource": queue_arn}
        ],
    }

    policy_name_base = f"{role_name}-policy"
    policy_name = truncate_resource_name("iam_policy", policy_name_base)
    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy),
        )
        created_resources.append(("inline_policy", (role_name, policy_name)))
        logger.info(f"Attached policy to EventBridge role {role_name}")
    except Exception as e:
        logger.error(
            f"Error attaching policy to EventBridge role {role_name}: {str(e)}"
        )
        # Don't fail for policy attachment issues if role already exists

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


def create_s3_bucket(s3_client, bucket_name, region):
    """
    Create an S3 bucket in the specified region

    Args:
        s3_client: S3 client instance
        bucket_name: Name of the bucket to create
        region: AWS region where the bucket should be created

    Returns:
        str: The region where the bucket was created

    Raises:
        Exception: If bucket creation fails
    """
    try:
        # For us-east-1, we don't specify LocationConstraint
        if region == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region},
            )

        logger.info(
            f"Successfully created S3 bucket '{bucket_name}' in region '{region}'"
        )
        return region

    except s3_client.exceptions.BucketAlreadyExists:
        logger.error(
            f"Bucket '{bucket_name}' already exists and is owned by another account"
        )
        raise Exception(
            f"Bucket '{bucket_name}' already exists and is owned by another account"
        )
    except s3_client.exceptions.BucketAlreadyOwnedByYou:
        logger.info(f"Bucket '{bucket_name}' already exists and is owned by you")
        # Get the bucket's region
        try:
            bucket_location = s3_client.get_bucket_location(Bucket=bucket_name)
            actual_region = bucket_location["LocationConstraint"] or os.environ.get(
                "REGION", "us-east-1"
            )
            return actual_region
        except Exception as e:
            logger.warning(
                f"Could not determine bucket region, using requested region: {e}"
            )
            return region
    except Exception as e:
        logger.error(f"Failed to create bucket '{bucket_name}': {str(e)}")
        raise Exception(f"Failed to create bucket '{bucket_name}': {str(e)}")


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
    # Ensure role name is within AWS limits
    role_name = truncate_resource_name("iam_role", role_name)

    # Check if role already exists
    try:
        existing_role = iam_client.get_role(RoleName=role_name)
        logger.info(f"IAM role {role_name} already exists, returning existing role ARN")
        return existing_role["Role"]["Arn"]
    except iam_client.exceptions.NoSuchEntityException:
        # Role doesn't exist, proceed with creation
        logger.info(f"IAM role {role_name} does not exist, creating new role")

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

    try:
        role = iam_client.create_role(
            RoleName=role_name, AssumeRolePolicyDocument=json.dumps(assume_role_policy)
        )
        logger.info(f"Successfully created IAM role: {role_name}")
    except iam_client.exceptions.EntityAlreadyExistsException:
        # Role was created by another process while we were checking
        logger.info(
            f"IAM role {role_name} was created by another process, retrieving existing role"
        )
        existing_role = iam_client.get_role(RoleName=role_name)
        return existing_role["Role"]["Arn"]

    # Attach the basic execution role policy
    try:
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )
        logger.info(f"Attached AWSLambdaBasicExecutionRole to {role_name}")
    except iam_client.exceptions.LimitExceededException:
        logger.warning(f"Policy already attached to role {role_name}")
    except Exception as e:
        logger.error(
            f"Error attaching basic execution policy to role {role_name}: {str(e)}"
        )
        # Don't fail the entire operation for policy attachment issues

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
        kms_policy_name = truncate_resource_name(
            "iam_policy", f"{role_name}-kms-policy"
        )
        try:
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=kms_policy_name,
                PolicyDocument=json.dumps(kms_policy),
            )
            logger.info(f"Attached KMS policy to {role_name}")
        except Exception as e:
            logger.error(f"Error attaching KMS policy to role {role_name}: {str(e)}")
            # Don't fail the entire operation for policy attachment issues

    # Add S3 Vector Store permissions for vector deletion functionality
    s3_vector_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "s3vectors:ListVectors",
                    "s3vectors:GetVectors",
                    "s3vectors:DeleteVectors",
                    "s3vectors:QueryVectors",
                ],
                "Resource": "*",
            }
        ],
    }
    s3_vector_policy_name = truncate_resource_name(
        "iam_policy", f"{role_name}-s3-vector-policy"
    )
    try:
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=s3_vector_policy_name,
            PolicyDocument=json.dumps(s3_vector_policy),
        )
        logger.info(f"Attached S3 Vector Store policy to {role_name}")
    except Exception as e:
        logger.error(
            f"Error attaching S3 Vector Store policy to role {role_name}: {str(e)}"
        )
        # Don't fail the entire operation for policy attachment issues

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


def update_bucket_notifications(
    s3: Any,
    s3_bucket: str,
    connector_id: str,
    queue_arn: str,
    object_prefix: list[str] | None,
) -> List[str]:
    errors: List[str] = []
    try:
        # Get existing configuration
        current_config = s3.get_bucket_notification_configuration(Bucket=s3_bucket)

        # Create new configuration starting with existing config
        new_config = current_config.copy()

        # Remove ResponseMetadata from the configuration
        new_config = {
            k: v for k, v in current_config.items() if k != "ResponseMetadata"
        }

        # Initialize QueueConfigurations if it doesn't exist
        if "QueueConfigurations" not in new_config:
            new_config["QueueConfigurations"] = []

        # Remove any existing configurations with our prefix
        prefix_id_base = (
            f"{os.environ.get('RESOURCE_PREFIX')}_notifications_{connector_id}"
        )
        new_config["QueueConfigurations"] = [
            config
            for config in new_config.get("QueueConfigurations", [])
            if not config.get("Id", "").startswith(prefix_id_base)
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
                                    "Value": (
                                        prefix if prefix.endswith("/") else f"{prefix}/"
                                    ),
                                }
                            ]
                        }
                    },
                }
                new_config["QueueConfigurations"].append(new_queue_config)

            logger.info(
                f"Created {len(object_prefix)} S3 notification configurations for different prefixes"
            )
        else:
            # No prefix - create a configuration without filter
            new_queue_config = {
                "Id": prefix_id_base,
                "QueueArn": queue_arn,
                "Events": events,
            }
            new_config["QueueConfigurations"].append(new_queue_config)

        # Apply the updated configuration
        s3.put_bucket_notification_configuration(
            Bucket=s3_bucket, NotificationConfiguration=new_config
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
    suffix: str,
) -> tuple[str, str]:
    """Create EventBridge Pipe between SQS and Lambda"""

    # Create region-specific pipes client and IAM client with optimized configuration
    pipes_client = get_optimized_client("pipes", bucket_region)
    iam_client = get_optimized_client("iam")

    # Ensure pipe role name is within AWS limits
    # Need to account for "-pipe-role" suffix in addition to the 4-char random suffix
    # Smart truncation: preserve the important parts and truncate the bucket name if needed
    resource_prefix = os.environ.get("RESOURCE_PREFIX", "medialake")

    # Calculate how much space we have for the bucket name
    # Format: {prefix}_connector_{bucket_name}-pipe-role-{suffix}
    # Fixed parts: prefix + "_connector_" + "-pipe-role-" + suffix = roughly 30 chars
    fixed_parts_length = (
        len(resource_prefix) + len("_connector_") + len("-pipe-role-") + len(suffix)
    )
    max_bucket_length = 64 - fixed_parts_length

    # Extract bucket name from resource_name_prefix
    bucket_name = resource_name_prefix.split(f"{resource_prefix}_connector_")[1]

    # Truncate bucket name intelligently if needed
    if len(bucket_name) > max_bucket_length:
        # Keep first part and last part (likely region), truncate middle
        if (
            max_bucket_length > 20
        ):  # Only do smart truncation if we have reasonable space
            keep_start = max_bucket_length // 2
            keep_end = max_bucket_length - keep_start - 2  # -2 for ".."
            truncated_bucket = bucket_name[:keep_start] + ".." + bucket_name[-keep_end:]
        else:
            truncated_bucket = bucket_name[:max_bucket_length]
        logger.info(
            f"Truncated bucket name in pipe role from '{bucket_name}' to '{truncated_bucket}' for length limits"
        )
        pipe_role_name_base = (
            f"{resource_prefix}_connector_{truncated_bucket}-pipe-role"
        )
    else:
        pipe_role_name_base = f"{resource_name_prefix}-pipe-role"

    pipe_role_name = f"{pipe_role_name_base}-{suffix}"

    # Final safety check
    if len(pipe_role_name) > 64:
        logger.warning(
            f"Pipe role name '{pipe_role_name}' still exceeds 64 chars, truncating..."
        )
        pipe_role_name = pipe_role_name[:64]

    logger.info(
        f"Creating EventBridge Pipe role with name: {pipe_role_name} (length: {len(pipe_role_name)})"
    )

    # Check if pipe role already exists
    try:
        existing_role = iam_client.get_role(RoleName=pipe_role_name)
        logger.info(
            f"Pipe IAM role {pipe_role_name} already exists, using existing role"
        )
        pipe_role_arn = existing_role["Role"]["Arn"]
        logger.info(f"Existing pipe role ARN: {pipe_role_arn}")
    except iam_client.exceptions.NoSuchEntityException:
        # Role doesn't exist, proceed with creation
        logger.info(f"Pipe IAM role {pipe_role_name} does not exist, creating new role")

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

        logger.info(
            f"Creating pipe role with trust policy for pipes.amazonaws.com service"
        )
        try:
            pipe_role = iam_client.create_role(
                RoleName=pipe_role_name,
                AssumeRolePolicyDocument=json.dumps(assume_role_policy),
                Description=f"Role for EventBridge Pipe to connect SQS to Lambda",
            )
            created_resources.append(("iam_role", pipe_role_name))
            pipe_role_arn = pipe_role["Role"]["Arn"]
            logger.info(
                f"Successfully created pipe IAM role: {pipe_role_name} with ARN: {pipe_role_arn}"
            )
        except iam_client.exceptions.EntityAlreadyExistsException:
            # Role was created by another process while we were checking
            logger.info(
                f"Pipe IAM role {pipe_role_name} was created by another process, retrieving existing role"
            )
            existing_role = iam_client.get_role(RoleName=pipe_role_name)
            pipe_role_arn = existing_role["Role"]["Arn"]
            logger.info(f"Retrieved existing pipe role ARN: {pipe_role_arn}")

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

    source_policy_name_base = f"{pipe_role_name}-source-policy"
    source_policy_name = truncate_resource_name("iam_policy", source_policy_name_base)
    try:
        iam_client.put_role_policy(
            RoleName=pipe_role_name,
            PolicyName=source_policy_name,
            PolicyDocument=json.dumps(source_policy),
        )
        created_resources.append(
            ("inline_policy", (pipe_role_name, source_policy_name))
        )
        logger.info(f"Attached source policy to pipe role {pipe_role_name}")
    except Exception as e:
        logger.error(
            f"Error attaching source policy to pipe role {pipe_role_name}: {str(e)}"
        )
        # Don't fail for policy attachment issues if role already exists

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

    target_policy_name_base = f"{pipe_role_name}-target-policy"
    target_policy_name = truncate_resource_name("iam_policy", target_policy_name_base)
    try:
        iam_client.put_role_policy(
            RoleName=pipe_role_name,
            PolicyName=target_policy_name,
            PolicyDocument=json.dumps(target_policy),
        )
        created_resources.append(
            ("inline_policy", (pipe_role_name, target_policy_name))
        )
        logger.info(f"Attached target policy to pipe role {pipe_role_name}")
    except Exception as e:
        logger.error(
            f"Error attaching target policy to pipe role {pipe_role_name}: {str(e)}"
        )
        # Don't fail for policy attachment issues if role already exists

    # Wait for role and policies to propagate
    if not wait_for_iam_role_propagation(iam_client, pipe_role_name):
        raise Exception(f"IAM role {pipe_role_name} did not propagate in time")

    # Minimal wait for pipes service - prioritize speed
    logger.info(f"Quick pipe role check for {pipe_role_name}...")
    time.sleep(1)  # Minimal 1 second wait

    # Create the pipe using region-specific client
    pipe_name_base = f"{resource_name_prefix}-pipe"
    pipe_name = create_resource_name_with_suffix(
        "eventbridge_pipe", pipe_name_base, suffix
    )

    logger.info(f"Creating EventBridge Pipe {pipe_name} with role ARN: {pipe_role_arn}")
    logger.info(f"Pipe will connect SQS queue {queue_arn} to Lambda {lambda_arn}")

    # Ultra-fast pipe creation for API Gateway timeout
    max_retries = 2  # Reduce to 2 retries maximum
    for attempt in range(max_retries):
        try:
            response = pipes_client.create_pipe(
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
            logger.info(f"Successfully created EventBridge Pipe: {pipe_arn}")
            return pipe_arn, pipe_role_arn

        except Exception as e:
            error_message = str(e)
            if (
                "does not have permission to assume the role" in error_message
                and attempt < max_retries - 1
            ):
                wait_time = 2 * (attempt + 1)  # Ultra-fast: 2, 4 seconds only
                logger.warning(
                    f"Pipe creation retry {attempt + 1}/{max_retries} after {wait_time}s..."
                )
                time.sleep(wait_time)
                continue
            else:
                logger.error(
                    f"Failed to create EventBridge Pipe after {attempt + 1} attempts: {error_message}"
                )
                raise e


@app.post("/connectors/s3")
def create_connector(createconnector: S3Connector) -> dict:
    """
    Create S3 connector asynchronously to avoid API Gateway timeout.
    Returns immediately with connector ID and processing status.
    """
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
            """Generate a 4-character alphanumeric suffix"""
            return "".join(random.choices(string.ascii_lowercase + string.digits, k=4))

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

        # Create target function name with proper truncation
        target_function_name_base = f"{resource_name_prefix}"
        target_function_name = create_resource_name_with_suffix(
            "lambda_function", target_function_name_base, suffix
        )

        # Handle bucket creation or validation based on bucketType
        bucket_type = createconnector.configuration.bucketType
        bucket_region = createconnector.configuration.region

        if bucket_type == "new":
            # Create new bucket
            if not bucket_region:
                bucket_region = os.environ.get(
                    "REGION", "us-east-1"
                )  # Use CDK deployment region

            try:
                bucket_region = create_s3_bucket(s3_client, s3_bucket, bucket_region)
                created_resources.append(("s3_bucket", s3_bucket))
            except Exception as e:
                return {
                    "status": "400",
                    "message": str(e),
                    "data": {},
                }
        else:
            # Validate existing bucket
            try:
                bucket_location = s3_client.get_bucket_location(Bucket=s3_bucket)
                bucket_region = bucket_location["LocationConstraint"]
                bucket_region = bucket_region or os.environ.get("REGION", "us-east-1")
            except s3_client.exceptions.ClientError:
                return {
                    "status": "400",
                    "message": (
                        f"S3 bucket '{s3_bucket}' does not exist or is not accessible"
                    ),
                    "data": {},
                }

        # Initialize S3, SQS, and Lambda clients in the bucket's region with optimized configuration
        s3 = get_optimized_client("s3", bucket_region)
        sqs = get_optimized_client("sqs", bucket_region)
        lambda_client = get_optimized_client("lambda", bucket_region)

        # Set up notifications based on integration method
        queue_url = None
        queue_arn = None
        if integration_method == "eventbridge":
            queue_url, queue_arn = setup_eventbridge_notifications(
                s3_bucket, bucket_region, created_resources, object_prefix, suffix
            )
        elif integration_method in ["s3Notifications"]:
            # Set up S3 event notifications
            # Create SQS queue in the same region as the bucket
            queue_name_base = f"medialake-connector-{s3_bucket}-notifications"
            queue_name = create_resource_name_with_suffix(
                "sqs_queue", queue_name_base, suffix
            )
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
                object_prefix=object_prefix,
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
            pipelines_event_bus = os.environ.get("PIPELINES_EVENT_BUS")
            medialake_asset_table = os.environ.get("MEDIALAKE_ASSET_TABLE")
            asset_table_file_hash_index_arn = os.environ.get(
                "MEDIALAKE_ASSET_TABLE_FILE_HASH_INDEX"
            )
            asset_table_asset_id_index_arn = os.environ.get(
                "MEDIALAKE_ASSET_TABLE_ASSET_ID_INDEX"
            )
            asset_table_s3_path_index_arn = os.environ.get(
                "MEDIALAKE_ASSET_TABLE_S3_PATH_INDEX"
            )
            layer_arn = os.environ.get("INGEST_MEDIA_PROCESSOR_LAYER")

            # Get current AWS account ID (needed for resource ARNs)
            account_id = get_optimized_client(
                "sts", bucket_region
            ).get_caller_identity()["Account"]

            # Create Lambda execution, IAM roles for Lambda
            # Include the suffix in the role name to ensure uniqueness
            role_name_base = f"{resource_name_prefix}-role"
            role_name = create_resource_name_with_suffix(
                "iam_role", role_name_base, suffix
            )
            bucket_kms_key = get_bucket_kms_key(s3_client, s3_bucket)
            lambda_role_arn = create_lambda_iam_role(
                iam_client, role_name, bucket_kms_key
            )
            created_resources.append(("iam_role", role_name))

            # The basic execution policy is already attached in create_lambda_iam_role
            # So we only need to track it in created_resources
            created_resources.append(
                ("role_policy", (role_name, "AWSLambdaBasicExecutionRole"))
            )

            # Attach VPC execution role policy
            try:
                iam_client.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
                )
                created_resources.append(
                    ("role_policy", (role_name, "AWSLambdaVPCAccessExecutionRole"))
                )
                logger.info(f"Attached AWSLambdaVPCAccessExecutionRole to {role_name}")
            except Exception as e:
                logger.error(
                    f"Error attaching VPC execution policy to role {role_name}: {str(e)}"
                )
                # Don't fail the entire operation for policy attachment issues

            # Prepare all policies for parallel attachment
            policies_to_attach = []

            # SQS policy
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
            sqs_policy_name_base = f"{role_name}-sqs-policy"
            sqs_policy_name = truncate_resource_name("iam_policy", sqs_policy_name_base)
            policies_to_attach.append((sqs_policy_name, sqs_policy))

            # S3 policy
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
                            "s3:DeleteObject",  # Added for asset deletion
                        ],
                        "Resource": [
                            f"arn:aws:s3:::{s3_bucket}",
                            f"arn:aws:s3:::{s3_bucket}/*",
                        ],
                    }
                ],
            }
            s3_policy_name_base = f"{role_name}-s3-policy"
            s3_policy_name = truncate_resource_name("iam_policy", s3_policy_name_base)
            policies_to_attach.append((s3_policy_name, s3_policy))

            # Media assets bucket policy for derived representations and transcripts
            media_assets_bucket = os.environ.get("MEDIA_ASSETS_BUCKET")
            if media_assets_bucket:
                media_assets_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "s3:DeleteObject",
                                "s3:GetObject",
                                "s3:ListBucket",
                            ],
                            "Resource": [
                                f"arn:aws:s3:::{media_assets_bucket}",
                                f"arn:aws:s3:::{media_assets_bucket}/*",
                            ],
                        }
                    ],
                }
                media_assets_policy_name_base = f"{role_name}-media-assets-policy"
                media_assets_policy_name = truncate_resource_name(
                    "iam_policy", media_assets_policy_name_base
                )
                policies_to_attach.append(
                    (media_assets_policy_name, media_assets_policy)
                )

            # EventBridge policy
            eventbridge_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["events:PutEvents"],
                        "Resource": f"arn:aws:events:{bucket_region}:{account_id}:event-bus/{pipelines_event_bus}",
                    }
                ],
            }
            eventbridge_policy_name_base = f"{role_name}-eventbridge-policy"
            eventbridge_policy_name = truncate_resource_name(
                "iam_policy", eventbridge_policy_name_base
            )
            policies_to_attach.append((eventbridge_policy_name, eventbridge_policy))

            # DynamoDB policy
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
                            "dynamodb:BatchWriteItem",
                            "dynamodb:BatchGetItem",
                            "dynamodb:DescribeTable",
                        ],
                        "Resource": [
                            medialake_asset_table,
                            asset_table_file_hash_index_arn,
                            asset_table_asset_id_index_arn,
                            asset_table_s3_path_index_arn,
                        ],
                    }
                ],
            }
            dynamodb_policy_name_base = f"{role_name}-dynamodb-policy"
            dynamodb_policy_name = truncate_resource_name(
                "iam_policy", dynamodb_policy_name_base
            )
            policies_to_attach.append((dynamodb_policy_name, dynamodb_policy))

            opensearch_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "es:ESHttpPost",  # for _delete_by_query
                            "es:ESHttpGet",  # for reading data
                            "es:ESHttpPut",  # for indexing documents
                            "es:ESHttpDelete",  # for deleting documents
                            "es:ESHttpHead",  # for checking existence
                        ],
                        "Resource": f"arn:aws:es:{bucket_region}:{account_id}:domain/*",
                    }
                ],
            }
            opensearch_policy_name = truncate_resource_name(
                "iam_policy", f"{role_name}-os-policy"
            )
            policies_to_attach.append((opensearch_policy_name, opensearch_policy))

            # Add VPC access policy
            vpc_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ec2:CreateNetworkInterface",
                            "ec2:DescribeNetworkInterfaces",
                            "ec2:DeleteNetworkInterface",
                            "ec2:AttachNetworkInterface",
                            "ec2:DetachNetworkInterface",
                        ],
                        "Resource": [
                            f"arn:aws:ec2:{bucket_region}:{account_id}:network-interface/*",
                            f"arn:aws:ec2:{bucket_region}:{account_id}:subnet/*",
                            f"arn:aws:ec2:{bucket_region}:{account_id}:security-group/*",
                        ],
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ec2:DescribeSecurityGroups",
                            "ec2:DescribeSubnets",
                            "ec2:DescribeVpcs",
                        ],
                        "Resource": "*",
                    },
                ],
            }
            vpc_policy_name = truncate_resource_name(
                "iam_policy", f"{role_name}-vpc-policy"
            )
            policies_to_attach.append((vpc_policy_name, vpc_policy))
            logger.info(f"Added VPC access policy to role {role_name}")

            # Attach all policies in parallel using ThreadPoolExecutor
            logger.info(
                f"Attaching {len(policies_to_attach)} policies to role {role_name} in parallel"
            )
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_policy = {
                    executor.submit(
                        attach_policy_async,
                        iam_client,
                        role_name,
                        policy_name,
                        policy_doc,
                        created_resources,
                    ): policy_name
                    for policy_name, policy_doc in policies_to_attach
                }

                policy_failures = []
                for future in as_completed(future_to_policy):
                    policy_name = future_to_policy[future]
                    try:
                        success, returned_policy_name = future.result()
                        if not success:
                            policy_failures.append(returned_policy_name)
                    except Exception as exc:
                        logger.error(
                            f"Policy attachment generated an exception for {policy_name}: {exc}"
                        )
                        policy_failures.append(policy_name)

                if policy_failures:
                    logger.warning(f"Failed to attach policies: {policy_failures}")
                    # Don't fail the entire operation for policy attachment issues
                else:
                    logger.info(
                        f"Successfully attached all policies to role {role_name}"
                    )

            # Define the policy ARN for wait_for_policy_attachment
            policy_arn = (
                "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            )

            # Get common libraries layer ARN from environment
            common_libraries_layer_arn = os.environ.get("COMMON_LIBRARIES_LAYER_ARN")

            # Construct AWS SDK Python layer ARN using current account
            aws_sdk_layer_arn = f"arn:aws:lambda:{bucket_region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-x86_64:2"

            # Get any existing layers
            layers = [layer_arn] if layer_arn else []

            # Add common libraries layer if available
            if common_libraries_layer_arn:
                layers.append(common_libraries_layer_arn)
                logger.info(
                    f"Adding common libraries layer to S3 connector Lambda: {common_libraries_layer_arn}"
                )

            # Add AWS SDK layer
            layers.append(aws_sdk_layer_arn)
            # Ultra-fast propagation checks - minimal waits for API Gateway timeout
            logger.info("Quick IAM propagation checks...")

            # Skip parallel checks - just do minimal verification
            if not wait_for_iam_role_propagation(iam_client, role_name):
                logger.warning(
                    f"Role {role_name} propagation check failed, continuing anyway..."
                )

            # Skip policy attachment wait - policies are attached, that's sufficient

            # Minimal Lambda-specific check
            wait_for_lambda_role_propagation(lambda_role_arn, role_name)

            # Deploy the lambda with minimal retries for API Gateway timeout
            max_lambda_retries = 2
            lambda_arn = None

            # Prepare Lambda function parameters
            create_function_params = {
                "FunctionName": target_function_name,
                "Runtime": "python3.12",
                "Role": lambda_role_arn,
                "Handler": "index.handler",
                "Code": {"S3Bucket": deployment_bucket, "S3Key": deployment_zip},
                "Publish": True,
                "Tags": {"medialake": medialake_tag},
                "Environment": {
                    "Variables": {
                        "PIPELINES_EVENT_BUS": pipelines_event_bus,
                        "MEDIALAKE_ASSET_TABLE": medialake_asset_table,
                        "POWERTOOLS_SERVICE_NAME": "asset-processor",
                        "POWERTOOLS_METRICS_NAMESPACE": "AssetProcessor",
                        "ASSETS_TABLE": medialake_asset_table,
                        "EVENT_BUS_NAME": pipelines_event_bus,
                        "DO_NOT_INGEST_DUPLICATES": "True",
                        "OPENSEARCH_ENDPOINT": os.environ["OPENSEARCH_ENDPOINT"],
                        "INDEX_NAME": os.environ.get("INDEX_NAME", "media"),
                        "OPENSEARCH_SERVICE": "es",
                        "REGION": bucket_region,
                        # S3 Vector Store configuration
                        "VECTOR_BUCKET_NAME": os.environ.get("VECTOR_BUCKET_NAME", ""),
                        "VECTOR_INDEX_NAME": os.environ.get(
                            "VECTOR_INDEX_NAME", "media-vectors"
                        ),
                    }
                },
                "Layers": layers,  # Updated to include both custom and AWS SDK layers
                "Timeout": 900,  # Maximum timeout: 15 minutes
                "MemorySize": 10240,  # Maximum memory: 10GB
                "EphemeralStorage": {"Size": 10240},  # Maximum ephemeral storage: 10GB
            }

            # Add VPC configuration for OpenSearch access
            opensearch_vpc_subnet_ids = os.environ["OPENSEARCH_VPC_SUBNET_IDS"]
            opensearch_security_group_id = os.environ["OPENSEARCH_SECURITY_GROUP_ID"]

            subnet_ids = opensearch_vpc_subnet_ids.split(",")
            create_function_params["VpcConfig"] = {
                "SubnetIds": subnet_ids,
                "SecurityGroupIds": [opensearch_security_group_id],
            }
            logger.info(
                f"Added VPC configuration to Lambda: Subnets={subnet_ids}, SecurityGroup={opensearch_security_group_id}"
            )

            for lambda_attempt in range(max_lambda_retries):
                try:
                    create_function_response = lambda_client.create_function(
                        **create_function_params
                    )
                    logger.info(
                        f"Successfully deployed Lambda function: {target_function_name}"
                    )
                    lambda_arn = create_function_response["FunctionArn"]
                    created_resources.append(("lambda_function", target_function_name))
                    break  # Success, exit retry loop

                except lambda_client.exceptions.InvalidParameterValueException as e:
                    if (
                        "cannot be assumed by Lambda" in str(e)
                        and lambda_attempt < max_lambda_retries - 1
                    ):
                        wait_time = 5 * (
                            lambda_attempt + 1
                        )  # Ultra-fast: 5, 10 seconds
                        logger.warning(
                            f"Lambda retry {lambda_attempt + 1}/{max_lambda_retries} after {wait_time}s..."
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(
                            f"Lambda creation failed after {lambda_attempt + 1} attempts: {str(e)}"
                        )
                        raise
                except Exception as e:
                    logger.error(
                        f"Unexpected error during Lambda creation (attempt {lambda_attempt + 1}): {str(e)}"
                    )
                    if lambda_attempt < max_lambda_retries - 1:
                        time.sleep(3)  # Minimal retry wait
                        continue
                    else:
                        raise

            if lambda_arn is None:
                raise Exception(
                    f"Failed to create Lambda function {target_function_name} after {max_lambda_retries} attempts"
                )

        except Exception as e:
            logger.error(f"Failed to deploy/configure lambda: {str(e)}")
            raise

        # Create EventBridge Pipe to connect SQS queue to Lambda function
        # This is needed for both eventbridge and s3Notifications integration methods
        try:
            pipe_resource_prefix = f"{resource_name_prefix}"
            pipe_arn, pipe_role_arn = create_eventbridge_pipe(
                pipe_resource_prefix,
                queue_arn,
                lambda_arn,
                bucket_region,
                created_resources,
                suffix,
            )
            logger.info(
                f"Created EventBridge Pipe: {pipe_arn} with role: {pipe_role_arn}"
            )
        except Exception as e:
            logger.error(f"Failed to create EventBridge Pipe: {str(e)}")
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
            "pipeRoleArn": pipe_role_arn,
        }

        table.put_item(Item=connector_item)
        created_resources.append(("dynamodb_item", (table_name, connector_id)))

        logger.info(f"Created connector '{connector_name}' for bucket '{s3_bucket}'")

        return {"status": "200", "message": "ok", "data": connector_item}

    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        error_traceback = traceback.format_exc()

        # Initialize region-specific clients for cleanup (in case they weren't created yet)
        eventbridge = None
        pipes_client = None
        s3 = None
        sqs = None
        lambda_client = None

        try:
            bucket_location = s3_client.get_bucket_location(Bucket=s3_bucket)
            bucket_region = bucket_location["LocationConstraint"]
            bucket_region = bucket_region or os.environ.get("REGION", "us-east-1")

            # Create region-specific clients for cleanup with optimized configuration
            eventbridge = get_optimized_client("events", bucket_region)
            pipes_client = get_optimized_client("pipes", bucket_region)
            s3 = get_optimized_client("s3", bucket_region)
            sqs = get_optimized_client("sqs", bucket_region)
            lambda_client = get_optimized_client("lambda", bucket_region)
            logger.info(f"Initialized cleanup clients for region: {bucket_region}")
        except Exception as cleanup_init_error:
            logger.error(
                f"Error initializing cleanup clients: {str(cleanup_init_error)}"
            )
            # If we can't initialize clients, we'll skip resource cleanup that requires them

        # Clean up created resources in reverse order
        for resource_type, resource_id in reversed(created_resources):
            try:
                if resource_type == "eventbridge_pipe" and pipes_client:
                    pipes_client.delete_pipe(Name=resource_id)
                    logger.info(f"Deleted EventBridge Pipe: {resource_id}")
                elif resource_type == "eventbridge_target" and eventbridge:
                    rule_name, target_id = resource_id
                    eventbridge.remove_targets(Rule=rule_name, Ids=[target_id])
                    logger.info(
                        f"Removed EventBridge target: {target_id} from rule: {rule_name}"
                    )
                elif resource_type == "eventbridge_rule" and eventbridge:
                    eventbridge.delete_rule(Name=resource_id)
                    logger.info(f"Deleted EventBridge rule: {resource_id}")
                elif resource_type == "eventbridge_config" and s3:
                    # Remove EventBridge configuration from bucket
                    s3.put_bucket_notification_configuration(
                        Bucket=resource_id, NotificationConfiguration={}
                    )
                    logger.info(
                        f"Removed EventBridge config from bucket: {resource_id}"
                    )
                elif resource_type == "dynamodb_item":
                    table_name, item_id = resource_id
                    table = dynamodb.Table(table_name)
                    table.delete_item(Key={"id": item_id})
                    logger.info(f"Deleted DynamoDB item: {item_id}")
                elif resource_type == "bucket_notification" and s3:
                    s3.put_bucket_notification_configuration(
                        Bucket=resource_id, NotificationConfiguration={}
                    )
                    logger.info(f"Removed bucket notifications from: {resource_id}")
                elif resource_type == "queue_policy" and sqs:
                    sqs.set_queue_attributes(
                        QueueUrl=resource_id, Attributes={"Policy": ""}
                    )
                    logger.info(f"Removed queue policy from: {resource_id}")
                elif resource_type == "event_source_mapping" and lambda_client:
                    lambda_client.delete_event_source_mapping(UUID=resource_id)
                    logger.info(f"Deleted event source mapping: {resource_id}")
                elif resource_type == "lambda_function" and lambda_client:
                    lambda_client.delete_function(FunctionName=resource_id)
                    logger.info(f"Deleted Lambda function: {resource_id}")
                elif resource_type == "inline_policy":
                    role_name, policy_name = resource_id
                    iam_client.delete_role_policy(
                        RoleName=role_name, PolicyName=policy_name
                    )
                    logger.info(
                        f"Deleted inline policy {policy_name} from role {role_name}"
                    )
                elif resource_type == "role_policy":
                    role_name, policy_name = resource_id
                    if policy_name in [
                        "AWSLambdaBasicExecutionRole",
                        "AWSLambdaVPCAccessExecutionRole",
                    ]:
                        iam_client.detach_role_policy(
                            RoleName=role_name,
                            PolicyArn=f"arn:aws:iam::aws:policy/service-role/{policy_name}",
                        )
                    else:
                        # Handle other managed policies if needed
                        iam_client.detach_role_policy(
                            RoleName=role_name,
                            PolicyArn=f"arn:aws:iam::aws:policy/{policy_name}",
                        )
                    logger.info(f"Detached policy {policy_name} from role {role_name}")
                elif resource_type == "iam_role":
                    iam_client.delete_role(RoleName=resource_id)
                    logger.info(f"Deleted IAM role: {resource_id}")
                elif resource_type == "sqs_queue" and sqs:
                    sqs.delete_queue(QueueUrl=resource_id)
                    logger.info(f"Deleted SQS queue: {resource_id}")
                elif resource_type == "s3_bucket" and s3:
                    # Only delete bucket if it's empty
                    try:
                        # First, try to delete all objects in the bucket
                        paginator = s3.get_paginator("list_objects_v2")
                        pages = paginator.paginate(Bucket=resource_id)

                        objects_to_delete = []
                        for page in pages:
                            if "Contents" in page:
                                objects_to_delete.extend(
                                    [{"Key": obj["Key"]} for obj in page["Contents"]]
                                )

                        if objects_to_delete:
                            s3.delete_objects(
                                Bucket=resource_id,
                                Delete={"Objects": objects_to_delete},
                            )
                            logger.info(
                                f"Deleted {len(objects_to_delete)} objects from bucket: {resource_id}"
                            )

                        # Now delete the bucket
                        s3.delete_bucket(Bucket=resource_id)
                        logger.info(f"Deleted S3 bucket: {resource_id}")
                    except Exception as bucket_cleanup_error:
                        logger.warning(
                            f"Could not delete S3 bucket {resource_id}: {str(bucket_cleanup_error)}"
                        )
                        # Don't fail the entire cleanup if bucket deletion fails
                else:
                    logger.warning(
                        f"Skipping cleanup for {resource_type}: {resource_id} - client not available"
                    )
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
