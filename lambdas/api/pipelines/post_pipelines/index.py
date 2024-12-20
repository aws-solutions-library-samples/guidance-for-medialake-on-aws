import os
import uuid
import json
import time
import boto3
from decimal import Decimal
from datetime import datetime
from contextlib import ExitStack
from botocore.exceptions import ClientError


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

from image_pipeline_definitions import (
    get_state_machine_definition,
    # create_metadata_extractor_lambda,
    # create_image_proxy_lambda,
)

tracer = Tracer()
logger = Logger()
app = APIGatewayRestResolver(enable_validation=True)

# Initialize AWS clients
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")
iam_client = boto3.client("iam")
sqs_client = boto3.client("sqs")
sfn_client = boto3.client("stepfunctions")
eventbridge = boto3.client("events")


class S3Pipeline(BaseModel):
    definition: dict
    name: str
    type: str
    system: bool


def wait_for_iam_role_propagation(iam_client, role_name, max_retries=5, base_delay=5):

    for attempt in range(max_retries):
        logger.info(f"wait_for_iam_role_propagation {role_name}. retry {attempt}")
        try:
            iam_client.get_role(RoleName=role_name)
            time.sleep(base_delay)
            return True
        except iam_client.exceptions.NoSuchEntityException:
            delay = (2**attempt) * base_delay
            time.sleep(delay)
    return False


def wait_for_policy_attachment(
    iam_client, role_name, policy_arn, max_retries=5, base_delay=5
):
    for attempt in range(max_retries):
        logger.info(f"wait_for_policy_attachment {role_name}. retry {attempt}")
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


def float_to_decimal(obj):
    """Convert float values to Decimal for DynamoDB compatibility"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [float_to_decimal(x) for x in obj]
    return obj


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


def create_sqs_fifo_queue(queue_name: str, tags: dict) -> tuple[str, str]:
    """Create SQS FIFO queue and return queue URL and ARN"""
    try:
        # Create the queue first
        response = sqs_client.create_queue(
            QueueName=f"{queue_name}.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "true",
                "DeduplicationScope": "messageGroup",
                "FifoThroughputLimit": "perMessageGroupId",
            },
            tags=tags,
        )
        queue_url = response["QueueUrl"]

        # Get queue ARN
        queue_attributes = sqs_client.get_queue_attributes(
            QueueUrl=queue_url, AttributeNames=["QueueArn"]
        )
        queue_arn = queue_attributes["Attributes"]["QueueArn"]

        # Add permission for EventBridge to send messages
        queue_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "EventBridgeToSQS",
                    "Effect": "Allow",
                    "Principal": {"Service": "events.amazonaws.com"},
                    "Action": "sqs:SendMessage",
                    "Resource": queue_arn,
                }
            ],
        }

        # Set the queue policy
        sqs_client.set_queue_attributes(
            QueueUrl=queue_url, Attributes={"Policy": json.dumps(queue_policy)}
        )

        return queue_url, queue_arn
    except Exception as e:
        logger.error(f"Failed to create SQS FIFO queue: {str(e)}")
        raise


def create_state_machine(
    state_machine_name: str, role_arn: str, definition: dict, tags: dict
) -> str:
    """Create Step Function state machine and return its ARN"""
    try:
        response = sfn_client.create_state_machine(
            name=state_machine_name,
            definition=json.dumps(definition),
            roleArn=role_arn,
            type="STANDARD",
            tags=[{"key": k, "value": v} for k, v in tags.items()],
        )
        return response["stateMachineArn"]
    except Exception as e:
        logger.error(f"Failed to create Step Function: {str(e)}")
        raise


def create_eventbridge_rule(
    rule_name: str, event_bus_name: str, queue_arn: str, tags: dict
) -> str:
    """Create EventBridge rule to send all events to SQS FIFO queue"""
    try:

        # Create the rule
        response = eventbridge.put_rule(
            Name=rule_name,
            EventBusName=event_bus_name,
            EventPattern=json.dumps({"detail-type": ["AssetCreated"]}),
            State="ENABLED",
            Tags=[{"Key": k, "Value": v} for k, v in tags.items()],
        )

        # Add target (SQS queue)
        eventbridge.put_targets(
            Rule=rule_name,
            EventBusName=event_bus_name,
            Targets=[
                {
                    "Id": f"{rule_name}-target",
                    "Arn": queue_arn,
                    "SqsParameters": {
                        "MessageGroupId": "default"  # Required for FIFO queues
                    },
                }
            ],
        )

        return response["RuleArn"]
    except Exception as e:
        logger.error(f"Failed to create EventBridge rule: {str(e)}")
        raise


def create_stepfunction_role(role_name: str, queue_arn: str, tags: dict) -> str:
    """Create IAM role for pipeline execution"""
    try:
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": ["states.amazonaws.com"]},
                    "Action": "sts:AssumeRole",
                }
            ],
        }

        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
            Tags=[{"Key": k, "Value": v} for k, v in tags.items()],
        )

        lambda_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["lambda:InvokeFunction"],
                    "Resource": [
                        os.environ.get("IMAGE_METADATA_EXTRACTOR_LAMBDA_ARN"),
                        os.environ.get("IMAGE_PROXY_LAMBDA_ARN"),
                    ],
                }
            ],
        }

        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}-lambda-policy",
            PolicyDocument=json.dumps(lambda_policy),
        )

        return response["Role"]["Arn"]
    except Exception as e:
        logger.error(f"Failed to create IAM role: {str(e)}")
        raise


def create_executer_lambda_role(
    role_name: str, queue_arn: str, state_machine_name: str, tags: dict
) -> str:
    """Create IAM role for executer lambda"""
    try:
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": ["lambda.amazonaws.com"]},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
        policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
            Tags=[{"Key": k, "Value": v} for k, v in tags.items()],
        )

        # Attach policies to the role
        iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)

        if not wait_for_policy_attachment(iam_client, role_name, policy_arn):
            raise Exception(
                f"Policy {policy_arn} did not attach to role {role_name} in time"
            )

        # Create and attach SQS policy
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
                        "sqs:SendMessage",
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

        step_functions_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "states:StartExecution",
                        "states:DescribeExecution",
                        "states:StopExecution",
                    ],
                    "Resource": [
                        f"arn:aws:states:{os.environ['AWS_REGION']}:{os.environ['AWS_ACCOUNT_ID']}:stateMachine:{state_machine_name}",
                        f"arn:aws:states:{os.environ['AWS_REGION']}:{os.environ['AWS_ACCOUNT_ID']}:execution:{state_machine_name}:*",
                    ],
                }
            ],
        }

        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}-stepfunctions-policy",
            PolicyDocument=json.dumps(step_functions_policy),
        )

        return response["Role"]["Arn"]
    except Exception as e:
        logger.error(f"Failed to create IAM role: {str(e)}")
        raise


def update_lambda_role_permissions(function_name, new_policy):
    # Get the current function configuration
    function_config = lambda_client.get_function(FunctionName=function_name)
    current_role_arn = function_config["Configuration"]["Role"]

    # Extract the role name from the ARN
    role_name = current_role_arn.split("/")[-1]

    # Add the new policy to the role
    try:
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}-additional-policy",
            PolicyDocument=json.dumps(new_policy),
        )
        logger.info(f"Successfully added new policy to role {role_name}")
    except Exception as e:
        logger.error(f"Failed to add policy to role {role_name}: {str(e)}")
        raise


def check_event_source_mappings(lambda_name: str) -> bool:
    """Check if a Lambda function has any event source mappings"""
    try:
        response = lambda_client.list_event_source_mappings(FunctionName=lambda_name)
        if response["EventSourceMappings"]:
            return True
        return False
    except Exception as e:
        logger.error(
            f"Error checking event source mappings for {lambda_name}: {str(e)}"
        )
        raise


def check_resource_exists(
    pipeline_name: str,
    queue_name: str,
    rule_name: str,
    sfn_role_name: str,
    lambda_s3_dynamo_rw_role_name: str,
    lambda_executer_role_name: str,
    state_machine_name: str,
    lambda_names: list,
) -> tuple[bool, str]:
    """Check if any of the resources already exist"""
    try:
        # Check SQS Queue
        try:
            sqs_client.get_queue_url(QueueName=f"{queue_name}.fifo")
            return True, f"SQS Queue {queue_name}.fifo already exists"
        except sqs_client.exceptions.QueueDoesNotExist:
            pass

        # Check EventBridge Rule
        try:
            eventbridge.describe_rule(Name=rule_name)
            return True, f"EventBridge Rule {rule_name} already exists"
        except eventbridge.exceptions.ResourceNotFoundException:
            pass

        # Check IAM Roles
        try:
            iam_client.get_role(RoleName=lambda_s3_dynamo_rw_role_name)
            return True, f"IAM Role {lambda_s3_dynamo_rw_role_name} already exists"
        except iam_client.exceptions.NoSuchEntityException:
            pass
        try:
            iam_client.get_role(RoleName=lambda_executer_role_name)
            return True, f"IAM Role {lambda_executer_role_name} already exists"
        except iam_client.exceptions.NoSuchEntityException:
            pass
        try:
            iam_client.get_role(RoleName=sfn_role_name)
            return True, f"IAM Role {sfn_role_name} already exists"
        except iam_client.exceptions.NoSuchEntityException:
            pass

        # Check Step Function
        try:
            sfn_client.describe_state_machine(
                stateMachineArn=f"arn:aws:states:{os.environ['AWS_REGION']}:{os.environ['AWS_ACCOUNT_ID']}:stateMachine:{state_machine_name}"
            )
            return True, f"State Machine {state_machine_name} already exists"
        except sfn_client.exceptions.StateMachineDoesNotExist:
            pass

        # Check Lambda Functions
        for lambda_name in lambda_names:
            try:
                lambda_client.get_function(FunctionName=lambda_name)
                if check_event_source_mappings(lambda_name):
                    return (
                        True,
                        f"Lambda Function {lambda_name} with event source mappings already exists",
                    )
                return True, f"Lambda Function {lambda_name} already exists"
            except lambda_client.exceptions.ResourceNotFoundException:
                pass

        # Check DynamoDB for pipeline name
        pipeline_table_name = os.environ.get("PIPELINES_TABLE_NAME")
        if pipeline_table_name:
            pipeline_table = dynamodb.Table(pipeline_table_name)
            response = pipeline_table.scan(
                FilterExpression="#name = :name",
                ExpressionAttributeNames={"#name": "name"},
                ExpressionAttributeValues={":name": pipeline_name},
            )
            if response["Items"]:
                return True, f"Pipeline with name {pipeline_name} already exists"

        return False, ""

    except Exception as e:
        logger.error(f"Error checking resource existence: {str(e)}")
        raise


def rollback_resources(resources_to_delete):
    for resource_type, resource_id in resources_to_delete:
        try:
            print(f"rollback {resource_type}")
            if resource_type == "sqs":
                sqs_client.delete_queue(QueueUrl=resource_id)
            elif resource_type == "eventbridge_rule":
                eventbridge.delete_rule(Name=resource_id)
            elif (
                resource_type == "iam_stepfunction_role"
                or resource_type == "iam_lambda_executer_role"
            ):

                # Detach policies and delete role
                role_name = resource_id.split("/")[-1]

                attached_policies = iam_client.list_attached_role_policies(
                    RoleName=role_name
                )
                for policy in attached_policies.get("AttachedPolicies", []):
                    try:
                        iam_client.detach_role_policy(
                            RoleName=role_name, PolicyArn=policy["PolicyArn"]
                        )
                        logger.info(
                            f"Successfully detached managed policy {policy['PolicyArn']} from role {role_name}"
                        )
                    except ClientError as e:
                        if e.response["Error"]["Code"] != "NoSuchEntity":
                            raise
                        logger.warning(f"Policy {policy['PolicyArn']} already detached")

                inline_policies = iam_client.list_role_policies(RoleName=role_name)
                for policy_name in inline_policies.get("PolicyNames", []):
                    try:
                        iam_client.delete_role_policy(
                            RoleName=role_name, PolicyName=policy_name
                        )
                        logger.info(
                            f"Successfully deleted inline policy {policy_name} from role {role_name}"
                        )
                    except ClientError as e:
                        if e.response["Error"]["Code"] != "NoSuchEntity":
                            raise
                        logger.warning(f"Inline policy {policy_name} already deleted")

            elif resource_type == "lambda":
                lambda_client.delete_function(FunctionName=resource_id)
            elif resource_type == "step_function":
                sfn_client.delete_state_machine(stateMachineArn=resource_id)
            elif resource_type == "event_source_mapping":
                lambda_client.delete_event_source_mapping(UUID=resource_id)
            logger.info(f"Rolled back {resource_type}: {resource_id}")
        except ClientError as e:
            logger.error(
                f"Failed to roll back {resource_type}: {resource_id}. Error: {str(e)}"
            )


def create_iam_lambda_s3_dynamo_rw_policy(connector_buckets):
    iam_lambda_s3_dynamo_rw_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:UpdateItem",
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                ],
                "Resource": [f"{os.environ['MEDIALAKE_ASSET_TABLE']}"],
            },
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject", "s3:PutObjectAcl"],
                "Resource": [
                    f"arn:aws:s3:::{os.environ['MEDIA_ASSETS_BUCKET_NAME']}/*",
                    f"arn:aws:s3:::{os.environ.get('MEDIA_ASSETS_BUCKET_NAME')}",
                ],
            },
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket}/*" for bucket in connector_buckets]
                + [f"arn:aws:s3:::{bucket}" for bucket in connector_buckets],
            },
            {
                "Effect": "Allow",
                "Action": ["kms:GenerateDataKey"],
                "Resource": [
                    os.environ["MEDIA_ASSETS_BUCKET_NAME_KMS_KEY"],
                ],
            },
        ],
    }
    return iam_lambda_s3_dynamo_rw_policy


def get_connector_buckets(pipeline_type):
    print(os.environ["CONNECTOR_TABLE"])

    connector_table = dynamodb.Table(os.environ["CONNECTOR_TABLE"])
    response = connector_table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr("type").eq("s3")
    )
    print(response)

    buckets = []
    for item in response["Items"]:
        if "storageIdentifier" in item:
            buckets.append(item["storageIdentifier"])

    if not buckets:
        raise ValueError("No connectors found. Pipeline creation cannot proceed.")

    return buckets


@app.post("/pipelines")
def create_pipeline(createpipeline: S3Pipeline) -> dict:
    resources_to_delete = []

    with ExitStack() as stack:
        stack.callback(rollback_resources, resources_to_delete)
        connector_buckets = None
        try:

            try:
                connector_buckets = get_connector_buckets(createpipeline.type)
            except ValueError as e:
                logger.error(f"Failed to create pipeline: {str(e)}")
                return {
                    "status": "400",
                    "message": str(e),
                    "data": {"error": str(e)},
                }

            global_prefix = os.environ["GLOBAL_PREFIX"]
            # Generate names for resources
            queue_name = f"{global_prefix}-pl-{createpipeline.name}"
            rule_name = f"{global_prefix}-pl-{createpipeline.name}-rule"
            sfn_role_name = f"{global_prefix}-pl-sfn-{createpipeline.name}"

            lambda_s3_dynamo_rw_role_name = (
                f"{global_prefix}-pl-s3_dynamo_rw-lam-{createpipeline.name}"
            )
            lambda_executer_role_name = (
                f"{global_prefix}-pl-executer-lam-{createpipeline.name}"
            )
            state_machine_name = f"{global_prefix}-pl-{createpipeline.name}"

            pipeline_trigger_lambda_function_name = (
                f"medialake-pipeline-{createpipeline.name}-executor"
            )

            # Check if resources exist
            resources_exist, error_message = check_resource_exists(
                createpipeline.name,
                queue_name,
                rule_name,
                sfn_role_name,
                lambda_s3_dynamo_rw_role_name,
                lambda_executer_role_name,
                state_machine_name,
                [pipeline_trigger_lambda_function_name],
            )

            if resources_exist:
                return {
                    "status": "409",
                    "message": "Resource conflict",
                    "data": {"error": error_message},
                }

            # Generate unique ID and timestamps
            pipeline_id = str(uuid.uuid4())
            current_time = datetime.utcnow().isoformat(timespec="seconds")
            deployment_bucket = os.environ.get("IAC_ASSETS_BUCKET")
            pipeline_trigger_deployment_zip = os.environ.get("PIPELINE_TRIGGER_LAMBDA")
            parent_event_bus_name = os.environ.get("INGEST_EVENT_BUS")
            # connector_table_name = os.environ.get("CONNECTOR_TABLE_NAME")
            # Common tags for all resources
            tags = {
                "medialake": "true",
                "pipeline_id": pipeline_id,
                "pipeline_name": createpipeline.name,
            }

            # Create SQS FIFO Queue
            queue_name = f"medialake-pipeline-{createpipeline.name}"
            try:
                queue_url, queue_arn = create_sqs_fifo_queue(queue_name, tags)
                resources_to_delete.append(("sqs", queue_url))
            except sqs_client.exceptions.QueueDeletedRecently as e:
                logger.error(f"Failed to create pipeline: {str(e)}")
                return {
                    "status": "400",
                    "message": "SQS FIFO queue creation failed: 60-second wait required after deletion before reusing name.",
                    "data": {
                        "error": "You must wait 60 seconds after deleting a queue before you can create another with the same name."
                    },
                }

            # Create EventBridge rule
            rule_name = f"medialake-pipeline-{createpipeline.name}-rule"
            rule_arn = create_eventbridge_rule(
                rule_name, parent_event_bus_name, queue_arn, tags
            )
            resources_to_delete.append(("eventbridge_rule", rule_name))

            # Create IAM Role for Lambda and Step Functions
            state_machine_name = f"medialake-pipeline-{createpipeline.name}"

            sfn_role_arn = create_stepfunction_role(sfn_role_name, queue_arn, tags)
            resources_to_delete.append(("iam_stepfunction_role", sfn_role_arn))

            lambda_executer_role_arn = create_executer_lambda_role(
                lambda_executer_role_name, queue_arn, state_machine_name, tags
            )
            resources_to_delete.append(
                ("iam_lambda_executer_role", lambda_executer_role_arn)
            )

            iam_lambda_s3_dynamo_rw_policy = create_iam_lambda_s3_dynamo_rw_policy(
                connector_buckets
            )
            # print(iam_lambda_s3_dynamo_rw_policy)

            update_lambda_role_permissions(
                os.environ.get("IMAGE_METADATA_EXTRACTOR_LAMBDA_ARN"),
                iam_lambda_s3_dynamo_rw_policy,
            )
            update_lambda_role_permissions(
                os.environ.get("IMAGE_PROXY_LAMBDA_ARN"), iam_lambda_s3_dynamo_rw_policy
            )

            new_bucket_policy = {
                "Sid": "AllowLambdaWriteAccess",
                "Effect": "Allow",
                "Principal": {
                    "Service": "lambda.amazonaws.com"  # Use service principal
                },
                "Action": ["s3:PutObject", "s3:PutObjectAcl"],
                "Resource": [
                    f"arn:aws:s3:::{os.environ['MEDIA_ASSETS_BUCKET_NAME']}/*",
                    f"arn:aws:s3:::{os.environ['MEDIA_ASSETS_BUCKET_NAME']}",
                ],
                "Condition": {
                    "ArnLike": {"aws:SourceArn": os.environ["IMAGE_PROXY_LAMBDA_ARN"]}
                },
            }
            result = s3_client.get_bucket_policy(
                Bucket=os.environ["MEDIA_ASSETS_BUCKET_NAME"]
            )
            current_policy = json.loads(result["Policy"])
            current_policy["Statement"].append(new_bucket_policy)
            updated_policy = json.dumps(current_policy)
            # print(updated_policy)
            # Do not JSON dump again, as it's already a JSON string
            s3_client.put_bucket_policy(
                Bucket=os.environ["MEDIA_ASSETS_BUCKET_NAME"],
                Policy=updated_policy,
            )

            # Create Step Function
            state_machine_name = f"medialake-pipeline-{createpipeline.name}"

            # Get state machine definition

            state_machine_definition = get_state_machine_definition(
                os.environ.get("IMAGE_METADATA_EXTRACTOR_LAMBDA_ARN"),
                os.environ.get("IMAGE_PROXY_LAMBDA_ARN"),
                createpipeline.name,
                os.environ.get("MEDIA_ASSETS_BUCKET_NAME"),
            )

            state_machine_arn = create_state_machine(
                state_machine_name, sfn_role_arn, state_machine_definition, tags
            )
            resources_to_delete.append(("step_function", state_machine_arn))

            # Create Lambda Function

            pipeline_trigger_lambda_response = lambda_client.create_function(
                FunctionName=pipeline_trigger_lambda_function_name,
                Runtime="python3.12",
                Role=lambda_executer_role_arn,
                Handler="index.lambda_handler",
                Code={
                    "S3Bucket": deployment_bucket,
                    "S3Key": pipeline_trigger_deployment_zip,
                },
                Environment={"Variables": {"STEP_FUNCTION_ARN": state_machine_arn}},
                Tags=tags,
            )
            resources_to_delete.append(
                ("lambda", pipeline_trigger_lambda_function_name)
            )

            if not wait_for_iam_role_propagation(iam_client, sfn_role_name):
                raise Exception(
                    f"Role {lambda_executer_role_name} is not ready in time"
                )
            # Add SQS trigger to Lambda
            event_source_mapping = lambda_client.create_event_source_mapping(
                EventSourceArn=queue_arn,
                FunctionName=pipeline_trigger_lambda_function_name,
                Enabled=True,
            )
            resources_to_delete.append(
                ("event_source_mapping", event_source_mapping["UUID"])
            )

            # Save pipeline details to DynamoDB
            pipeline_table_name = os.environ.get("PIPELINES_TABLE_NAME")
            if not pipeline_table_name:
                raise ValueError("PIPELINES_TABLE_NAME environment variable not set")

            # Convert the definition's float values to Decimal
            definition = float_to_decimal(createpipeline.definition)

            pipeline_table = dynamodb.Table(pipeline_table_name)
            pipeline_item = {
                "id": pipeline_id,
                "name": createpipeline.name,
                "system": createpipeline.system,
                "type": createpipeline.type,
                "createdAt": current_time,
                "updatedAt": current_time,
                "definition": definition,
                "queueUrl": queue_url,
                "queueArn": queue_arn,
                # "eventBridgeRuleArn": rule_arn,
                "eventBridgeDetails": {
                    "eventBridgeRuleArn": rule_arn,
                    "parentEventBusName": parent_event_bus_name,
                },
                "triggerLambdaArn": pipeline_trigger_lambda_response["FunctionArn"],
                "stateMachineArn": state_machine_arn,
                "sfnRoleArn": sfn_role_arn,
                "executerRoleArn": lambda_executer_role_arn,
                "dependentResources": resources_to_delete,
            }

            pipeline_table.put_item(Item=pipeline_item)

            logger.info(
                f"Created pipeline '{createpipeline.name}' with ID {pipeline_id}"
            )
            stack.pop_all()

            return {
                "status": "200",
                "message": "Pipeline created successfully",
                "data": pipeline_item,
            }

        except Exception as e:
            logger.exception(f"Failed to create pipeline: {str(e)}")
            raise  # Re-raise the exception to trigger the rollback
    return {
        "statusCode": 500,
        "body": {
            "status": "500",
            "message": f"Failed to create pipeline: {str(e)}",
            "data": {},
        },
    }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
