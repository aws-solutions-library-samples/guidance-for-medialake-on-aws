import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import boto3
from aws_lambda_powertools import Logger

from config import NODE_TABLE, PIPELINES_TABLE

# Initialize logger
logger = Logger()


def get_node_info_from_dynamodb(node_id: str) -> Dict[str, Any]:
    """
    Retrieve node information from DynamoDB.

    Args:
        node_id: ID of the node

    Returns:
        Node information dictionary
    """
    logger.info(f"Retrieving node info from DynamoDB for node_id: {node_id}")
    dynamodb = boto3.resource("dynamodb")

    if not NODE_TABLE:
        msg = "Environment variable NODE_TABLE is not set."
        logger.error(msg)
        raise ValueError(msg)

    table = dynamodb.Table(NODE_TABLE)

    # Adjust the key to match the table schema.
    # For example, if the partition key is "pk" and the sort key is "sk" and your records use a prefix "NODE#":
    key = {"pk": f"NODE#{node_id}", "sk": "INFO"}
    logger.debug(f"Using DynamoDB key: {key}")

    response = table.get_item(Key=key)
    node_info = response.get("Item", {})
    logger.info(f"Retrieved node info for {node_id}: {node_info}")
    return node_info


def compare_pipeline_definitions(
    existing_def: Dict[str, Any], new_def: Dict[str, Any]
) -> bool:
    """
    Compare two pipeline definitions to check if they are functionally equivalent.

    Args:
        existing_def: Existing pipeline definition
        new_def: New pipeline definition

    Returns:
        True if the definitions are functionally equivalent, False otherwise
    """
    # Compare nodes
    existing_nodes = {
        node["data"]["id"]: node
        for node in existing_def.get("configuration", {}).get("nodes", [])
    }
    new_nodes = {
        node["data"]["id"]: node
        for node in new_def.get("configuration", {}).get("nodes", [])
    }

    if existing_nodes.keys() != new_nodes.keys():
        return False

    for node_id, existing_node in existing_nodes.items():
        new_node = new_nodes[node_id]
        if (
            existing_node["data"]["type"] != new_node["data"]["type"]
            or existing_node["data"]["configuration"]
            != new_node["data"]["configuration"]
        ):
            return False

    # Compare edges
    existing_edges = {
        edge["id"]: edge
        for edge in existing_def.get("configuration", {}).get("edges", [])
    }
    new_edges = {
        edge["id"]: edge for edge in new_def.get("configuration", {}).get("edges", [])
    }

    if existing_edges.keys() != new_edges.keys():
        return False

    for edge_id, existing_edge in existing_edges.items():
        new_edge = new_edges[edge_id]
        if (
            existing_edge["source"] != new_edge["source"]
            or existing_edge["target"] != new_edge["target"]
        ):
            return False

    return True


def get_pipeline_by_name(
    pipeline_name: str, definition: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Get pipeline record from DynamoDB by name and optionally check if definition matches.

    Args:
        pipeline_name: Name of the pipeline to look up
        definition: Optional pipeline definition to compare against

    Returns:
        Pipeline record if found and definition matches (if provided), None otherwise
    """
    logger.info(f"Looking up pipeline with name: {pipeline_name}")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(PIPELINES_TABLE)

    try:
        # Scan for items with matching name
        response = table.scan(
            FilterExpression="#n = :name",
            ExpressionAttributeNames={"#n": "name"},
            ExpressionAttributeValues={":name": pipeline_name},
        )
        items = response.get("Items", [])
        if items:
            pipeline = items[0]
            # Check if the pipeline has a definition
            if "definition" in pipeline:
                # If definition is provided, check if it matches
                if definition and not compare_pipeline_definitions(
                    pipeline["definition"], definition
                ):
                    logger.info("Found pipeline but definition does not match")
                    return None
                return pipeline
        return None
    except Exception as e:
        logger.error(f"Error looking up pipeline: {e}")
        return None


def get_node_auth_config(node_id: str) -> Dict[str, Any]:
    """
    Retrieve node authentication configuration from DynamoDB.

    Args:
        node_id: ID of the node

    Returns:
        Auth configuration dictionary or None if not found
    """
    logger.info(f"Retrieving auth config from DynamoDB for node_id: {node_id}")
    dynamodb = boto3.resource("dynamodb")

    if not NODE_TABLE:
        msg = "Environment variable NODE_TABLE is not set."
        logger.error(msg)
        raise ValueError(msg)

    table = dynamodb.Table(NODE_TABLE)

    key = {"pk": f"NODE#{node_id}", "sk": "AUTH"}
    logger.debug(f"Using DynamoDB key: {key}")

    response = table.get_item(Key=key)
    auth_config = response.get("Item", {})
    logger.info(f"Retrieved auth config for {node_id}: {auth_config}")
    return auth_config


def get_node_info(node_id: str) -> Dict[str, Any]:
    """
    Retrieve node info from DynamoDB.

    Args:
        node_id: ID of the node

    Returns:
        Info dictionary or None if not found
    """
    logger.info(f"Retrieving info from DynamoDB for node_id: {node_id}")
    dynamodb = boto3.resource("dynamodb")

    if not NODE_TABLE:
        msg = "Environment variable NODE_TABLE is not set."
        logger.error(msg)
        raise ValueError(msg)

    table = dynamodb.Table(NODE_TABLE)

    key = {"pk": f"NODE#{node_id}", "sk": "INFO"}
    logger.debug(f"Using DynamoDB key: {key}")

    response = table.get_item(Key=key)
    info = response.get("Item", {})
    logger.info(f"Retrieved info for {node_id}: {info}")
    return info


def get_node_method(node_id: str, node_method: str) -> Dict[str, Any]:
    """
    Retrieve node method from DynamoDB.

    Args:
        node_id: ID of the node

    Returns:
        Method dictionary or None if not found
    """
    logger.info(f"Retrieving method from DynamoDB for node_id: {node_id}")
    dynamodb = boto3.resource("dynamodb")

    if not NODE_TABLE:
        msg = "Environment variable NODE_TABLE is not set."
        logger.error(msg)
        raise ValueError(msg)

    table = dynamodb.Table(NODE_TABLE)

    key = {
        "pk": f"NODE#{node_id}",
        "sk": f"METHOD#{node_method}",
    }  # i.e. embed_tasks_post
    logger.debug(f"Using DynamoDB key: {key}")

    response = table.get_item(Key=key)
    method = response.get("Item", {})
    logger.info(f"Retrieved mthod for {node_id}: {method}")
    return method


def get_integration_secret_arn(integration_id: str) -> Optional[str]:
    """
    Get the API key secret ARN for an integration.

    Args:
        integration_id: ID of the integration

    Returns:
        Secret ARN or None if not found
    """
    logger.info(f"Retrieving secret ARN for integration_id: {integration_id}")
    dynamodb = boto3.resource("dynamodb")

    integrations_table = os.environ.get("INTEGRATIONS_TABLE")
    if not integrations_table:
        logger.warning("INTEGRATIONS_TABLE environment variable not set")
        return None

    table = dynamodb.Table(integrations_table)

    # Construct the partition key with the INTEGRATION# prefix
    pk = f"INTEGRATION#{integration_id}"

    # Query for items with this partition key
    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(pk)
    )

    items = response.get("Items", [])
    if not items:
        logger.warning(f"No integration found with ID: {integration_id}")
        return None

    # Use the first item (assuming there's only one configuration per integration)
    integration = items[0]

    # Extract the ApiKeySecretArn from the top level
    secret_arn = integration.get("ApiKeySecretArn", {})

    logger.info(f"Retrieved secret ARN for integration {integration_id}: {secret_arn}")
    return secret_arn


def get_pipeline_by_id(pipeline_id: str) -> Optional[Dict[str, Any]]:
    """
    Get pipeline record from DynamoDB by ID.

    Args:
        pipeline_id: ID of the pipeline to look up

    Returns:
        Pipeline record if found, None otherwise
    """
    logger.info(f"Looking up pipeline with ID: {pipeline_id}")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(PIPELINES_TABLE)

    try:
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
    pipeline: Any,
    execution_arn: Optional[str] = None,
    deployment_status: str = "CREATING",
    active: bool = True,  # Default to active
) -> str:
    """
    Create a new pipeline record in DynamoDB with initial status.

    Args:
        pipeline: Pipeline definition object
        execution_arn: Optional ARN of the Step Function execution
        deployment_status: Initial deployment status
        active: Whether the pipeline is active

    Returns:
        ID of the created pipeline record
    """
    logger.info(
        f"Creating pipeline record with status: {deployment_status}, active: {active}"
    )
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
        "active": active,  # Add active field
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
        logger.info(f"Successfully created pipeline record with id {pipeline_id}")
        return pipeline_id
    except Exception as e:
        logger.exception(f"Failed to create pipeline record: {e}")
        raise


def update_pipeline_status(
    pipeline_id: str,
    deployment_status: str,
    state_machine_arn: Optional[str] = None,
    lambda_arns: Optional[Dict[str, str]] = None,
    eventbridge_rule_arns: Optional[Dict[str, str]] = None,
    active: Optional[bool] = None,  # New parameter
    sfn_role_arn: Optional[str] = None,
    lambda_role_arns: Optional[Dict[str, str]] = None,
    eventbridge_role_arns: Optional[Dict[str, str]] = None,
    trigger_lambda_arns: Optional[Dict[str, str]] = None,
    sqs_queue_arns: Optional[Dict[str, str]] = None,
    event_source_mapping_uuids: Optional[Dict[str, str]] = None,
    service_role_arns: Optional[Dict[str, Dict[str, str]]] = None,
) -> None:
    """
    Update the deployment status and optionally resources of a pipeline.

    Args:
        pipeline_id: ID of the pipeline to update
        deployment_status: New deployment status
        state_machine_arn: Optional ARN of the state machine
        lambda_arns: Optional dictionary mapping node IDs to Lambda ARNs
        eventbridge_rule_arns: Optional dictionary mapping node IDs to EventBridge rule ARNs
        active: Optional boolean indicating whether the pipeline is active
        sfn_role_arn: Optional ARN of the Step Functions IAM role
        lambda_role_arns: Optional dictionary mapping node IDs to Lambda IAM role ARNs
        eventbridge_role_arns: Optional dictionary mapping node IDs to EventBridge IAM role ARNs
        trigger_lambda_arns: Optional dictionary mapping node IDs to trigger Lambda ARNs
        sqs_queue_arns: Optional dictionary mapping node IDs to SQS queue ARNs
        event_source_mapping_uuids: Optional dictionary mapping node IDs to event source mapping UUIDs
        service_role_arns: Optional dictionary mapping node IDs to dictionaries of service role names and ARNs
    """
    logger.info(f"Updating pipeline {pipeline_id} status to {deployment_status}")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(PIPELINES_TABLE)

    now_iso = datetime.utcnow().isoformat()

    update_expr = "SET #status = :status, #up = :updated"
    expr_values = {":status": deployment_status, ":updated": now_iso}
    expr_names = {"#status": "deploymentStatus", "#up": "updatedAt"}

    # Add active state if provided
    if active is not None:
        update_expr += ", #active = :active"
        expr_values[":active"] = active
        expr_names["#active"] = "active"

    # Add resources if provided
    dependent_resources = []
    if lambda_arns:
        for node_id, arn in lambda_arns.items():
            if arn:
                dependent_resources.append(["lambda", arn])

                # Add Lambda IAM role if available
                if lambda_role_arns and node_id in lambda_role_arns:
                    role_arn = lambda_role_arns[node_id]
                    dependent_resources.append(["iam_role", role_arn])
                    logger.info(
                        f"Added Lambda IAM role {role_arn} to dependent resources"
                    )

        # Add service roles if available
        if service_role_arns:
            for node_id, roles in service_role_arns.items():
                for role_name, role_arn in roles.items():
                    dependent_resources.append(["service_role", role_arn])
                    logger.info(
                        f"Added service role {role_name} ({role_arn}) to dependent resources"
                    )

        update_expr += ", #res = :res"
        expr_values[":res"] = dependent_resources
        expr_names["#res"] = "dependentResources"

    if state_machine_arn:
        if lambda_arns:
            # Already added dependentResources, just append to it
            dependent_resources.append(["step_function", state_machine_arn])

            # Add Step Functions IAM role if available
            if sfn_role_arn:
                dependent_resources.append(["iam_role", sfn_role_arn])
                logger.info(
                    f"Added Step Functions IAM role {sfn_role_arn} to dependent resources"
                )
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

    # Handle service roles separately if lambda_arns is not provided
    elif service_role_arns:
        # Need to get existing dependentResources first
        pipeline = get_pipeline_by_id(pipeline_id)
        if pipeline and "dependentResources" in pipeline:
            dependent_resources = pipeline["dependentResources"]

        # Add service roles
        for node_id, roles in service_role_arns.items():
            for role_name, role_arn in roles.items():
                dependent_resources.append(["service_role", role_arn])
                logger.info(
                    f"Added service role {role_name} ({role_arn}) to dependent resources"
                )

        update_expr += ", #res = :res"
        expr_values[":res"] = dependent_resources
        expr_names["#res"] = "dependentResources"

    if eventbridge_rule_arns and not lambda_arns and not service_role_arns:
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

                # Add EventBridge IAM role if available
                if eventbridge_role_arns and node_id in eventbridge_role_arns:
                    role_arn = eventbridge_role_arns[node_id]
                    dependent_resources.append(["iam_role", role_arn])
                    logger.info(
                        f"Added EventBridge IAM role {role_arn} to dependent resources"
                    )

                # Add trigger Lambda if available
                if trigger_lambda_arns and node_id in trigger_lambda_arns:
                    trigger_lambda_arn = trigger_lambda_arns[node_id]
                    dependent_resources.append(["trigger_lambda", trigger_lambda_arn])
                    logger.info(
                        f"Added trigger Lambda {trigger_lambda_arn} to dependent resources"
                    )

                # Add SQS queue if available
                if sqs_queue_arns and node_id in sqs_queue_arns:
                    queue_arn = sqs_queue_arns[node_id]
                    dependent_resources.append(["sqs_queue", queue_arn])
                    logger.info(f"Added SQS queue {queue_arn} to dependent resources")

                # Add event source mapping if available
                if event_source_mapping_uuids and node_id in event_source_mapping_uuids:
                    mapping_uuid = event_source_mapping_uuids[node_id]
                    dependent_resources.append(["event_source_mapping", mapping_uuid])
                    logger.info(
                        f"Added event source mapping {mapping_uuid} to dependent resources"
                    )

    try:
        table.update_item(
            Key={"id": pipeline_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names,
        )
        logger.info(
            f"Successfully updated pipeline {pipeline_id} status to {deployment_status}"
        )
    except Exception as e:
        logger.exception(f"Failed to update pipeline status: {e}")
        raise


def store_pipeline_info(
    pipeline: Any,
    state_machine_arn: str,
    lambda_arns: Dict[str, str],
    eventbridge_rule_arns: Optional[Dict[str, str]] = None,
    pipeline_id: Optional[str] = None,
    active: bool = True,  # Default to active
    sfn_role_arn: Optional[str] = None,
    lambda_role_arns: Optional[Dict[str, str]] = None,
    eventbridge_role_arns: Optional[Dict[str, str]] = None,
    trigger_lambda_arns: Optional[Dict[str, str]] = None,
    sqs_queue_arns: Optional[Dict[str, str]] = None,
    event_source_mapping_uuids: Optional[Dict[str, str]] = None,
    service_role_arns: Optional[Dict[str, Dict[str, str]]] = None,
) -> str:
    """
    Store or update pipeline information in DynamoDB.

    Args:
        pipeline: Pipeline definition object
        state_machine_arn: ARN of the state machine
        lambda_arns: Dictionary mapping node IDs to Lambda ARNs
        eventbridge_rule_arns: Optional dictionary mapping node IDs to EventBridge rule ARNs
        pipeline_id: Optional ID of an existing pipeline record
        active: Whether the pipeline is active
        sfn_role_arn: Optional ARN of the Step Functions IAM role
        lambda_role_arns: Optional dictionary mapping node IDs to Lambda IAM role ARNs
        eventbridge_role_arns: Optional dictionary mapping node IDs to EventBridge IAM role ARNs
        trigger_lambda_arns: Optional dictionary mapping node IDs to trigger Lambda ARNs
        sqs_queue_arns: Optional dictionary mapping node IDs to SQS queue ARNs
        event_source_mapping_uuids: Optional dictionary mapping node IDs to event source mapping UUIDs
        service_role_arns: Optional dictionary mapping node IDs to dictionaries of service role names and ARNs

    Returns:
        ID of the created or updated pipeline
    """
    logger.info("Storing/updating pipeline information in DynamoDB")

    if pipeline_id:
        # Update existing pipeline with DEPLOYED status and new definition
        logger.info(f"Updating existing pipeline with ID: {pipeline_id}")

        # Update the pipeline definition
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(PIPELINES_TABLE)
        now_iso = datetime.utcnow().isoformat()

        try:
            # Update the definition and name fields
            table.update_item(
                Key={"id": pipeline_id},
                UpdateExpression="SET #def = :def, #name = :name, #desc = :desc, #up = :updated",
                ExpressionAttributeNames={
                    "#def": "definition",
                    "#name": "name",
                    "#desc": "description",
                    "#up": "updatedAt",
                },
                ExpressionAttributeValues={
                    ":def": pipeline.dict(),
                    ":name": pipeline.name,
                    ":desc": pipeline.description,
                    ":updated": now_iso,
                },
            )
            logger.info(f"Successfully updated definition for pipeline {pipeline_id}")
        except Exception as e:
            logger.exception(f"Failed to update pipeline definition: {e}")
            raise

        # Update the pipeline status and resources
        update_pipeline_status(
            pipeline_id,
            "DEPLOYED",
            state_machine_arn,
            lambda_arns,
            eventbridge_rule_arns,
            active=active,
            sfn_role_arn=sfn_role_arn,
            lambda_role_arns=lambda_role_arns,
            eventbridge_role_arns=eventbridge_role_arns,
            trigger_lambda_arns=trigger_lambda_arns,
            sqs_queue_arns=sqs_queue_arns,
            event_source_mapping_uuids=event_source_mapping_uuids,
            service_role_arns=service_role_arns,
        )
        return pipeline_id
    else:
        # Check for existing pipeline with same name
        existing_pipeline = get_pipeline_by_name(pipeline.name)
        if existing_pipeline:
            pipeline_id = existing_pipeline["id"]
            update_pipeline_status(
                pipeline_id,
                "DEPLOYED",
                state_machine_arn,
                lambda_arns,
                eventbridge_rule_arns,
                active=active,
                sfn_role_arn=sfn_role_arn,
                lambda_role_arns=lambda_role_arns,
                eventbridge_role_arns=eventbridge_role_arns,
                trigger_lambda_arns=trigger_lambda_arns,
                sqs_queue_arns=sqs_queue_arns,
                event_source_mapping_uuids=event_source_mapping_uuids,
                service_role_arns=service_role_arns,
            )
            return pipeline_id
        else:
            # Create new pipeline with DEPLOYED status
            pipeline_id = create_pipeline_record(
                pipeline, None, "DEPLOYED", active=active
            )
            update_pipeline_status(
                pipeline_id,
                "DEPLOYED",
                state_machine_arn,
                lambda_arns,
                eventbridge_rule_arns,
                sfn_role_arn=sfn_role_arn,
                lambda_role_arns=lambda_role_arns,
                eventbridge_role_arns=eventbridge_role_arns,
                trigger_lambda_arns=trigger_lambda_arns,
                sqs_queue_arns=sqs_queue_arns,
                event_source_mapping_uuids=event_source_mapping_uuids,
                service_role_arns=service_role_arns,
            )
            return pipeline_id
