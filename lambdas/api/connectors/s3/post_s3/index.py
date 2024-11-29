import os
import uuid
import json
import time
import string
import random
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
from botocore.exceptions import ClientError

tracer = Tracer()
logger = Logger()
app = APIGatewayRestResolver(enable_validation=True)

# Initialize AWS Clients S3 client - region will be determined per bucket
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
iam_client = boto3.client("iam")


class S3ConnectorConfig(BaseModel):
    bucket: str
    s3IntegrationMethod: str


class S3Connector(BaseModel):
    configuration: S3ConnectorConfig
    name: str
    type: str

def wait_for_iam_role_propagation(iam_client, role_name, max_retries=5, base_delay=1):
    for attempt in range(max_retries):
        try:
            iam_client.get_role(RoleName=role_name)
            return True
        except iam_client.exceptions.NoSuchEntityException:
            delay = (2 ** attempt) * base_delay
            time.sleep(delay)
    return False

def wait_for_policy_attachment(iam_client, role_name, policy_arn, max_retries=5, base_delay=1):
    for attempt in range(max_retries):
        try:
            attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)['AttachedPolicies']
            if any(policy['PolicyArn'] == policy_arn for policy in attached_policies):
                return True
            delay = (2 ** attempt) * base_delay
            time.sleep(delay)
        except iam_client.exceptions.NoSuchEntityException:
            delay = (2 ** attempt) * base_delay
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
    s3_bucket: str, bucket_region: str, created_resources: list
) -> tuple[str, str]:
    """Set up EventBridge notifications and return queue URL and ARN"""

    eventbridge = boto3.client("events", region_name=bucket_region)
    sqs = boto3.client("sqs", region_name=bucket_region)
    s3 = boto3.client("s3", region_name=bucket_region)

    # Enable EventBridge notifications on the S3 bucket
    try:
        response = s3.put_bucket_notification_configuration(
            Bucket=s3_bucket,
            NotificationConfiguration={"EventBridgeConfiguration": {}},
        )
        logger.info(
            f"Enabled EventBridge notifications for bucket {s3_bucket} with response {response}"
        )
        created_resources.append(("eventbridge_config", s3_bucket))
    except ClientError as e:
        logger.error(f"Failed to enable EventBridge notifications: {str(e)}")
        raise

    # Create FIFO SQS queue
    queue_name = (
        f"medialake-connector-{s3_bucket}-eventbridge.fifo"  # Note the .fifo suffix
    )
    response = sqs.create_queue(
        QueueName=queue_name,
        Attributes={
            "VisibilityTimeout": "360",
            "FifoQueue": "true",  # Enable FIFO
            "ContentBasedDeduplication": "true",  # Enable content-based deduplication
            "DeduplicationScope": "messageGroup",  # Deduplicate within message groups
            "FifoThroughputLimit": "perMessageGroupId",  # Throughput limit per message group
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
    role_name = f"medialake-eb-{rule_name}"

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


@app.post("/connectors/s3")
def create_connector(createconnector: S3Connector) -> dict:
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

        def generate_suffix():
            """Generate a 6-digit alphanumeric suffix"""
            return "".join(random.choices(string.ascii_lowercase + string.digits, k=6))

        # Get request variables from request body
        s3_bucket = createconnector.configuration.bucket
        connector_name = createconnector.name
        integration_method = createconnector.configuration.s3IntegrationMethod

        suffix = generate_suffix()

        # Create resource specific name prefix
        resource_name_prefix = f"medialake_connector_{s3_bucket}"
        target_function_name = f"medialake_connector_{s3_bucket}_{suffix}"

        # Validate S3 bucket exists and get its region
        try:

            bucket_location = s3_client.get_bucket_location(Bucket=s3_bucket)
            bucket_region = bucket_location["LocationConstraint"]
            bucket_region = bucket_region or "us-east-1"
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

        # Set up notifications based on integration method
        if integration_method == "eventbridge":
            queue_url, queue_arn = setup_eventbridge_notifications(
                s3_bucket, bucket_region, created_resources
            )
        else:  # s3-event-notifications
            # Create SQS queue in the same region as the bucket
            queue_name = f"medialake-connector-{s3_bucket}-notifications"
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

            # Configure S3 bucket notifications with comprehensive event types
            notification_config = {
                "QueueConfigurations": [
                    {
                        "QueueArn": queue_arn,
                        "Events": [
                            "s3:ObjectCreated:*",
                            "s3:ObjectRemoved:*",
                            "s3:ObjectRestore:*",
                            "s3:ObjectTagging:*",
                            "s3:ObjectAcl:Put",
                            # "s3:ObjectStorageClass:Changed",
                        ],
                    }
                ]
            }
            s3.put_bucket_notification_configuration(
                Bucket=s3_bucket, NotificationConfiguration=notification_config
            )
            created_resources.append(("bucket_notification", s3_bucket))

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

            # Wait for role to be available
   
            if not wait_for_iam_role_propagation(iam_client, role_name):
                raise Exception(f"IAM role {role_name} did not propagate in time")


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
                PolicyName=f"{role_name}-sqs-policy",
                PolicyDocument=json.dumps(sqs_policy),
            )
            created_resources.append(
                ("inline_policy", (role_name, f"{role_name}-sqs-policy"))
            )

          
            # Wait for policy attachment to propagate
            if not wait_for_policy_attachment(iam_client, role_name, policy_arn):
                raise Exception(

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
                            asset_table_asset_id_index_arn
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
                if resource_type == "eventbridge_target":
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
            "statusCode": 500,
            "body": {"status": "500", "message": "Internal server error", "data": {}},
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
