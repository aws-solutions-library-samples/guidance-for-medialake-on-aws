import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import (
    APIGatewayRestResolver,
    CORSConfig,
)
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from models import PipelineDefinition
from pipeline_utils import determine_pipeline_type
from portal_validation import validate_portal_config

# Initialize AWS Lambda Powertools utilities
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="PostPipelineAsyncHandler")

# Import environment variables
PIPELINES_TABLE = os.environ.get("PIPELINES_TABLE")
if not PIPELINES_TABLE:
    logger.error("PIPELINES_TABLE environment variable is not set")


def _api_response(status_code: int, body: Dict[str, Any]) -> Response:
    """Build a Powertools ``Response`` with a JSON body and explicit status.

    Route handlers must return a ``Response`` (not a bare API-Gateway-proxy
    dict) so the ``APIGatewayRestResolver`` honours the intended HTTP status.
    Returning a raw ``{"statusCode": ...}`` dict causes the resolver to treat
    the whole dict as the response *body* and emit HTTP 200, which silently
    hides 4xx validation errors from the client. CORS headers are added by the
    resolver's ``CORSConfig``.
    """
    return Response(
        status_code=status_code,
        content_type=content_types.APPLICATION_JSON,
        body=json.dumps(body),
    )


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
            # Skip pipelines that have been deleted — allow name reuse
            active_items = [
                item
                for item in items
                if item.get("deploymentStatus") not in ("DELETED", "DELETING")
            ]
            if not active_items:
                return None
            pipeline = active_items[0]
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

    # Determine the correct pipeline type based on the pipeline definition
    pipeline_type = determine_pipeline_type(pipeline)
    logger.info(f"Determined pipeline type: {pipeline_type}")

    item = {
        "id": pipeline_id,
        "createdAt": now_iso,
        "updatedAt": now_iso,
        "definition": pipeline.dict(),
        "dependentResources": [],  # Will be populated later
        "name": pipeline.name,
        "stateMachineArn": "",  # Will be populated later
        "type": pipeline_type,
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


def _coerce_json_param(value: Any) -> Any:
    """Coerce a node parameter that may arrive as a JSON string into a value.

    The pipeline editor's generic node-config form serializes object-typed
    parameters (e.g. ``Default Portal Config`` / ``Field Mapping``) as JSON
    *strings*, whereas other callers may pass an already-parsed object. The
    ``manage_portal`` node runtime itself ``json.loads`` these params, so the
    deploy-time check must accept the same string form or it would reject every
    UI-configured node with a spurious "must be an object" error.

    Returns the parsed value (for a JSON string), the original value (for a
    non-string), ``{}`` for an empty/blank string, or the sentinel
    ``_INVALID_JSON`` when a string is present but is not valid JSON.
    """
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return {}
        try:
            return json.loads(stripped)
        except (ValueError, TypeError):
            return _INVALID_JSON
    return value


# Sentinel distinguishing "a string that failed to parse as JSON" from a
# legitimately parsed value (which could itself be falsy, e.g. {} or None).
_INVALID_JSON = object()


def _validate_portal_nodes(request_data: Dict[str, Any]) -> list[dict]:
    """Validate the static config of any ``manage_portal`` nodes in the pipeline.

    Returns a list of ``{"node": <label>, "errors": [...]}`` for nodes whose
    portal config is invalid (empty list = all good). Uses the same shared
    validator as the portal API and the node's runtime check, so a bad slug /
    appearance / page structure is rejected at deploy time with the same
    messages — before any resources are created.

    A node may legitimately receive ``name``/``slug`` from runtime field-mapping
    rather than its static ``Default Portal Config``; in that case we validate
    leniently (format/structure only). With no field mapping, ``name``/``slug``
    are required because nothing else can supply them.

    ``Default Portal Config`` and ``Field Mapping`` may arrive either as objects
    or as JSON strings (the pipeline editor serializes object-typed params as
    strings); both forms are accepted here, mirroring the node runtime.
    """
    problems: list[dict] = []
    configuration = request_data.get("configuration") or {}
    for index, node in enumerate(configuration.get("nodes") or []):
        data = node.get("data") or {}
        if data.get("id") != "manage_portal":
            continue
        label = data.get("label") or data.get("id") or f"node[{index}]"
        params = (data.get("configuration") or {}).get("parameters") or {}

        raw_portal_config = params.get("Default Portal Config")
        if raw_portal_config is None:
            raw_portal_config = {}
        portal_config = _coerce_json_param(raw_portal_config)
        if portal_config is _INVALID_JSON or not isinstance(portal_config, dict):
            problems.append(
                {"node": label, "errors": ["Default Portal Config must be an object"]}
            )
            continue

        # Field mapping is optional; parse it (it may be a JSON string too) so
        # `partial` reflects whether runtime mappings actually exist. A missing,
        # empty, or unparseable mapping is treated as "no mapping" (strict).
        field_mapping = _coerce_json_param(params.get("Field Mapping") or {})
        if field_mapping is _INVALID_JSON or not isinstance(field_mapping, dict):
            field_mapping = {}
        # A Template reference supplies the portal's structure/slug at runtime
        # (the node fetches + expands the template), so the inline Default Portal
        # Config may legitimately be empty. Validate leniently when a Template ID
        # is set — any values that ARE present are still format-checked.
        template_ref_raw = params.get("Template ID")
        template_ref = isinstance(template_ref_raw, str) and bool(
            template_ref_raw.strip()
        )
        partial = bool(field_mapping) or template_ref
        errors = validate_portal_config(portal_config, partial=partial)
        if errors:
            problems.append({"node": label, "errors": errors})

    return problems


def _validate_collection_nodes(request_data: Dict[str, Any]) -> list[dict]:
    """Validate the static config of any ``collection_manager`` nodes.

    Catches the common misconfigurations at deploy time (clear 400) instead of
    at pipeline runtime:
      - create without an ``Owner ID`` (collections need a real owner; we never
        silently fall back to a hidden ``system`` owner), and
      - update / add_assets without a ``Collection ID``.

    Returns ``[{"node": <label>, "errors": [...]}]`` (empty = all good).
    """
    problems: list[dict] = []
    configuration = request_data.get("configuration") or {}
    for index, node in enumerate(configuration.get("nodes") or []):
        data = node.get("data") or {}
        if data.get("id") != "collection_manager":
            continue
        label = data.get("label") or data.get("id") or f"node[{index}]"
        params = (data.get("configuration") or {}).get("parameters") or {}
        operation = str(params.get("Operation") or "create").lower()
        errors: list[str] = []

        if operation == "create":
            if not str(params.get("Owner ID") or "").strip():
                errors.append(
                    "Owner ID is required when the operation is 'create' "
                    "(a collection must have a real owner to be visible/manageable)."
                )
        elif operation in ("update", "add_assets"):
            if not str(params.get("Collection ID") or "").strip():
                errors.append(
                    f"Collection ID is required when the operation is '{operation}'."
                )

        if errors:
            problems.append({"node": label, "errors": errors})

    return problems


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

        # Validate portal-node config up front so a misconfigured manage_portal
        # node fails the deploy with clear, field-level errors before we create
        # any pipeline record or start the creation state machine.
        portal_problems = _validate_portal_nodes(request_data)
        collection_problems = _validate_collection_nodes(request_data)
        node_problems = portal_problems + collection_problems
        if node_problems:
            logger.info(f"Rejecting pipeline - invalid node(s): {node_problems}")
            return _api_response(
                400,
                {
                    "error": "Invalid node configuration",
                    "details": node_problems,
                },
            )

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
                return _api_response(404, error_body)
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
                return _api_response(400, error_body)

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
            return _api_response(500, error_body)

        return _api_response(202, response_body)  # Accepted

    except Exception as e:
        logger.exception("Error starting pipeline creation")
        error_body = {"error": "Failed to start pipeline creation", "details": str(e)}

        return _api_response(500, error_body)


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
