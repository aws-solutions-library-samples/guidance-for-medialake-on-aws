import json
from typing import Any, Dict

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from dynamodb_operations import (
    create_pipeline_record,
    get_pipeline_by_id,
    get_pipeline_by_name,
    store_pipeline_info,
    update_pipeline_status,
)
from eventbridge import create_eventbridge_rule, delete_eventbridge_rule
from graph_utils import GraphAnalyzer
from lambda_operations import create_lambda_function
from models import PipelineDefinition
from s3_loader import load_pipeline_from_s3
from step_functions_builder import build_step_function_definition, create_step_function

# Initialize AWS Lambda Powertools utilities
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="PostPipeline")


def transform_pipeline_data(pipeline_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform pipeline data to match the expected format for PipelineDefinition.

    This function:
    1. Converts numeric width and height values to strings
    2. Adds an 'id' field to each node's data object based on the nodeId field

    Args:
        pipeline_data: The pipeline data to transform

    Returns:
        The transformed pipeline data
    """
    logger.info("Transforming pipeline data to match expected format")

    # Make a deep copy to avoid modifying the original
    transformed_data = json.loads(json.dumps(pipeline_data))

    # Transform nodes
    if (
        "configuration" in transformed_data
        and "nodes" in transformed_data["configuration"]
    ):
        for node in transformed_data["configuration"]["nodes"]:
            # Convert width and height to strings
            if "width" in node and isinstance(node["width"], int):
                node["width"] = str(node["width"])
            if "height" in node and isinstance(node["height"], int):
                node["height"] = str(node["height"])

            # Add id field to data object based on nodeId
            if "data" in node and "nodeId" in node["data"] and "id" not in node["data"]:
                node["data"]["id"] = node["data"]["nodeId"]

    logger.info("Pipeline data transformation complete")
    return transformed_data


def parse_pipeline_definition(event: Dict[str, Any]) -> PipelineDefinition:
    """
    Parse pipeline definition from event input.

    This function handles:
    1. Direct pipeline definitions at the top level
    2. Pipeline definitions wrapped in a "body" field (API Gateway style)
    3. Pipeline definitions stored in S3 (referenced by definitionFile and loadFromS3 flag)
    """
    logger.info("Parsing pipeline definition from event")
    logger.info(f"Event: {event}")

    # Check if we should load from S3
    if event.get("loadFromS3") is True and "definitionFile" in event:
        logger.info("Loading pipeline definition from S3")
        definition_file = event.get("definitionFile", {})
        bucket = definition_file.get("bucket")
        key = definition_file.get("key")

        if not bucket or not key:
            raise ValueError("Missing bucket or key in definitionFile")

        logger.info(f"Loading pipeline definition from S3: {bucket}/{key}")
        pipeline_data = load_pipeline_from_s3(bucket, key)
        logger.info(f"Successfully loaded pipeline definition from S3")

        # Transform the pipeline data to match the expected format
        transformed_data = transform_pipeline_data(pipeline_data)
        return PipelineDefinition(**transformed_data)

    # Check if the event has the required pipeline fields at the top level
    if all(key in event for key in ["name", "description", "configuration"]):
        logger.info("Pipeline definition found at top level of event")
        # Transform the pipeline data to match the expected format
        transformed_data = transform_pipeline_data(event)
        pipeline = PipelineDefinition(**transformed_data)
    else:
        # Try to extract from body field (API Gateway style)
        logger.info("Trying to extract pipeline definition from event body")
        body_str = event.get("body", "{}")
        body = body_str if isinstance(body_str, dict) else json.loads(body_str)
        # Transform the pipeline data to match the expected format
        transformed_body = transform_pipeline_data(body)
        pipeline = PipelineDefinition(**transformed_body)

    logger.debug(f"Parsed pipeline definition: {pipeline}")
    return pipeline


def create_pipeline(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create or update a pipeline based on the provided configuration.

    Args:
        event: Lambda event containing the pipeline definition

    Returns:
        A response dict with statusCode, headers, and body
    """
    try:
        logger.info("Received request to create/update a pipeline")
        # Use our helper to extract the pipeline configuration.
        pipeline = parse_pipeline_definition(event)
        logger.debug(f"Pipeline configuration: {pipeline}")

        pipeline_name = pipeline.name
        logger.info(f"Processing pipeline: {pipeline_name} - {pipeline.description}")

        # Check if pipeline_id is provided in the event
        pipeline_id = event.get("pipeline_id")

        # If pipeline_id is provided, this is an update operation
        if pipeline_id:
            logger.info(
                f"Using provided pipeline_id: {pipeline_id} for pipeline update"
            )

            # Get the existing pipeline
            existing_pipeline = get_pipeline_by_id(pipeline_id)
            if not existing_pipeline:
                error_body = {
                    "error": "Pipeline not found",
                    "details": f"No pipeline with ID '{pipeline_id}' exists.",
                }
                logger.info(
                    f"Rejecting pipeline update - ID does not exist: {pipeline_id}"
                )
                return {
                    "statusCode": 404,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                    },
                    "body": json.dumps(error_body),
                }

            # Clean up existing resources before creating new ones
            logger.info(f"Cleaning up existing resources for pipeline: {pipeline_id}")
            for resource_type, resource_arn in existing_pipeline.get(
                "dependentResources", []
            ):
                if resource_type == "eventbridge_rule":
                    rule_name = resource_arn.split("/")[
                        -1
                    ]  # Extract rule name from ARN
                    try:
                        delete_eventbridge_rule(rule_name)
                        logger.info(f"Deleted existing EventBridge rule: {rule_name}")
                    except Exception as e:
                        logger.error(
                            f"Failed to delete EventBridge rule {rule_name}: {e}"
                        )

                if resource_type == "lambda":
                    # Extract function name from ARN
                    function_name = resource_arn.split(":")[-1]
                    try:
                        lambda_client = boto3.client("lambda")
                        lambda_client.delete_function(FunctionName=function_name)
                        logger.info(
                            f"Deleted existing Lambda function: {function_name}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to delete Lambda function {function_name}: {e}"
                        )

                if resource_type == "step_function":
                    # Extract state machine name from ARN
                    state_machine_name = resource_arn.split(":")[-1]
                    try:
                        delete_step_function(state_machine_name)
                        logger.info(
                            f"Deleted existing Step Function: {state_machine_name}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to delete Step Function {state_machine_name}: {e}"
                        )
        # If pipeline_id is not provided, check if a pipeline with this name already exists
        else:
            existing_pipeline = get_pipeline_by_name(pipeline_name)
            if existing_pipeline:
                error_body = {
                    "error": "Pipeline name already exists",
                    "details": f"A pipeline with the name '{pipeline_name}' already exists. Please use a different name or update the existing pipeline.",
                }
                logger.info(
                    f"Rejecting pipeline creation - name already exists: {pipeline_name}"
                )
                return {
                    "statusCode": 400,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                    },
                    "body": json.dumps(error_body),
                }

        # No execution_uuid generation

        # If pipeline_id is not provided, create a new pipeline record
        if not pipeline_id:
            # Create new pipeline record with initial status
            pipeline_id = create_pipeline_record(pipeline, None, "INITIALIZING")
            logger.info(f"Created new pipeline record with ID: {pipeline_id}")

        try:
            # Update status to indicate validation phase
            update_pipeline_status(pipeline_id, "VALIDATING PIPELINE")
            logger.info(f"Validating pipeline configuration for {pipeline_name}")

            # Update status to indicate resource creation phase
            update_pipeline_status(pipeline_id, "CREATING RESOURCES")
            logger.info(f"Starting resource creation for pipeline {pipeline_name}")

            lambda_arns = {}
            lambda_role_arns = {}
            service_role_arns = {}  # Dictionary to collect service roles
            total_nodes = len(pipeline.configuration.nodes)
            processed_nodes = 0

            # Create a graph analyzer to identify first and last lambdas
            graph_analyzer = GraphAnalyzer(pipeline)
            graph_analyzer.analyze()
            first_lambda_node_id, last_lambda_node_id = (
                graph_analyzer.find_first_and_last_lambdas()
            )

            logger.info(f"Identified first lambda node: {first_lambda_node_id}")
            logger.info(f"Identified last lambda node: {last_lambda_node_id}")

            for node in pipeline.configuration.nodes:
                processed_nodes += 1
                node_id = node.data.id
                node_type = node.data.type.lower()

                # Update status for each node being processed
                update_pipeline_status(
                    pipeline_id, f"PROCESSING NODE {processed_nodes}/{total_nodes}"
                )
                logger.info(
                    f"Processing node {processed_nodes}/{total_nodes} with id: {node_id}, type: {node_type}"
                )
                logger.debug(f"Node details: {node}")

                # Check if this is the first or last lambda
                is_first = node.id == first_lambda_node_id
                is_last = node.id == last_lambda_node_id

                lambda_result = create_lambda_function(
                    pipeline_name, node, is_first=is_first, is_last=is_last
                )

                # Create a specific key for Lambda ARN mapping that distinguishes methods/operations.
                lambda_key = node.data.id
                if (
                    node.data.type.lower() == "integration"
                    and "method" in node.data.configuration
                ):
                    lambda_key = f"{node.data.id}_{node.data.configuration['method']}"
                    if (
                        "operationId" in node.data.configuration
                        and node.data.configuration["operationId"]
                    ):
                        lambda_key = (
                            f"{lambda_key}_{node.data.configuration['operationId']}"
                        )

                if lambda_result:
                    lambda_arns[lambda_key] = lambda_result["function_arn"]
                    lambda_role_arns[lambda_key] = lambda_result["role_arn"]

                    # Collect service roles if available
                    if (
                        "service_roles" in lambda_result
                        and lambda_result["service_roles"]
                    ):
                        if node.data.id not in service_role_arns:
                            service_role_arns[node.data.id] = {}
                        service_role_arns[node.data.id].update(
                            lambda_result["service_roles"]
                        )
                        logger.info(
                            f"Collected {len(lambda_result['service_roles'])} service roles for node {node.data.id}"
                        )

                # Update status after node processing is complete
                if lambda_result:
                    # update_pipeline_status(pipeline_id, f"NODE {node_id} LAMBDA CREATED")
                    logger.info(f"Lambda function created for node {node_id}")
                else:
                    logger.info(f"No Lambda function needed for node {node_id}")

            # Update status after all Lambda functions are created
            update_pipeline_status(pipeline_id, "LAMBDA RESOURCES CREATED")
            logger.info(f"All Lambda functions created for pipeline {pipeline_name}")

            # Log edge processing (if any)
            update_pipeline_status(pipeline_id, "PROCESSING EDGES")
            logger.info(
                f"Processing {len(pipeline.configuration.edges)} edges for pipeline {pipeline_name}"
            )
            for edge in pipeline.configuration.edges:
                logger.info(
                    f"Processing edge: {edge.id} from {edge.source} to {edge.target}"
                )

            settings = pipeline.configuration.settings
            logger.info(
                f"Pipeline settings: AutoStart={settings.autoStart}, RetryAttempts={settings.retryAttempts}, Timeout={settings.timeout}"
            )

            # Build and create/update the state machine
            update_pipeline_status(pipeline_id, "BUILDING STATE MACHINE DEFINITION")
            logger.info(
                f"Building state machine definition for pipeline {pipeline_name}"
            )
            state_machine_definition = build_step_function_definition(
                pipeline, lambda_arns
            )

            update_pipeline_status(pipeline_id, "CREATING STATE MACHINE")
            logger.info(f"Creating state machine for pipeline {pipeline_name}")
            sfn_result = create_step_function(pipeline_name, state_machine_definition)
            state_machine_arn = sfn_result["response"].get("stateMachineArn")
            sfn_role_arn = sfn_result["role_arn"]
            logger.info(f"State machine created with ARN: {state_machine_arn}")

            update_pipeline_status(pipeline_id, "STATE MACHINE CREATED")
            logger.info(
                f"State machine successfully created for pipeline {pipeline_name}"
            )

            # Create EventBridge rules for trigger nodes
            update_pipeline_status(pipeline_id, "CREATING EVENT RULES")
            logger.info(
                f"Creating EventBridge rules for trigger nodes in pipeline {pipeline_name}"
            )
            eventbridge_rule_arns = {}
            eventbridge_role_arns = {}
            trigger_lambda_arns = {}
            sqs_queue_arns = {}
            event_source_mapping_uuids = {}
            trigger_nodes = [
                node
                for node in pipeline.configuration.nodes
                if node.data.type.lower() == "trigger"
            ]
            total_triggers = len(trigger_nodes)
            processed_triggers = 0
            for node in pipeline.configuration.nodes:
                if node.data.type.lower() == "trigger":
                    processed_triggers += 1
                    update_pipeline_status(
                        pipeline_id,
                        f"CREATING EVENT RULE {processed_triggers}/{total_triggers}",
                    )
                    logger.info(
                        f"Creating EventBridge rule for trigger node {processed_triggers}/{total_triggers}: {node.data.id}"
                    )
                    try:
                        rule_result = create_eventbridge_rule(
                            pipeline_name,
                            node,
                            state_machine_arn,
                            active=pipeline.active,
                        )
                        if rule_result:
                            eventbridge_rule_arns[node.data.id] = rule_result[
                                "rule_arn"
                            ]
                            eventbridge_role_arns[node.data.id] = rule_result[
                                "role_arn"
                            ]
                            trigger_lambda_arns[node.data.id] = rule_result[
                                "trigger_lambda_arn"
                            ]
                            sqs_queue_arns[node.data.id] = rule_result["queue_arn"]
                            if rule_result["event_source_mapping_uuid"]:
                                event_source_mapping_uuids[node.data.id] = rule_result[
                                    "event_source_mapping_uuid"
                                ]
                            logger.info(
                                f"Added EventBridge rule {rule_result['rule_arn']} for node {node.data.id} with active={pipeline.active}"
                            )
                    except Exception as e:
                        logger.error(
                            f"Failed to create EventBridge rule for node {node.data.id}: {e}"
                        )

            if total_triggers > 0:
                update_pipeline_status(pipeline_id, "EVENT RULES CREATED")
                logger.info(
                    f"All EventBridge rules created for pipeline {pipeline_name}"
                )
            else:
                logger.info(
                    f"No trigger nodes found in pipeline {pipeline_name}, skipping EventBridge rule creation"
                )

            # Update status before final deployment
            update_pipeline_status(pipeline_id, "FINALIZING DEPLOYMENT")
            logger.info(f"Finalizing deployment for pipeline {pipeline_name}")

            # Update pipeline info in DynamoDB with DEPLOYED status and all resource ARNs
            pipeline_id = store_pipeline_info(
                pipeline,
                state_machine_arn,
                lambda_arns,
                eventbridge_rule_arns,
                pipeline_id,
                active=pipeline.active,  # Pass the active field from the pipeline definition
                sfn_role_arn=sfn_role_arn,
                lambda_role_arns=lambda_role_arns,
                eventbridge_role_arns=eventbridge_role_arns,
                trigger_lambda_arns=trigger_lambda_arns,
                sqs_queue_arns=sqs_queue_arns,
                event_source_mapping_uuids=event_source_mapping_uuids,
                service_role_arns=service_role_arns,
            )

            update_pipeline_status(pipeline_id, "DEPLOYED")
            logger.info(
                f"Pipeline {pipeline_name} successfully deployed with ID: {pipeline_id}"
            )

            # Determine if this was an update or create operation
            operation = "updated" if event.get("pipeline_id") else "created"
            response_body = {
                "message": f"Pipeline {operation} successfully",
                "pipeline_id": pipeline_id,
                "pipeline_name": pipeline_name,
                "state_machine_arn": state_machine_arn,
                "deployment_status": "DEPLOYED",
            }
        except Exception as e:
            # Update pipeline status to FAILED if any error occurs
            update_pipeline_status(pipeline_id, "FAILED")
            raise e
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
        logger.exception("Error creating/updating pipeline")
        error_body = {"error": "Failed to create/update pipeline", "details": str(e)}
        logger.error(f"Returning error response: {error_body}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(error_body),
        }


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for processing pipeline creation/updating.

    Now a regular lambda function that directly invokes the create_pipeline route handler.
    """
    logger.info("Lambda handler invoked", extra={"event": event})
    response = create_pipeline(event)
    logger.info(f"Returning response from lambda_handler: {response}")
    return response
