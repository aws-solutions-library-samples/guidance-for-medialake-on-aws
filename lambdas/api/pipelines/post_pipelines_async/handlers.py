import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.api_gateway import (
    APIGatewayRestResolver,
    CORSConfig,
)
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from models import PipelineDefinition

# Initialize AWS Lambda Powertools utilities
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="PostPipelineAsyncHandler")

# Import environment variables
PIPELINES_TABLE = os.environ.get("PIPELINES_TABLE")
if not PIPELINES_TABLE:
    logger.error("PIPELINES_TABLE environment variable is not set")


# DynamoDB operations
def get_pipeline_by_name(pipeline_name: str) -> Dict[str, Any]:
    """
    Get pipeline record from DynamoDB by name.

    Args:
        pipeline_name: Name of the pipeline to look up

    Returns:
        Pipeline record if found, None otherwise
    """
    logger.info(f"Looking up pipeline with name: {pipeline_name}")

    if not PIPELINES_TABLE:
        logger.error("PIPELINES_TABLE environment variable is not set")
        return None

    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(PIPELINES_TABLE)

        # Scan for items with matching name
        response = table.scan(
            FilterExpression="#n = :name",
            ExpressionAttributeNames={"#n": "name"},
            ExpressionAttributeValues={":name": pipeline_name},
        )
        items = response.get("Items", [])
        if items:
            pipeline = items[0]
            return pipeline
        return None
    except Exception as e:
        logger.error(f"Error looking up pipeline: {e}")
        return None


def get_pipeline_by_id(pipeline_id: str) -> Dict[str, Any]:
    """
    Get pipeline record from DynamoDB by ID.

    Args:
        pipeline_id: ID of the pipeline to look up

    Returns:
        Pipeline record if found, None otherwise
    """
    logger.info(f"Looking up pipeline with ID: {pipeline_id}")

    if not PIPELINES_TABLE:
        logger.error("PIPELINES_TABLE environment variable is not set")
        return None

    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(PIPELINES_TABLE)

        response = table.get_item(Key={"id": pipeline_id})
        pipeline = response.get("Item")
        if pipeline:
            logger.info(f"Found pipeline with ID: {pipeline_id}")
            return pipeline
        logger.info(f"No pipeline found with ID: {pipeline_id}")
        return None
    except Exception as e:
        logger.error(f"Error looking up pipeline: {e}")
        return None


def create_pipeline_record(
    pipeline: Any, execution_arn: str = None, deployment_status: str = "CREATING"
) -> str:
    """
    Create a new pipeline record in DynamoDB with initial status.

    Args:
        pipeline: Pipeline definition object
        execution_arn: Optional ARN of the Step Function execution
        deployment_status: Initial deployment status

    Returns:
        ID of the created pipeline record
    """
    import uuid
    from datetime import datetime

    logger.info(f"Creating pipeline record with status: {deployment_status}")

    if not PIPELINES_TABLE:
        logger.error("PIPELINES_TABLE environment variable is not set")
        raise ValueError("PIPELINES_TABLE environment variable is not set")

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(PIPELINES_TABLE)

    pipeline_id = str(uuid.uuid4())
    now_iso = datetime.utcnow().isoformat()

    item = {
        "id": pipeline_id,
        "createdAt": now_iso,
        "updatedAt": now_iso,
        "definition": pipeline.dict(),
        "dependentResources": [],  # Will be populated later
        "name": pipeline.name,
        "stateMachineArn": "",  # Will be populated later
        "type": "Event Triggered",
        "system": False,
        "deploymentStatus": deployment_status,
    }

    if execution_arn:
        item["executionArn"] = execution_arn

    try:
        table.put_item(Item=item)
        logger.info(f"Successfully created pipeline record with id {pipeline_id}")
        return pipeline_id
    except Exception as e:
        logger.exception(f"Failed to create pipeline record: {e}")
        raise


def update_pipeline_status(
    pipeline_id: str,
    deployment_status: str,
    state_machine_arn: str = None,
    lambda_arns: Dict[str, str] = None,
    eventbridge_rule_arns: Dict[str, str] = None,
    execution_arn: str = None,
) -> None:
    """
    Update the deployment status and optionally resources of a pipeline.

    Args:
        pipeline_id: ID of the pipeline to update
        deployment_status: New deployment status
        state_machine_arn: Optional ARN of the state machine
        lambda_arns: Optional dictionary mapping node IDs to Lambda ARNs
        eventbridge_rule_arns: Optional dictionary mapping node IDs to EventBridge rule ARNs
    """
    from datetime import datetime

    logger.info(f"Updating pipeline {pipeline_id} status to {deployment_status}")

    if not PIPELINES_TABLE:
        logger.error("PIPELINES_TABLE environment variable is not set")
        raise ValueError("PIPELINES_TABLE environment variable is not set")

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(PIPELINES_TABLE)

    now_iso = datetime.utcnow().isoformat()

    update_expr = "SET #status = :status, #up = :updated"
    expr_values = {":status": deployment_status, ":updated": now_iso}
    expr_names = {"#status": "deploymentStatus", "#up": "updatedAt"}

    # Add executionArn if provided
    if execution_arn:
        update_expr += ", #exec = :exec"
        expr_values[":exec"] = execution_arn
        expr_names["#exec"] = "executionArn"

    # Add resources if provided
    dependent_resources = []
    if lambda_arns:
        for node_id, arn in lambda_arns.items():
            if arn:
                dependent_resources.append(["lambda", arn])

        update_expr += ", #res = :res"
        expr_values[":res"] = dependent_resources
        expr_names["#res"] = "dependentResources"

    if state_machine_arn:
        if lambda_arns:
            # Already added dependentResources, just append to it
            dependent_resources.append(["step_function", state_machine_arn])
        else:
            # Need to get existing dependentResources first
            pipeline = get_pipeline_by_id(pipeline_id)
            if pipeline and "dependentResources" in pipeline:
                dependent_resources = pipeline["dependentResources"]
                dependent_resources.append(["step_function", state_machine_arn])
                update_expr += ", #res = :res"
                expr_values[":res"] = dependent_resources
                expr_names["#res"] = "dependentResources"
            else:
                dependent_resources = [["step_function", state_machine_arn]]
                update_expr += ", #res = :res"
                expr_values[":res"] = dependent_resources
                expr_names["#res"] = "dependentResources"

        update_expr += ", #arn = :arn"
        expr_values[":arn"] = state_machine_arn
        expr_names["#arn"] = "stateMachineArn"

    if eventbridge_rule_arns and not lambda_arns:
        # Need to get existing dependentResources first if lambda_arns not provided
        pipeline = get_pipeline_by_id(pipeline_id)
        if pipeline and "dependentResources" in pipeline:
            dependent_resources = pipeline["dependentResources"]

        for node_id, arn in eventbridge_rule_arns.items():
            if arn:
                dependent_resources.append(["eventbridge_rule", arn])

        update_expr += ", #res = :res"
        expr_values[":res"] = dependent_resources
        expr_names["#res"] = "dependentResources"
    elif eventbridge_rule_arns:
        # lambda_arns was provided, so dependentResources is already set up
        for node_id, arn in eventbridge_rule_arns.items():
            if arn:
                dependent_resources.append(["eventbridge_rule", arn])

    try:
        logger.info(f"Updating pipeline {pipeline_id} with expression: {update_expr}")
        logger.info(f"Expression values: {expr_values}")
        logger.info(f"Expression names: {expr_names}")

        table.update_item(
            Key={"id": pipeline_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names,
        )
        logger.info(
            f"Successfully updated pipeline {pipeline_id} status to {deployment_status}"
        )

        # Verify the update
        updated_pipeline = get_pipeline_by_id(pipeline_id)
        logger.info(
            f"Verified pipeline status after update: {updated_pipeline.get('deploymentStatus', 'unknown')}"
        )
    except Exception as e:
        logger.exception(f"Failed to update pipeline status: {e}")
        raise


# Configure CORS and API Gateway resolver
cors_config = CORSConfig(allow_origin="*", allow_headers=["*"])
app = APIGatewayRestResolver(cors=cors_config)

# Get the Step Function ARN from environment variables
PIPELINE_CREATION_STATE_MACHINE_ARN = os.environ.get(
    "PIPELINE_CREATION_STATE_MACHINE_ARN"
)


@app.post("/pipelines")
@tracer.capture_method
def create_pipeline() -> Dict[str, Any]:
    """
    Start a pipeline creation process asynchronously.

    Returns:
        API Gateway response with the execution ARN and pipeline ID
    """
    try:
        logger.info("Received request to create/update a pipeline")
        request_data = app.current_event.json_body

        # Validate the pipeline definition
        pipeline = PipelineDefinition(**request_data)
        logger.debug(f"Pipeline configuration: {pipeline}")

        pipeline_name = pipeline.name
        logger.info(f"Processing pipeline: {pipeline_name} - {pipeline.description}")

        # Check if this is an update operation by looking for pipeline_id in the request
        pipeline_id = request_data.get("pipeline_id")

        if pipeline_id:
            # This is an update operation, check if the pipeline exists
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
            logger.info(f"Updating existing pipeline with ID: {pipeline_id}")
        else:
            # This is a new pipeline creation, check if the name already exists
            existing_pipeline = get_pipeline_by_name(pipeline_name)
            if existing_pipeline:
                error_body = {
                    "error": "Pipeline name already exists",
                    "details": f"A pipeline with the name '{pipeline_name}' already exists. Please use a different name or provide the pipeline_id to update it.",
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

            # For new pipelines, create a pipeline record with initial status
            pipeline_id = create_pipeline_record(pipeline, None, "CREATING")

            # Add pipeline_id to the request data
            request_data["pipeline_id"] = pipeline_id

        # Start the Step Function execution
        sfn_client = boto3.client("stepfunctions")
        response = sfn_client.start_execution(
            stateMachineArn=PIPELINE_CREATION_STATE_MACHINE_ARN,
            input=json.dumps(request_data),
        )

        execution_arn = response["executionArn"]
        logger.info(f"Started Step Function execution: {execution_arn}")

        try:
            # Update the pipeline record with the execution ARN
            update_pipeline_status(
                pipeline_id, "CREATING", None, None, None, execution_arn
            )

            # Return a response to the client
            response_body = {
                "message": f"Pipeline creation started for '{pipeline_name}'",
                "pipeline_id": pipeline_id,
                "execution_arn": execution_arn,
                "status": "CREATING",
                "pipeline_name": pipeline_name,
            }
        except ValueError as ve:
            # Handle the case when PIPELINES_TABLE is not set
            error_body = {"error": "Configuration error", "details": str(ve)}
            logger.error(f"Configuration error: {ve}")
            return {
                "statusCode": 500,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps(error_body),
            }

        return {
            "statusCode": 202,  # Accepted
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(response_body),
        }

    except Exception as e:
        logger.exception("Error starting pipeline creation")
        error_body = {"error": "Failed to start pipeline creation", "details": str(e)}

        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(error_body),
        }


@app.get("/pipelines/status/{executionArn}")
@tracer.capture_method
def get_pipeline_status(executionArn: str) -> Dict[str, Any]:
    """
    Get the status of a pipeline creation.

    Args:
        executionArn: ARN of the Step Function execution

    Returns:
        API Gateway response with the execution status and pipeline record
    """
    try:
        logger.info(f"Checking status of execution: {executionArn}")

        # Get the execution status
        sfn_client = boto3.client("stepfunctions")
        sfn_response = sfn_client.describe_execution(executionArn=executionArn)

        status = sfn_response["status"]
        output = (
            json.loads(sfn_response.get("output", "{}"))
            if "output" in sfn_response
            else {}
        )

        logger.info(f"Step Function status: {status}")
        logger.info(f"Step Function output: {output}")

        # Find the pipeline record by execution ARN
        pipeline_record = None
        try:
            if not PIPELINES_TABLE:
                logger.error("PIPELINES_TABLE environment variable is not set")
                raise ValueError("PIPELINES_TABLE environment variable is not set")

            dynamodb = boto3.resource("dynamodb")
            table = dynamodb.Table(PIPELINES_TABLE)

            logger.info(f"Scanning for pipeline with executionArn: {executionArn}")
            pipeline_response = table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr("executionArn").eq(
                    executionArn
                )
            )

            logger.info(f"Scan result: {pipeline_response}")

            if pipeline_response.get("Items"):
                pipeline_record = pipeline_response["Items"][0]
                logger.info(f"Found pipeline record: {pipeline_record}")

                # Update pipeline status based on Step Function status if needed
                current_status = pipeline_record.get("deploymentStatus", "CREATING")
                new_status = current_status
                logger.info(f"Current status: {current_status}")

                logger.info(
                    f"Step Function status: {status}, determining new pipeline status"
                )
                if status == "RUNNING":
                    # Keep the current status, which should be more specific
                    logger.info("Step Function is RUNNING, keeping current status")
                elif status == "SUCCEEDED":
                    new_status = "DEPLOYED"
                    logger.info("Step Function SUCCEEDED, setting status to DEPLOYED")
                elif status == "FAILED":
                    new_status = "FAILED"
                    logger.info("Step Function FAILED, setting status to FAILED")
                elif status == "TIMED_OUT":
                    new_status = "FAILED"
                    logger.info("Step Function TIMED_OUT, setting status to FAILED")
                elif status == "ABORTED":
                    new_status = "FAILED"
                    logger.info("Step Function ABORTED, setting status to FAILED")

                logger.info(f"New status determined: {new_status}")

                # Update the status if it changed
                if new_status != current_status:
                    logger.info(
                        f"Status changed from {current_status} to {new_status}, updating database"
                    )
                    try:
                        update_pipeline_status(pipeline_record["id"], new_status)
                        pipeline_record["deploymentStatus"] = new_status
                        logger.info(
                            f"Updated pipeline record with new status: {new_status}"
                        )
                    except ValueError as ve2:
                        logger.error(f"Failed to update pipeline status: {ve2}")
                else:
                    logger.info(
                        f"Status unchanged ({current_status}), no update needed"
                    )
        except ValueError as ve:
            logger.error(f"Configuration error: {ve}")

        # Return both the Step Function status and the pipeline record
        response_body = {
            "execution_arn": executionArn,
            "step_function_status": status,
            "step_function_output": output,
            "pipeline": pipeline_record,
        }

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(response_body),
        }

    except Exception as e:
        logger.exception("Error checking pipeline status")
        error_body = {"error": "Failed to check pipeline status", "details": str(e)}

        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(error_body),
        }


@app.get("/pipelines/pipeline/{pipelineId}")
@tracer.capture_method
def get_pipeline_by_id_handler(pipelineId: str) -> Dict[str, Any]:
    """
    Get a pipeline by ID.

    Args:
        pipelineId: ID of the pipeline

    Returns:
        API Gateway response with the pipeline record
    """
    try:
        logger.info(f"Getting pipeline with ID: {pipelineId}")

        try:
            pipeline = get_pipeline_by_id(pipelineId)
            if not pipeline:
                return {
                    "statusCode": 404,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                    },
                    "body": json.dumps({"error": "Pipeline not found"}),
                }
        except ValueError as ve:
            # Handle the case when PIPELINES_TABLE is not set
            error_body = {"error": "Configuration error", "details": str(ve)}
            logger.error(f"Configuration error: {ve}")
            return {
                "statusCode": 500,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps(error_body),
            }

        # If the pipeline has an execution ARN, get the Step Function status
        execution_status = None
        if "executionArn" in pipeline:
            try:
                sfn_client = boto3.client("stepfunctions")
                sfn_response = sfn_client.describe_execution(
                    executionArn=pipeline["executionArn"]
                )
                execution_status = sfn_response["status"]
            except Exception as e:
                logger.warning(f"Failed to get execution status: {e}")

        response_body = {"pipeline": pipeline, "execution_status": execution_status}

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(response_body),
        }

    except Exception as e:
        logger.exception("Error getting pipeline")
        error_body = {"error": "Failed to get pipeline", "details": str(e)}

        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(error_body),
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    AWS Lambda handler entry point.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    logger.info("Lambda handler invoked", extra={"event": event})
    response = app.resolve(event, context)
    logger.info(f"Returning response from lambda_handler: {response}")
    return response
