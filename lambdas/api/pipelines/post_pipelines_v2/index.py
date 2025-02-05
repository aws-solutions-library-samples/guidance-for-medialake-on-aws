import os
import json
import re
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

import boto3
from pydantic import BaseModel, Field

from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.event_handler.api_gateway import (
    APIGatewayRestResolver,
    CORSConfig,
)

# Initialize AWS Lambda Powertools utilities
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="PostPipeliNeV2")

# Configure CORS and API Gateway resolver
cors_config = CORSConfig(allow_origin="*", allow_headers=["*"])
app = APIGatewayRestResolver(cors=cors_config)


# --------
# Data Models (Pydantic)
# --------
class NodeData(BaseModel):
    id: str
    type: str
    label: str
    icon: Dict[str, Any]
    inputTypes: List[str] = Field(default_factory=list)
    outputTypes: List[str] = Field(default_factory=list)
    configuration: Dict[str, Any]


class Node(BaseModel):
    id: str
    type: str
    position: Dict[str, Any]
    width: str
    height: str
    data: NodeData


class Edge(BaseModel):
    source: str
    sourceHandle: Optional[str]
    target: str
    targetHandle: Optional[str]
    id: str
    type: str
    data: Dict[str, Any]


class Settings(BaseModel):
    autoStart: bool
    retryAttempts: int
    timeout: int


class Configuration(BaseModel):
    nodes: List[Node]
    edges: List[Edge]
    settings: Settings


class PipelineDefinition(BaseModel):
    name: str
    description: str
    configuration: Configuration


def parse_pipeline_definition(event: Dict[str, Any]) -> PipelineDefinition:
    logger.info("Parsing pipeline definition from event body")
    body = json.loads(event.get("body", "{}"))
    pipeline = PipelineDefinition(**body)
    logger.debug(f"Parsed pipeline definition: {pipeline}")
    return pipeline


# --------
# Helper Functions
# --------
def get_node_info_from_dynamodb(node_id: str) -> Dict[str, Any]:
    logger.info(f"Retrieving node info from DynamoDB for node_id: {node_id}")
    dynamodb = boto3.resource("dynamodb")
    table_name = os.environ.get("NODE_TABLE")
    if not table_name:
        msg = "Environment variable NODE_TABLE is not set."
        logger.error(msg)
        raise ValueError(msg)
    table = dynamodb.Table(table_name)

    # Adjust the key to match the table schema.
    # For example, if the partition key is "pk" and the sort key is "sk" and your records use a prefix "NODE#":
    key = {"pk": f"NODE#{node_id}", "sk": "INFO"}
    logger.debug(f"Using DynamoDB key: {key}")

    response = table.get_item(Key=key)
    node_info = response.get("Item", {})
    logger.info(f"Retrieved node info for {node_id}: {node_info}")
    return node_info


def sanitize_function_name(pipeline_name, node_label, version):
    # Combine the components
    raw_name = f"{pipeline_name}-{node_label}-{version}".lower()

    # Replace spaces with hyphens
    raw_name = raw_name.replace(" ", "-")

    # Replace non-alphanumeric characters (except hyphens) with underscores
    sanitized_name = re.sub(r"[^a-z0-9-]", "_", raw_name)

    # Ensure the name starts with a letter or number
    sanitized_name = re.sub(r"^[^a-z0-9]+", "", sanitized_name)

    # Truncate to 64 characters (maximum length for Lambda function names)
    sanitized_name = sanitized_name[:64]

    # Ensure the name doesn't end with a hyphen or underscore
    sanitized_name = re.sub(r"[-_]+$", "", sanitized_name)

    return sanitized_name


def create_lambda_function(pipeline_name: str, node: Node) -> str:
    logger.info(f"Creating Lambda function for node: {node.id}")
    lambda_client = boto3.client("lambda")

    account_id = os.environ.get("ACCOUNT_ID")
    if not account_id:
        raise ValueError("ACCOUNT_ID environment variable is not set")

    version = node.data.configuration.get("version", "v1")
    function_name = sanitize_function_name(pipeline_name, node.data.label, version)
    logger.debug(f"Lambda function name generated: {function_name}")

    # Retrieve additional info if needed.
    node_info = get_node_info_from_dynamodb(node.data.id)
    logger.debug(f"Additional node info: {node_info}")

    # Dummy code package; replace with your actual deployment package
    dummy_code = (
        b"def lambda_handler(event, context):\n"
        b"    return {'statusCode': 200, 'body': 'Hello from %s'}"
        % function_name.encode()
    )

    try:
        response = lambda_client.create_function(
            FunctionName=function_name,
            Runtime="python3.9",
            Role=f"arn:aws:iam::{account_id}:role/LambdaExecutionRole",  # Replace with your Lambda execution role ARN
            Handler="lambda_function.lambda_handler",
            Code={"ZipFile": dummy_code},
            Publish=True,
        )
        function_arn = response["FunctionArn"]
        logger.info(
            f"Created Lambda function '{function_name}' with ARN: {function_arn}"
        )
        return function_arn
    except Exception as e:
        logger.exception(f"Failed to create Lambda function {function_name}: {e}")
        raise


def build_step_function_definition(
    pipeline: PipelineDefinition, lambda_arns: Dict[str, str]
) -> Dict[str, Any]:
    logger.info("Building Step Functions state machine definition")
    states = {}
    for node in pipeline.configuration.nodes:
        node_id = node.data.id
        lambda_arn = lambda_arns.get(node_id)
        if not lambda_arn:
            logger.warning(
                f"No Lambda ARN found for node {node_id}; skipping state creation."
            )
            continue

        state_def = {
            "Type": "Task",
            "Resource": lambda_arn,
            "Retry": [
                {
                    "ErrorEquals": ["States.ALL"],
                    "IntervalSeconds": 2,
                    "MaxAttempts": pipeline.configuration.settings.retryAttempts,
                    "BackoffRate": 2.0,
                }
            ],
            "End": True,
        }
        states[node_id] = state_def
        logger.debug(f"State definition for node {node_id}: {state_def}")

    start_at = (
        pipeline.configuration.nodes[0].data.id
        if pipeline.configuration.nodes
        else None
    )
    definition = {
        "Comment": f"State machine for pipeline {pipeline.name}",
        "StartAt": start_at,
        "States": states,
    }
    logger.info(f"Built state machine definition: {definition}")
    return definition


def create_step_function(
    pipeline_name: str, definition: Dict[str, Any]
) -> Dict[str, Any]:
    logger.info(f"Creating Step Functions state machine for pipeline: {pipeline_name}")
    account_id = os.environ.get("ACCOUNT_ID")
    if not account_id:
        raise ValueError("ACCOUNT_ID environment variable is not set")

    sfn_client = boto3.client("stepfunctions")
    try:
        response = sfn_client.create_state_machine(
            name=pipeline_name,
            definition=json.dumps(definition),
            RoleArn=f"arn:aws:iam::{account_id}:role/StepFunctionsExecutionRole",  # Replace with your Step Functions role ARN
        )
        logger.info(f"Created state machine for pipeline '{pipeline_name}': {response}")
        return response
    except Exception as e:
        logger.exception(
            f"Failed to create state machine for pipeline '{pipeline_name}': {e}"
        )
        raise


def store_pipeline_info(
    pipeline: PipelineDefinition, state_machine_arn: str, lambda_arns: Dict[str, str]
) -> None:
    logger.info("Storing pipeline information in DynamoDB")
    dynamodb = boto3.resource("dynamodb")
    table_name = os.environ.get("PIPELINES_TABLE")
    if not table_name:
        msg = "Environment variable PIPELINES_TABLE is not set."
        logger.error(msg)
        raise ValueError(msg)
    table = dynamodb.Table(table_name)

    pipeline_id = str(uuid.uuid4())
    now_iso = datetime.utcnow().isoformat()

    dependent_resources = []
    for node_id, arn in lambda_arns.items():
        dependent_resources.append(["lambda", arn])
        logger.debug(f"Added dependent resource for node {node_id}: lambda -> {arn}")
    dependent_resources.append(["step_function", state_machine_arn])
    logger.debug(
        f"Added dependent resource for state machine: step_function -> {state_machine_arn}"
    )

    # item = {
    #     "id": pipeline_id,
    #     "createdAt": now_iso,
    #     "updatedAt": now_iso,
    #     "definition": pipeline.dict(),
    #     "dependentResources": dependent_resources,
    #     "name": pipeline.name,
    #     "stateMachineArn": state_machine_arn,
    #     # "triggerLambdaArn": os.environ.get("TRIGGER_LAMBDA_ARN", "undefined"),
    #     # "sfnRoleArn": os.environ.get("SFN_ROLE_ARN", "undefined"),
    #     # "queueArn": os.environ.get("QUEUE_ARN", "undefined"),
    #     # "queueUrl": os.environ.get("QUEUE_URL", "undefined"),
    #     # "type": os.environ.get("PIPELINE_TYPE", "default"),
    #     "system": True,
    # }

    # try:
    #     table.put_item(Item=item)
    #     logger.info(f"Successfully stored pipeline info with id {pipeline_id}")
    # except Exception as e:
    #     logger.exception(f"Failed to store pipeline info: {e}")
    #     raise


# --------
# Route Handler
# --------
@app.post("/pipelinesv2")
@tracer.capture_method
def create_pipeline() -> Dict[str, Any]:
    """
    Create a new pipeline based on the provided configuration.
    """
    try:
        logger.info("Received request to create a new pipeline")
        request_data = app.current_event.json_body
        pipeline = PipelineDefinition(**request_data)
        logger.debug(f"Pipeline configuration: {pipeline}")

        pipeline_name = pipeline.name
        logger.info(f"Creating pipeline: {pipeline_name} - {pipeline.description}")

        # Create Lambda functions for each node.
        lambda_arns = {}
        for node in pipeline.configuration.nodes:
            logger.info(f"Processing node with id: {node.id}")
            lambda_arn = create_lambda_function(pipeline_name, node)
            lambda_arns[node.data.id] = lambda_arn

        # Log edge processing (if any).
        for edge in pipeline.configuration.edges:
            logger.info(
                f"Processing edge: {edge.id} from {edge.source} to {edge.target}"
            )

        settings = pipeline.configuration.settings
        logger.info(
            f"Pipeline settings: AutoStart={settings.autoStart}, RetryAttempts={settings.retryAttempts}, Timeout={settings.timeout}"
        )

        # Build and create the state machine.
        state_machine_definition = build_step_function_definition(pipeline, lambda_arns)
        sfn_response = create_step_function(pipeline_name, state_machine_definition)
        state_machine_arn = sfn_response.get("stateMachineArn")
        logger.info(f"State machine ARN: {state_machine_arn}")

        # Store pipeline info in DynamoDB.
        store_pipeline_info(pipeline, state_machine_arn, lambda_arns)

        response_body = {
            "message": "Pipeline created successfully",
            "pipeline_name": pipeline_name,
            "state_machine_arn": state_machine_arn,
        }
        logger.info(f"Returning success response: {response_body}")
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(response_body),
        }

    except Exception as e:
        logger.exception("Error creating pipeline")
        error_body = {"error": "Failed to create pipeline", "details": str(e)}
        logger.error(f"Returning error response: {error_body}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(error_body),
        }


# --------
# Lambda Handler
# --------
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    AWS Lambda handler entry point.
    """
    logger.info("Lambda handler invoked", extra={"event": event})
    response = app.resolve(event, context)
    logger.info(f"Returning response from lambda_handler: {response}")
    return response
