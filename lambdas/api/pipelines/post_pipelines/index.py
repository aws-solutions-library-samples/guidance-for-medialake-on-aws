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

MAX_RETRIES = 10
RETRY_DELAY = 5


class S3Pipeline(BaseModel):
    definition: dict
    event_pattern: dict
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


def wait_for_lambda_ready(function_name: str, max_retries=50, delay=10):
    lambda_client = boto3.client("lambda")
    for _ in range(max_retries):
        response = lambda_client.get_function(FunctionName=function_name)
        if response["Configuration"]["State"] == "Active":
            time.sleep(delay * 2)
            return True
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


def get_state_machine_definition(
    pipeline_definition: dict, output_bucket_name: str, pipeline_name: str
) -> dict:
    """Returns the state machine definition based on the provided pipeline definition"""
    logger.info(f"Pipeline definition received: {pipeline_definition}")

    if not isinstance(pipeline_definition, dict):
        raise ValueError(f"Expected dictionary, got {type(pipeline_definition)}")

    if "nodes" not in pipeline_definition or "edges" not in pipeline_definition:
        raise ValueError(
            f"Pipeline definition is missing 'nodes' or 'edges'. Keys present: {pipeline_definition.keys()}"
        )

    nodes = pipeline_definition["nodes"]
    edges = pipeline_definition["edges"]

    # Create a mapping of node ids to their data
    node_map = {node["id"]: node["data"] for node in nodes}

    # Find the start node (node with no incoming edges)
    start_node = next(
        node
        for node in nodes
        if not any(edge["target"] == node["id"] for edge in edges)
    )

    # Create the state machine definition
    state_machine = {
        "Comment": f"Pipeline {pipeline_name}",
        "StartAt": node_map[start_node["id"]]["label"].replace(" ", ""),
        "States": {
            "PublishCompletion": {
                "Type": "Task",
                "Resource": "arn:aws:states:::events:putEvents",
                "Parameters": {
                    "Entries": [
                        {
                            "DetailType": "Pipeline Execution Completed",
                            "Source": "medialake.pipeline",
                            "EventBusName": os.environ["INGEST_EVENT_BUS"],
                            "Detail": {
                                "pipelineName": pipeline_name,
                                "status": "SUCCESS",
                                "outputs.$": "$",
                            },
                        }
                    ]
                },
                "Next": "FinishState",
            }
        },
    }

    # Create states for each node
    for node in nodes:
        node_data = node["data"]
        state_name = node_data["label"].replace(" ", "")

        if node_data["type"] in [
            "videometadata",
            "audiometadata",
            "imagemetadata",
            "videoproxyandthumbnail",
            "audioproxyandthumbnail",
            "imageproxy",
            "imagethumbnail",
            "checkmediaconvertstatus",
        ]:
            state = {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": node_data["id"],
                    "Payload": {
                        "pipeline_id.$": "$.pipeline_id",
                        "input.$": "$.input",
                        "previous_task_output.$": "$",
                    },
                },
                "ResultPath": f"$.{state_name}Result",
                "Retry": [
                    {
                        "ErrorEquals": ["Lambda.TooManyRequestsException"],
                        "IntervalSeconds": 1,
                        "MaxAttempts": 10,
                        "BackoffRate": 2.0
                    }
                ]
            }
        elif node_data["type"] == "choice":
            state = {"Type": "Choice", "Choices": [], "Default": "FailState"}
            for edge in edges:
                if edge["source"] == node["id"]:
                    condition = edge["data"].get("condition", {})
                    if condition:
                        target_type = node_map[edge["target"]]["type"]
                        next_state = (
                            "PublishCompletion"
                            if target_type == "succeed"
                            else node_map[edge["target"]]["label"].replace(" ", "")
                        )
                        choice = {"Next": next_state}
                        if "equals" in condition:
                            choice["StringEquals"] = condition["equals"]
                            choice["Variable"] = condition["variable"]
                        elif "not_equals" in condition:
                            if isinstance(condition["not_equals"], list):
                                # Handle multiple not_equals values
                                choice["And"] = [
                                    {
                                        "Not": {
                                            "Variable": condition["variable"],
                                            "StringEquals": value,
                                        }
                                    }
                                    for value in condition["not_equals"]
                                ]
                            else:
                                choice["Not"] = {
                                    "Variable": condition["variable"],
                                    "StringEquals": condition["not_equals"],
                                }
                        state["Choices"].append(choice)
        elif node_data["type"] == "wait":
            state = {
                "Type": "Wait",
                "Seconds": node_data.get("seconds", 60),
            }
        elif node_data["type"] == "succeed":
            state = {"Type": "Succeed"}
        elif node_data["type"] == "fail":
            state = {
                "Type": "Fail",
                "Cause": node_data.get("cause", "Pipeline execution failed"),
            }
        else:
            raise ValueError(f"Unsupported node type: {node_data['type']}")

        # Add mode and output_bucket for Image Proxy, Image Thumbnail, Video Proxy, and Video Thumbnail
        if node_data["type"] in [
            "imageproxy",
            "imagethumbnail",
            "videoproxyandthumbnail",
            "audioproxyandthumbnail",
        ]:
            state["Parameters"]["Payload"]["output_bucket"] = output_bucket_name
            state["Parameters"]["Payload"]["mode"] = (
                "proxy"
                if node_data["type"] in ["imageproxy", "videoproxy", "audioproxy"]
                else "thumbnail"
            )
            # Add width and height for Image Thumbnail and Video Thumbnail
            if node_data["type"] in [
                "imagethumbnail",
                "videothumbnail",
                "audiothumbnail",
            ]:
                state["Parameters"]["Payload"]["width"] = node_data.get("width")
                state["Parameters"]["Payload"]["height"] = node_data.get("height")

        # Find the next node
        next_edge = next((edge for edge in edges if edge["source"] == node["id"]), None)
        if next_edge and node_data["type"] not in ["choice", "succeed", "fail"]:
            target_type = node_map[next_edge["target"]]["type"]
            state["Next"] = (
                "PublishCompletion"
                if target_type == "succeed"
                else node_map[next_edge["target"]]["label"].replace(" ", "")
            )
        elif node_data["type"] not in ["choice", "succeed", "fail"]:
            if not next_edge:
                state["Next"] = "PublishCompletion"

        state_machine["States"][state_name] = state

    # Add FinishState as a terminal state
    state_machine["States"]["FinishState"] = {"Type": "Succeed"}

    print(state_machine)
    return state_machine


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
                "VisibilityTimeout": "300",
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


def create_sqs_standard_queue(queue_name: str, tags: dict) -> tuple[str, str]:
    """Create SQS standard queue and return queue URL and ARN"""
    try:
        # Create the queue
        response = sqs_client.create_queue(
            QueueName=queue_name,
            Attributes={
                "VisibilityTimeout": "300",
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
        logger.error(f"Failed to create SQS standard queue: {str(e)}")
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
    rule_name: str,
    event_bus_name: str,
    queue_arn: str,
    event_pattern: dict,
    state_machine_arn: str,
    tags: dict,
) -> str:
    """Create EventBridge rule to send all events to SQS Standard queue"""
    try:

        # Create the rule
        response = eventbridge.put_rule(
            Name=rule_name,
            EventBusName=event_bus_name,
            EventPattern=json.dumps(event_pattern),
            State="ENABLED",
            Tags=[{"Key": k, "Value": v} for k, v in tags.items()],
        )

        # SQS FIFO
        eventbridge.put_targets(
            Rule=rule_name,
            EventBusName=event_bus_name,
            Targets=[
                {
                    "Id": f"{rule_name}-target",
                    "Arn": queue_arn,
                    # "SqsParameters": {
                    #     "MessageGroupId": "default",  # Required for FIFO queues
                    # },
                    "InputTransformer": {
                        "InputPathsMap": {"detail": "$.detail"},
                        "InputTemplate": f'{{"Asset": <detail>, "StateMachineArn": "{state_machine_arn}"}}',
                    },
                }
            ],
        )

        # Add target (SQS queue)
        # eventbridge.put_targets(
        #     Rule=rule_name,
        #     EventBusName=event_bus_name,
        #     Targets=[
        #         {
        #             "Id": f"{rule_name}-target",
        #             "Arn": queue_arn,
        #             "InputTransformer": {
        #                 "InputPathsMap": {"detail": "$.detail"},
        #                 "InputTemplate": f'{{"Asset": <detail>, "StateMachineArn": "{state_machine_arn}"}}',
        #             },
        #         }
        #     ],
        # )

        return response["RuleArn"]
    except Exception as e:
        logger.error(f"Failed to create EventBridge rule: {str(e)}")
        raise


def create_stepfunction_role(
    role_name: str, queue_arn: str, tags: dict, lambda_arns: list
) -> str:
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
                    "Resource": lambda_arns,
                }
            ],
        }

        eventbridge_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["events:PutEvents"],
                    "Resource": [
                        f"arn:aws:events:{os.environ['AWS_REGION']}:{os.environ['AWS_ACCOUNT_ID']}:event-bus/{os.environ['INGEST_EVENT_BUS']}"
                    ],
                }
            ],
        }

        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}-lambda-policy",
            PolicyDocument=json.dumps(lambda_policy),
        )

        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}-eventbridge-policy",
            PolicyDocument=json.dumps(eventbridge_policy),
        )

        return response["Role"]["Arn"]
    except Exception as e:
        logger.error(f"Failed to create IAM role: {str(e)} {lambda_policy}")
        raise


def modify_trigger_lambda_role(
    role_name: str, queue_arn: str, state_machine_name: str, tags: dict, unique_id: str
) -> str:
    """
    Modify the IAM role for the trigger Lambda by adding a new inline policy with a unique name.
    The unique_id parameter (e.g. pipeline ID) ensures that concurrent invocations do not overwrite each other.
    """
    try:
        # Check if the role exists
        try:
            response = iam_client.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]
            logger.info(f"Role {role_name} already exists. Modifying...")
        except iam_client.exceptions.NoSuchEntityException:
            raise Exception(f"Role {role_name} does not exist")

        # Define the new policy statements
        new_sqs_statement = {
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

        new_step_functions_statement = {
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

        # Use a unique inline policy name by appending the unique_id
        unique_policy_name = f"{role_name}-policy-{unique_id}"
        new_policy_doc = {
            "Version": "2012-10-17",
            "Statement": [new_sqs_statement, new_step_functions_statement],
        }

        # Put the new inline policy on the role
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=unique_policy_name,
            PolicyDocument=json.dumps(new_policy_doc),
        )

        logger.info(f"Added inline policy {unique_policy_name} to role {role_name}")
        return role_arn

    except Exception as e:
        logger.error(f"Failed to modify IAM role: {str(e)}")
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
    state_machine_name: str,
) -> tuple[bool, str]:
    """Check if any of the resources already exist"""
    try:
        # Check SQS Queue
        # try:
        #     sqs_client.get_queue_url(QueueName=f"{queue_name}.fifo")
        #     return True, f"SQS Queue {queue_name}.fifo already exists"
        # except sqs_client.exceptions.QueueDoesNotExist:
        #     pass
        try:
            sqs_client.get_queue_url(QueueName=queue_name)
            return True, f"SQS Queue {queue_name} already exists"
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
        # for lambda_name in lambda_names:
        #     try:
        #         lambda_client.get_function(FunctionName=lambda_name)
        #         if check_event_source_mappings(lambda_name):
        #             return (
        #                 True,
        #                 f"Lambda Function {lambda_name} with event source mappings already exists",
        #             )
        #         return True, f"Lambda Function {lambda_name} already exists"
        #     except lambda_client.exceptions.ResourceNotFoundException:
        #         pass

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
                if isinstance(resource_id, dict):
                    eventbridge.delete_rule(
                        Name=resource_id["rule_name"],
                        EventBusName=resource_id["eventbus_name"],
                    )
                else:
                    eventbridge.delete_rule(Name=resource_id)
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


def create_iam_lambda_s3_dynamo_rw_policy():
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
            # {
            #     "Effect": "Allow",
            #     "Action": ["s3:GetObject"],
            #     "Resource": [f"arn:aws:s3:::{bucket}/*" for bucket in connector_buckets]
            #     + [f"arn:aws:s3:::{bucket}" for bucket in connector_buckets],
            # },
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": [
                    f"arn:aws:s3:::*",
                    f"arn:aws:s3:::*/*",
                ],
            },
            {
                "Effect": "Allow",
                "Action": [
                    "kms:Encrypt",
                    "kms:Decrypt",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                    "kms:DescribeKey",
                ],
                "Resource": ["*"],
            },
            {
                "Effect": "Allow",
                "Action": ["kms:GenerateDataKey"],
                "Resource": [
                    os.environ["MEDIA_ASSETS_BUCKET_ARN_KMS_KEY"],
                ],
            },
        ],
    }
    return iam_lambda_s3_dynamo_rw_policy


def get_connector_buckets(pipeline_type):

    connector_table = dynamodb.Table(os.environ["CONNECTOR_TABLE"])
    response = connector_table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr("type").eq("s3")
    )

    buckets = []
    for item in response["Items"]:
        if "storageIdentifier" in item:
            buckets.append(item["storageIdentifier"])

    if not buckets:
        raise ValueError("No connectors found. Pipeline creation cannot proceed.")

    return buckets


def update_lambda_function_role(function_name: str, role_arn: str, max_retries=5):
    lambda_client = boto3.client("lambda")
    for attempt in range(max_retries):
        try:
            lambda_client.update_function_configuration(
                FunctionName=function_name, Role=role_arn
            )
            logger.info(
                f"Successfully updated role for Lambda function {function_name}"
            )
            return
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceConflictException":
                if attempt < max_retries - 1:
                    wait_time = (2**attempt) * 5  # exponential backoff
                    logger.warning(
                        f"Update in progress, retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Failed to update role for Lambda function {function_name} after {max_retries} attempts: {str(e)}"
                    )
                    raise
            else:
                logger.error(
                    f"Failed to update role for Lambda function {function_name}: {str(e)}"
                )
                raise


def create_event_source_mapping(lambda_client, queue_arn, pipeline_trigger_lambda_arn):
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(
                f"Creating event source mapping (Attempt {attempt + 1}/{MAX_RETRIES})"
            )
            event_source_mapping = lambda_client.create_event_source_mapping(
                EventSourceArn=queue_arn,
                FunctionName=pipeline_trigger_lambda_arn,
                Enabled=True,
                FunctionResponseTypes=['ReportBatchItemFailures']
                # BatchSize=1000, #default is 100.
            )
            logger.info("Event source mapping created successfully")
            return event_source_mapping
        except lambda_client.exceptions.InvalidParameterValueException as e:
            if (
                "The function execution role does not have permissions to call ReceiveMessage on SQS"
                in str(e)
            ):
                logger.warning(
                    f"Attempt {attempt + 1}/{MAX_RETRIES}: Lambda function lacks SQS permissions. Retrying..."
                )
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Invalid parameter value: {str(e)}")
                raise
        except ClientError as e:
            logger.error(
                f"AWS API error on attempt {attempt + 1}/{MAX_RETRIES}: {str(e)}"
            )
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(RETRY_DELAY)

    logger.error(f"Failed to create event source mapping after {MAX_RETRIES} attempts")
    raise Exception(
        f"Failed to create event source mapping after {MAX_RETRIES} attempts"
    )


@app.post("/pipelines")
def create_pipeline(createpipeline: S3Pipeline) -> dict:
    print("Received pipeline definition:", createpipeline.dict())
    resources_to_delete = []

    with ExitStack() as stack:
        logger.info(f"Received create pipeline request: {createpipeline}")
        stack.callback(rollback_resources, resources_to_delete)
        # connector_buckets = None
        try:
            logger.info("Starting pipeline creation process")

            # try:
            #     connector_buckets = get_connector_buckets(createpipeline.type)
            # except ValueError as e:
            #     logger.error(f"Failed to create pipeline: {str(e)}")
            #     return {
            #         "status": "400",
            #         "message": str(e),
            #         "data": {"error": str(e)},
            #     }

            global_prefix = os.environ["GLOBAL_PREFIX"]
            logger.info(f"Global prefix: {global_prefix}")
            # Generate names for resources
            pipeline_suffix = createpipeline.name.replace(" ", "-").lower()
            queue_name = f"{global_prefix}-pl-{pipeline_suffix}"
            rule_name = f"{global_prefix}-pl-{pipeline_suffix}-rule"
            sfn_role_name = f"{global_prefix}-pl-sfn-{pipeline_suffix}"

            lambda_s3_dynamo_rw_role_name = (
                f"{global_prefix}-pl-s3_dynamo_rw-lam-{pipeline_suffix}"
            )

            state_machine_name = f"{global_prefix}-pl-{pipeline_suffix}"

            logger.info(
                f"Generated resource names: queue={queue_name}, rule={rule_name}, sfn_role={sfn_role_name}, lambda_roles={lambda_s3_dynamo_rw_role_name}, state_machine={state_machine_name}"
            )

            event_pattern = createpipeline.event_pattern

            # Check if resources exist
            resources_exist, error_message = check_resource_exists(
                createpipeline.name,
                queue_name,
                rule_name,
                sfn_role_name,
                lambda_s3_dynamo_rw_role_name,
                state_machine_name,
            )

            if resources_exist:
                logger.error(error_message)
                return {
                    "status": "409",
                    "message": "Resource conflict",
                    "data": {"error": error_message},
                }

            # Generate unique ID and timestamps
            pipeline_id = str(uuid.uuid4())
            current_time = datetime.utcnow().isoformat(timespec="seconds")
            logger.info(f"Generated pipeline ID: {pipeline_id}")
            deployment_bucket = os.environ.get("IAC_ASSETS_BUCKET")
            pipeline_trigger_lambda_arn = os.environ.get("PIPELINE_TRIGGER_LAMBDA_ARN")
            parent_event_bus_name = os.environ.get("INGEST_EVENT_BUS")
            logger.info(
                f"Environment variables: deployment_bucket={deployment_bucket}, pipeline_trigger_lambda_arn={pipeline_trigger_lambda_arn}, parent_event_bus_name={parent_event_bus_name}"
            )
            # connector_table_name = os.environ.get("CONNECTOR_TABLE_NAME")
            # Common tags for all resources
            tags = {
                "medialake": "true",
                "pipeline_id": pipeline_id,
                "pipeline_name": createpipeline.name,
            }
            logger.info(f"Resource tags: {tags}")

            # Create SQS Sandard Queue
            queue_name = f"medialake-pipeline-{pipeline_suffix}"
            try:
                # logger.info(f"Creating SQS FIFO queue: {queue_name}")
                logger.info(f"Creating SQS standard queue: {queue_name}")
                # queue_url, queue_arn = create_sqs_fifo_queue(queue_name, tags)
                queue_url, queue_arn = create_sqs_standard_queue(queue_name, tags)
                resources_to_delete.append(("sqs", queue_url))
            except sqs_client.exceptions.QueueDeletedRecently as e:
                logger.error(f"Failed to create pipeline: {str(e)}")
                # return {
                #     "status": "400",
                #     "message": "SQS FIFO queue creation failed: 60-second wait required after deletion before reusing name.",
                #     "data": {
                #         "error": "You must wait 60 seconds after deleting a queue before you can create another with the same name."
                #     },
                # }
                return {
                    "status": "400",
                    "message": "SQS standard queue creation failed.",
                    "data": {"error": str(e)},
                }

            # Create IAM Role for Lambda and Step Functions
            state_machine_name = f"medialake-pipeline-{pipeline_suffix}"
            logger.info(f"Creating IAM role for Step Functions: {sfn_role_name}")

            # Extract Lambda ARNs from the pipeline definition
            lambda_arns = list(
                set(
                    node["data"]["id"]
                    for node in createpipeline.definition["nodes"]
                    if "id" in node["data"] and node["data"]["id"]
                )
            )

            if not lambda_arns:
                logger.error("No valid Lambda ARNs found in the pipeline definition")
                return {
                    "status": "400",
                    "message": "Invalid pipeline definition: No valid Lambda ARNs found",
                    "data": {
                        "error": "Pipeline must include at least one Lambda function"
                    },
                }

            sfn_role_arn = create_stepfunction_role(
                sfn_role_name, queue_arn, tags, lambda_arns
            )
            resources_to_delete.append(("iam_stepfunction_role", sfn_role_arn))
            logger.info(f"Step Functions IAM role created: {sfn_role_arn}")

            trigger_lambda = lambda_client.get_function(
                FunctionName=pipeline_trigger_lambda_arn
            )
            lambda_trigger_role_arn = trigger_lambda["Configuration"]["Role"]
            lambda_trigger_role_name = lambda_trigger_role_arn.split("/")[-1]

            logger.info(
                f"Modifying IAM role for Lambda trigger: {lambda_trigger_role_name}"
            )

            modify_trigger_lambda_role(
                lambda_trigger_role_name,
                queue_arn,
                state_machine_name,
                tags,
                pipeline_id,  # Unique identifier to prevent overwrites
            )

            logger.info(f"Lambda trigger IAM role modified: {lambda_trigger_role_name}")
            logger.info("Updating Lambda function role")

            if wait_for_lambda_ready(pipeline_trigger_lambda_arn):
                update_lambda_function_role(
                    pipeline_trigger_lambda_arn, lambda_trigger_role_arn
                )
            else:
                logger.error(
                    f"Lambda function {pipeline_trigger_lambda_arn} is not in Active state"
                )
            logger.info("Creating IAM Lambda S3 DynamoDB read-write policy")

            iam_lambda_s3_dynamo_rw_policy = create_iam_lambda_s3_dynamo_rw_policy()
            # print(iam_lambda_s3_dynamo_rw_policy)
            # logger.info("Updating Lambda role permissions for image metadata extractor")

            # update_lambda_role_permissions(
            #     os.environ.get("IMAGE_METADATA_EXTRACTOR_LAMBDA_ARN"),
            #     iam_lambda_s3_dynamo_rw_policy,
            # )
            # logger.info("Updating Lambda role permissions for image proxy")

            # update_lambda_role_permissions(
            #     os.environ.get("IMAGE_PROXY_LAMBDA_ARN"), iam_lambda_s3_dynamo_rw_policy
            # )

            for lambda_arn in lambda_arns:
                update_lambda_role_permissions(
                    lambda_arn,
                    iam_lambda_s3_dynamo_rw_policy,
                )
                logger.info(f"Updating Lambda role permissions for {lambda_arn}")

            logger.info("Creating new bucket policy")

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
                # "Condition": {
                #     "ArnLike": {"aws:SourceArn": os.environ["IMAGE_PROXY_LAMBDA_ARN"]}
                # },
            }
            result = s3_client.get_bucket_policy(
                Bucket=os.environ["MEDIA_ASSETS_BUCKET_NAME"]
            )
            current_policy = json.loads(result["Policy"])
            current_policy["Statement"].append(new_bucket_policy)
            updated_policy = json.dumps(current_policy)
            logger.info(f"Current bucket policy: {json.dumps(current_policy)}")

            # print(updated_policy)
            # Do not JSON dump again, as it's already a JSON string
            logger.info("Putting updated bucket policy")

            s3_client.put_bucket_policy(
                Bucket=os.environ["MEDIA_ASSETS_BUCKET_NAME"],
                Policy=updated_policy,
            )

            # Get state machine definition
            logger.info("Getting state machine definition")

            output_bucket_name = os.environ.get("MEDIA_ASSETS_BUCKET_NAME")
            state_machine_definition = get_state_machine_definition(
                createpipeline.definition, output_bucket_name, createpipeline.name
            )
            logger.info("Creating state machine")

            state_machine_arn = create_state_machine(
                state_machine_name, sfn_role_arn, state_machine_definition, tags
            )
            resources_to_delete.append(("step_function", state_machine_arn))

            # Create EventBridge rule
            rule_name = f"medialake-pipeline-{pipeline_suffix}-rule"
            logger.info(f"Creating EventBridge rule: {rule_name}")
            rule_arn = create_eventbridge_rule(
                rule_name,
                parent_event_bus_name,
                queue_arn,
                event_pattern,
                state_machine_arn,
                tags,
            )
            resources_to_delete.append(
                (
                    "eventbridge_rule",
                    {"rule_name": rule_name, "eventbus_name": parent_event_bus_name},
                )
            )
            logger.info(f"EventBridge rule created: {rule_arn}")

            if not wait_for_iam_role_propagation(iam_client, sfn_role_name):
                raise Exception(f"Role {lambda_trigger_role_name} is not ready in time")
            # Add SQS trigger to Lambda
            time.sleep(20)
            logger.info("Creating event source mapping")

            try:
                event_source_mapping = create_event_source_mapping(
                    lambda_client, queue_arn, pipeline_trigger_lambda_arn
                )
                resources_to_delete.append(
                    ("event_source_mapping", event_source_mapping["UUID"])
                )
            except Exception as e:
                logger.exception(f"Failed to create event source mapping: {str(e)}")
                return {
                    "status": "500",
                    "message": "Failed to create pipeline: Could not create event source mapping",
                    "data": {"error": str(e)},
                }

            # Save pipeline details to DynamoDB
            pipeline_table_name = os.environ.get("PIPELINES_TABLE_NAME")
            if not pipeline_table_name:
                logger.error("PIPELINES_TABLE_NAME environment variable not set")

                raise ValueError("PIPELINES_TABLE_NAME environment variable not set")

            # Convert the definition's float values to Decimal
            logger.info("Converting definition's float values to Decimal")

            definition = float_to_decimal(createpipeline.definition)

            pipeline_table = dynamodb.Table(pipeline_table_name)
            logger.debug("Preparing pipeline item for DynamoDB")

            pipeline_item = {
                "id": pipeline_id,
                "name": createpipeline.name,
                "system": createpipeline.system,
                "type": createpipeline.type,
                "createdAt": current_time,
                "updatedAt": current_time,
                "definition": definition,
                # "eventPattern": event_pattern,
                "queueUrl": queue_url,
                "queueArn": queue_arn,
                "triggerLambdaArn": pipeline_trigger_lambda_arn,
                "stateMachineArn": state_machine_arn,
                "sfnRoleArn": sfn_role_arn,
                "dependentResources": resources_to_delete,
            }
            logger.info(f"Pipeline item: {json.dumps(pipeline_item, default=str)}")

            logger.info("Putting item in DynamoDB")

            pipeline_table.put_item(Item=pipeline_item)

            logger.info(
                f"Created pipeline '{createpipeline.name}' with ID {pipeline_id}"
            )
            stack.pop_all()
            logger.info("Pipeline creation successful")

            return {
                "status": "200",
                "message": "Pipeline created successfully",
                "data": {
                    "id": pipeline_id,
                },
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
    print(json.dumps(event))

    # Check if DefinitionFile is present in the event
    if "body" in event:
        pipeline_definition = json.loads(event["body"])
    elif "definitionFile" in event:
        try:
            # Extract bucket and key from DefinitionFile
            definition_file = event["definitionFile"]
            bucket = definition_file["bucket"]
            key = definition_file["key"]

            # Read the JSON file from S3
            response = s3_client.get_object(Bucket=bucket, Key=key)
            file_content = response["Body"].read().decode("utf-8")

            # Parse the JSON content
            pipeline_definition = json.loads(file_content)

            # Update the event with the pipeline definition
            event["body"] = json.dumps(pipeline_definition)

        except Exception as e:
            logger.error(f"Failed to read pipeline definition from S3: {str(e)}")
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "status": "400",
                        "message": "Failed to read pipeline definition from S3",
                        "data": {"error": str(e)},
                    }
                ),
            }
    else:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "status": "400",
                    "message": "Invalid input: missing pipeline definition",
                    "data": {},
                }
            ),
        }

    return app.resolve(event, context)