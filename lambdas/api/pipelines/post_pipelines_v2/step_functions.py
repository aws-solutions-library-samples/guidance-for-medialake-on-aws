import json
import re
import time
from typing import Dict, Any
import os
import boto3
from aws_lambda_powertools import Logger

from iam_operations import create_sfn_role

# Initialize logger
logger = Logger()

resource_prefix = os.environ["RESOURCE_PREFIX"]


def sanitize_role_name(name: str) -> str:
    """
    Create a sanitized IAM role name from a pipeline name.

    Args:
        name: Name to sanitize

    Returns:
        A sanitized name suitable for IAM roles
    """
    # Convert to lowercase
    sanitized_name = name.lower()

    # Replace spaces with hyphens
    sanitized_name = sanitized_name.replace(" ", "-")

    # Replace non-alphanumeric characters (except allowed special chars) with underscores
    sanitized_name = re.sub(r"[^a-z0-9+=,.@_-]", "_", sanitized_name)

    # Ensure the name starts with a letter or allowed character
    sanitized_name = re.sub(r"^[^a-z0-9+=,.@_-]+", "", sanitized_name)

    # Truncate to 64 characters (maximum length for IAM role names)
    sanitized_name = sanitized_name[:64]

    # Ensure the name doesn't end with a hyphen or underscore
    sanitized_name = re.sub(r"[-_]+$", "", sanitized_name)

    return sanitized_name


def get_flow_state_definition(node: Any) -> Dict[str, Any]:
    """
    Create a Step Function state definition for a flow-type node.

    Args:
        node: Node object containing configuration

    Returns:
        State definition dictionary for the flow node
    """
    logger.info(f"Creating flow state definition for node: {node.id}")

    # Read YAML file from S3
    from lambda_operations import read_yaml_from_s3
    from config import NODE_TEMPLATES_BUCKET

    yaml_file_path = f"node_templates/flow/{node.data.id}.yaml"
    try:
        yaml_data = read_yaml_from_s3(NODE_TEMPLATES_BUCKET, yaml_file_path)
    except Exception as e:
        logger.warning(
            f"Failed to read YAML for flow node {node.id}, using default: {e}"
        )
        # If the specific node YAML doesn't exist, try to use a generic one based on the node label
        yaml_file_path = f"node_templates/flow/{node.data.label.lower()}.yaml"
        try:
            yaml_data = read_yaml_from_s3(NODE_TEMPLATES_BUCKET, yaml_file_path)
        except Exception as e:
            logger.error(f"Failed to read generic YAML for flow node {node.id}: {e}")
            raise ValueError(f"No YAML template found for flow node {node.id}")

    # Get the Step Function step type from the YAML
    step_name = yaml_data["node"]["integration"]["config"]["aws_stepfunction"][
        "step_name"
    ]

    # Create the state definition based on the step type
    state_def = {}

    if step_name == "wait":
        # Wait state
        seconds = node.data.configuration.get("seconds", 1)
        state_def = {"Type": "Wait", "Seconds": seconds, "End": True}
    elif step_name == "choice":
        # Choice state
        choices = node.data.configuration.get("choices", [])
        
        # Ensure we have at least one choice in the Choices array
        if not choices:
            choices = [{"variable": "$.status", "value": "SUCCESS"}]
        
        # For Choice states, we'll set placeholder Next values that will be updated later
        # when we connect the edges. We use the node ID as a prefix to ensure uniqueness.
        state_def = {
            "Type": "Choice",
            "Choices": [
                {
                    "Variable": choice.get("variable", "$.status"),
                    "StringEquals": choice.get("value", "SUCCESS"),
                    "Next": f"__PLACEHOLDER__{node.id}_TRUE__",  # Placeholder to be replaced later
                }
                for choice in choices
            ],
            "Default": f"__PLACEHOLDER__{node.id}_FALSE__",  # Placeholder to be replaced later
        }
    elif step_name == "parallel":
        # Parallel state
        branches = node.data.configuration.get("branches", [])
        state_def = {"Type": "Parallel", "Branches": branches, "End": True}
    elif step_name == "map":
        # Map state
        iterator = node.data.configuration.get("iterator", {})
        
        # Ensure the Iterator has the required fields
        if not iterator or "States" not in iterator or "StartAt" not in iterator:
            # Create a minimal valid Iterator
            iterator = {
                "StartAt": "PassState",
                "States": {
                    "PassState": {
                        "Type": "Pass",
                        "End": True
                    }
                }
            }
        
        state_def = {
            "Type": "Map",
            "ItemsPath": node.data.configuration.get("itemsPath", "$.items"),
            "MaxConcurrency": node.data.configuration.get("maxConcurrency", 0),
            "Iterator": iterator,
            "End": True,
        }
    elif step_name == "pass":
        # Pass state
        result = node.data.configuration.get("result", None)
        state_def = {"Type": "Pass", "End": True}
        if result:
            state_def["Result"] = result
    elif step_name == "succeed":
        # Succeed state
        state_def = {"Type": "Succeed"}
    elif step_name == "fail":
        # Fail state
        state_def = {
            "Type": "Fail",
            "Error": node.data.configuration.get("error", "FlowFailure"),
            "Cause": node.data.configuration.get("cause", "Flow step failed"),
        }
    else:
        logger.warning(f"Unknown flow step type: {step_name}")
        state_def = {"Type": "Pass", "End": True}

    logger.debug(f"Created flow state definition for node {node.id}: {state_def}")
    return state_def


def build_step_function_definition(
    pipeline: Any, lambda_arns: Dict[str, str]
) -> Dict[str, Any]:
    """
    Build a Step Functions state machine definition from pipeline configuration.

    Args:
        pipeline: Pipeline definition object
        lambda_arns: Dictionary mapping node IDs to Lambda ARNs

    Returns:
        Complete state machine definition
    """
    logger.info("Building Step Functions state machine definition")

    # Log the pipeline configuration for debugging
    logger.info(f"Pipeline name: {pipeline.name}")
    logger.info(f"Number of nodes: {len(pipeline.configuration.nodes)}")
    logger.info(f"Number of edges: {len(pipeline.configuration.edges)}")

    # Create mappings between different node ID formats
    node_id_to_data_id = {}
    data_id_to_node_id = {}
    node_id_to_node = {}

    # Build the mappings
    for node in pipeline.configuration.nodes:
        if node.id and node.data and node.data.id:
            node_id_to_data_id[node.id] = node.data.id
            data_id_to_node_id[node.data.id] = node.id
            node_id_to_node[node.id] = node
            logger.info(f"Node mapping: {node.id} -> {node.data.id} ({node.data.type})")

    # Log the edges for debugging
    for edge in pipeline.configuration.edges:
        source_node = node_id_to_node.get(edge.source)
        target_node = node_id_to_node.get(edge.target)
        logger.info(
            f"Edge: {edge.source} ({source_node.data.id if source_node else 'unknown'}) -> "
            f"{edge.target} ({target_node.data.id if target_node else 'unknown'})"
        )

    # Create a simplified graph representation for analysis
    # Map from node.id to node.id (not data.id)
    graph = {}
    for edge in pipeline.configuration.edges:
        if edge.source not in graph:
            graph[edge.source] = []
        graph[edge.source].append(edge.target)

    # Also create a graph using data.id for the DFS later
    data_id_graph = {}
    for edge in pipeline.configuration.edges:
        source_data_id = node_id_to_data_id.get(edge.source)
        target_data_id = node_id_to_data_id.get(edge.target)

        if source_data_id and target_data_id:
            if source_data_id not in data_id_graph:
                data_id_graph[source_data_id] = []
            data_id_graph[source_data_id].append(target_data_id)
            logger.info(
                f"Added edge to data_id_graph: {source_data_id} -> {target_data_id}"
            )

    # Find the root node (node with no incoming edges)
    all_nodes = set(node.id for node in pipeline.configuration.nodes)
    target_nodes = set()
    for edge in pipeline.configuration.edges:
        # Handle both dictionary and object structures
        if isinstance(edge, dict):
            target_nodes.add(edge.get("target"))
        else:
            target_nodes.add(edge.target)
    root_nodes = all_nodes - target_nodes

    if not root_nodes:
        logger.warning("No root node found in the graph. Using first node as root.")
        root_node_id = (
            pipeline.configuration.nodes[0].id if pipeline.configuration.nodes else None
        )
    else:
        # Prefer trigger nodes as root
        trigger_roots = [
            node.id
            for node in pipeline.configuration.nodes
            if node.id in root_nodes and node.data.type.lower() == "trigger"
        ]
        root_node_id = trigger_roots[0] if trigger_roots else next(iter(root_nodes))

    logger.info(f"Root node ID: {root_node_id}")

    # Initialize states dictionary
    states = {}

    # Create mappings for unique state names
    node_id_to_state_name = {}
    data_id_to_unique_states = {}

    # First pass: create unique state names for each node
    for node in pipeline.configuration.nodes:
        # Create a unique state name that combines the node label and node ID
        # This ensures that each node gets a descriptive and unique state name
        operation_id = node.data.configuration.get("operationId", "")
        unique_state_name = f"{node.data.label} {operation_id} ({node.id})"

        # Sanitize the state name to ensure it's valid for Step Functions
        # Remove special characters and spaces that might cause issues
        sanitized_state_name = "".join(
            c if c.isalnum() else "_" for c in unique_state_name
        )
        # Ensure it starts with a letter or number
        if not sanitized_state_name[0].isalnum():
            sanitized_state_name = "state_" + sanitized_state_name

        # Store the mapping from node ID to unique state name
        node_id_to_state_name[node.id] = sanitized_state_name

        # Also store the reverse mapping using data.id for backward compatibility
        if node.data.id not in data_id_to_unique_states:
            data_id_to_unique_states[node.data.id] = []
        data_id_to_unique_states[node.data.id].append(sanitized_state_name)

        logger.info(
            f"Created unique state name for node {node.id}: {sanitized_state_name} (from label: {node.data.label})"
        )

    # Second pass: create state definitions using the unique state names
    for node in pipeline.configuration.nodes:
        # Skip trigger nodes as they don't need to be created as steps
        if node.data.type.lower() == "trigger":
            logger.info(f"Skipping trigger node {node.id}")
            continue

        unique_state_name = node_id_to_state_name[node.id]
        logger.info(f"Creating state definition for {unique_state_name}")

        if node.data.type.lower() == "flow":
            # Handle flow-type nodes
            try:
                state_def = get_flow_state_definition(node)
                # Remove End: true if it exists, we'll set it later if needed
                if "End" in state_def:
                    del state_def["End"]
                states[unique_state_name] = state_def
                logger.info(f"Created flow state for {unique_state_name}: {state_def}")
            except Exception as e:
                logger.error(
                    f"Failed to create flow state for node {unique_state_name}: {e}"
                )
                continue
        else:
            # Handle Lambda function nodes
            lambda_arn = lambda_arns.get(node.data.id)
            if not lambda_arn:
                logger.warning(
                    f"No Lambda ARN found for node {node.data.id}; creating pass state instead."
                )
                # Create a Pass state as a fallback - without End: true
                states[unique_state_name] = {
                    "Type": "Pass",
                    "Result": {"message": f"No Lambda function for {node.data.id}"},
                }
            else:
                states[unique_state_name] = {
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
                }
                logger.info(f"Created task state for {unique_state_name}")

    # Get the root node's unique state name to use as the start state
    # If the root node is a trigger, find the first non-trigger node connected to it
    if (
        root_node_id
        and node_id_to_node.get(root_node_id)
        and node_id_to_node[root_node_id].data.type.lower() == "trigger"
    ):
        logger.info(f"Root node {root_node_id} is a trigger, finding next node")
        if root_node_id in graph and graph[root_node_id]:
            # Get the first target from the graph
            next_node_id = graph[root_node_id][0]
            start_at = node_id_to_state_name.get(next_node_id)
            logger.info(
                f"Using node {next_node_id} as start state instead of trigger node"
            )
        else:
            logger.warning(
                f"Trigger root node {root_node_id} has no outgoing edges, using first available state"
            )
            # Use the first available state as start state
            start_at = next(iter(states)) if states else None
    else:
        start_at = node_id_to_state_name.get(root_node_id)

    logger.info(f"Start state: {start_at}")

    # Connect states based on edges using the unique state names
    for edge in pipeline.configuration.edges:
        # Handle both dictionary and object structures for edge properties
        if isinstance(edge, dict):
            source_id = edge.get("source")
            target_id = edge.get("target")
            source_handle = edge.get("sourceHandle")
        else:
            source_id = edge.source
            target_id = edge.target
            source_handle = getattr(edge, "sourceHandle", None)

        # Get the unique state names for the source and target nodes
        source_state_name = node_id_to_state_name.get(source_id)
        target_state_name = node_id_to_state_name.get(target_id)

        logger.info(
            f"Connecting: {source_id} ({source_state_name}) -> {target_id} ({target_state_name}), sourceHandle: {source_handle}"
        )

        if source_state_name in states and target_state_name in states:
            source_state = states[source_state_name]
            source_node = node_id_to_node.get(source_id)

            # Skip if the source state is a terminal state
            if source_state.get("Type") in ["Succeed", "Fail"]:
                continue

            # Handle Choice states specially
            if source_state.get("Type") == "Choice":
                # Check if this is a conditional edge (has a sourceHandle)
                if source_handle == "condition_true" or source_handle == "condition_true_output":
                    # This is the "true" path from the Choice
                    if "Choices" in source_state and source_state["Choices"]:
                        # Replace the placeholder with the actual target
                        for choice in source_state["Choices"]:
                            if "__PLACEHOLDER__" in str(choice.get("Next", "")):
                                choice["Next"] = target_state_name
                                logger.info(f"Connected Choice true path: {source_state_name} -> {target_state_name}")
                
                elif source_handle == "condition_false" or source_handle == "condition_false_output":
                    # This is the "false" path from the Choice (Default)
                    if "Default" in source_state and "__PLACEHOLDER__" in str(source_state["Default"]):
                        source_state["Default"] = target_state_name
                        logger.info(f"Connected Choice default path: {source_state_name} -> {target_state_name}")
                
                else:
                    # If no sourceHandle but it's a Choice state, this might be a regular connection
                    # We'll handle this as a fallback, but it's not the expected case for Choice states
                    logger.warning(f"Choice state {source_state_name} has a connection without a sourceHandle")
                    
                    # If Choices is empty or Default is not set, set them with the target
                    if "Choices" not in source_state or not source_state["Choices"]:
                        source_state["Choices"] = [{
                            "Variable": "$.status",
                            "StringEquals": "SUCCESS",
                            "Next": target_state_name
                        }]
                    
                    if "Default" not in source_state or "__PLACEHOLDER__" in str(source_state["Default"]):
                        source_state["Default"] = target_state_name
            
            else:
                # For non-Choice states, handle normally
                # Remove End: True if it exists
                if "End" in source_state:
                    del source_state["End"]

                # Add Next property
                source_state["Next"] = target_state_name
                logger.info(f"Connected {source_state_name} -> {target_state_name}")

    # Ensure the starting state exists and has a valid Next target if needed
    if start_at and start_at in states:
        start_state = states[start_at]

        # If the start state doesn't have a Next property and it's not a terminal state
        if (
            "Next" not in start_state
            and start_state.get("Type") not in ["Succeed", "Fail"]
            and root_node_id in graph  # Check if it has outgoing edges
        ):
            # Get the first target from the graph
            target_node_id = graph[root_node_id][0]
            target_state_name = node_id_to_state_name.get(target_node_id)

            if target_state_name and target_state_name in states:
                # Remove End: True if it exists
                if "End" in start_state:
                    del start_state["End"]

                # Add Next property
                start_state["Next"] = target_state_name
                logger.info(f"Connected start state {start_at} to {target_state_name}")

    # Find leaf nodes (nodes with no outgoing edges)
    leaf_node_ids = set()
    for node_id in all_nodes:
        if node_id not in graph:  # No outgoing edges
            leaf_node_ids.add(node_id)

    logger.info(f"Leaf nodes: {leaf_node_ids}")

    # Ensure at least one state has End: true or is a terminal state
    has_terminal_state = False

    # First check if any state is already a terminal state
    for state_id, state in states.items():
        if (
            state.get("Type") in ["Succeed", "Fail"]
            or "End" in state
            and state["End"] is True
        ):
            has_terminal_state = True
            logger.info(f"Found existing terminal state: {state_id}")
            break

    # If no terminal state exists, mark leaf nodes as terminal states
    if not has_terminal_state and leaf_node_ids:
        for leaf_id in leaf_node_ids:
            leaf_state_name = node_id_to_state_name.get(leaf_id)
            if leaf_state_name and leaf_state_name in states:
                # Only mark as terminal if it doesn't have a Next property
                if "Next" not in states[leaf_state_name]:
                    states[leaf_state_name]["End"] = True
                    logger.info(
                        f"Marked leaf node {leaf_state_name} as a terminal state"
                    )
                    has_terminal_state = True
                    break  # One terminal state is enough

    # If still no terminal state, try to find any state without a Next property
    if not has_terminal_state:
        for state_id, state in states.items():
            if "Next" not in state and state.get("Type") not in ["Succeed", "Fail"]:
                state["End"] = True
                logger.info(f"Marked state {state_id} as a terminal state")
                has_terminal_state = True
                break  # One terminal state is enough

    # If still no terminal state, forcibly mark the last state as terminal
    if not has_terminal_state and states:
        last_state_id = list(states.keys())[-1]
        # Remove Next if it exists
        if "Next" in states[last_state_id]:
            logger.warning(
                f"Removing Next from state {last_state_id} to make it terminal"
            )
            del states[last_state_id]["Next"]

        # Add End: true
        states[last_state_id]["End"] = True
        logger.info(f"Forcibly marked last state {last_state_id} as a terminal state")

    # Add a Succeed state as a last resort if there are no states at all
    if not states:
        logger.warning("No states found, adding a dummy Succeed state")
        states["DummySucceedState"] = {"Type": "Succeed"}
        if not start_at:
            start_at = "DummySucceedState"

    # Build a topological ordering of the states to find the execution path
    logger.info("Building topological ordering of states")

    # Create a graph representation using unique state names
    state_graph = {}
    for edge in pipeline.configuration.edges:
        # Handle both dictionary and object structures
        if isinstance(edge, dict):
            source_id = edge.get("source")
            target_id = edge.get("target")
        else:
            source_id = edge.source
            target_id = edge.target
            
        source_state_name = node_id_to_state_name.get(source_id)
        target_state_name = node_id_to_state_name.get(target_id)

        if source_state_name and target_state_name:
            if source_state_name not in state_graph:
                state_graph[source_state_name] = []
            state_graph[source_state_name].append(target_state_name)
            logger.info(
                f"Added edge to state_graph: {source_state_name} -> {target_state_name}"
            )

    # Find all states reachable from the start state
    reachable_states = set()
    execution_path = []  # To track the order of execution

    def dfs_topo(state_id, visited=None, path=None):
        if visited is None:
            visited = set()
        if path is None:
            path = []

        if state_id in visited:
            return path

        visited.add(state_id)
        path.append(state_id)

        # Follow outgoing edges
        for next_state in state_graph.get(state_id, []):
            if next_state not in visited:
                dfs_topo(next_state, visited, path)

        return path

    # Start DFS from the start state to get execution path
    if start_at:
        execution_path = dfs_topo(start_at)
        reachable_states = set(execution_path)
        logger.info(f"Execution path: {execution_path}")

    # Remove unreachable states
    unreachable_states = set(states.keys()) - reachable_states
    if unreachable_states:
        logger.warning(f"Removing unreachable states: {unreachable_states}")
        for state_id in unreachable_states:
            del states[state_id]

    # Connect states according to the execution path
    for i in range(len(execution_path) - 1):
        current_state = execution_path[i]
        next_state = execution_path[i + 1]

        if current_state in states and next_state in states:
            # Skip if the current state is a terminal state
            if states[current_state].get("Type") in ["Succeed", "Fail"]:
                continue

            # For Choice states, don't modify the Next property
            if states[current_state].get("Type") != "Choice":
                # Remove End: True if it exists
                if "End" in states[current_state]:
                    del states[current_state]["End"]

                # Add Next property
                states[current_state]["Next"] = next_state
                logger.info(
                    f"Connected {current_state} -> {next_state} in execution path"
                )

    # Mark the last state in the execution path as terminal
    if execution_path:
        last_state_id = execution_path[-1]
        if last_state_id in states:
            # If it has a Next property, remove it
            if "Next" in states[last_state_id]:
                del states[last_state_id]["Next"]

            # Add End: true unless it's already a terminal state
            if states[last_state_id].get("Type") not in ["Succeed", "Fail"]:
                states[last_state_id]["End"] = True
                logger.info(
                    f"Marked last state in execution path {last_state_id} as End: true"
                )

    # Ensure we have at least one terminal state
    has_terminal_state = False
    for state_id, state in states.items():
        if state.get("Type") in ["Succeed", "Fail"] or state.get("End") is True:
            has_terminal_state = True
            logger.info(f"Found terminal state: {state_id}")
            break

    # If still no terminal state, add a Succeed state
    if not has_terminal_state and states:
        logger.warning("No terminal state found, adding a Succeed state")
        succeed_state_id = "SucceedState"
        states[succeed_state_id] = {"Type": "Succeed"}

        # Connect the last state to the Succeed state
        if execution_path:
            last_state_id = execution_path[-1]
            if last_state_id in states:
                # Remove End: True if it exists
                if "End" in states[last_state_id]:
                    del states[last_state_id]["End"]

                # Add Next property
                states[last_state_id]["Next"] = succeed_state_id
                logger.info(
                    f"Connected last state {last_state_id} to {succeed_state_id}"
                )

    logger.info(f"Determined start node: {start_at}")
    definition = {
        "Comment": f"State machine for pipeline {pipeline.name}",
        "StartAt": start_at,
        "States": states,
    }
    logger.info(f"Built state machine definition: {definition}")
    return definition


def wait_for_state_machine_deletion(
    state_machine_name: str, max_attempts: int = 40
) -> None:
    """
    Wait for a state machine to be fully deleted.

    Args:
        state_machine_name: Name of the state machine
        max_attempts: Maximum number of attempts to check
    """
    sfn_client = boto3.client("stepfunctions")
    attempt = 0

    while attempt < max_attempts:
        try:
            paginator = sfn_client.get_paginator("list_state_machines")
            exists = False
            for page in paginator.paginate():
                for state_machine in page["stateMachines"]:
                    if state_machine["name"] == state_machine_name:
                        exists = True
                        break
                if exists:
                    break

            if not exists:
                logger.info(f"State machine {state_machine_name} has been deleted")
                return

            attempt += 1
            logger.info(
                f"State machine {state_machine_name} is still being deleted, waiting... (attempt {attempt}/{max_attempts})"
            )
            time.sleep(5)  # Wait 5 seconds between checks

        except Exception as e:
            logger.error(f"Error checking state machine status: {e}")
            attempt += 1
            time.sleep(5)

    raise TimeoutError(
        f"State machine {state_machine_name} deletion timed out after {max_attempts} attempts"
    )


def check_step_function_exists(state_machine_name: str) -> bool:
    """
    Check if a Step Function state machine exists.

    Args:
        state_machine_name: Name of the state machine

    Returns:
        True if the state machine exists, False otherwise
    """
    sfn_client = boto3.client("stepfunctions")
    try:
        paginator = sfn_client.get_paginator("list_state_machines")
        for page in paginator.paginate():
            for state_machine in page["stateMachines"]:
                if state_machine["name"] == state_machine_name:
                    return True
        return False
    except Exception as e:
        logger.error(f"Error checking Step Function existence: {e}")
        return False


def delete_step_function(state_machine_name: str) -> None:
    """
    Delete a Step Function state machine if it exists.

    Args:
        state_machine_name: Name of the state machine
    """
    sfn_client = boto3.client("stepfunctions")
    try:
        # First get the ARN
        paginator = sfn_client.get_paginator("list_state_machines")
        for page in paginator.paginate():
            for state_machine in page["stateMachines"]:
                if state_machine["name"] == state_machine_name:
                    sfn_client.delete_state_machine(
                        stateMachineArn=state_machine["stateMachineArn"]
                    )
                    logger.info(f"Deleted existing Step Function: {state_machine_name}")
                    return
    except Exception as e:
        logger.error(f"Error deleting Step Function: {e}")


def sanitize_state_machine_name(name: str) -> str:
    """
    Create a sanitized state machine name from a pipeline name.

    Args:
        name: Name to sanitize

    Returns:
        A sanitized name suitable for AWS Step Functions state machines
    """
    # Replace spaces with hyphens
    sanitized_name = name.replace(" ", "-")

    # Replace non-alphanumeric characters (except hyphens) with underscores
    sanitized_name = re.sub(r"[^a-zA-Z0-9-]", "_", sanitized_name)

    # Ensure the name starts with a letter or number
    sanitized_name = re.sub(r"^[^a-zA-Z0-9]+", "", sanitized_name)

    # Truncate to 80 characters (maximum length for Step Function names)
    sanitized_name = sanitized_name[:80]

    # Ensure the name doesn't end with a hyphen or underscore
    sanitized_name = re.sub(r"[-_]+$", "", sanitized_name)

    return f"{resource_prefix}_{sanitized_name}_pipeline"


def create_step_function(
    pipeline_name: str, definition: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a Step Functions state machine.

    Args:
        pipeline_name: Name of the pipeline
        definition: State machine definition

    Returns:
        Response from the create_state_machine API call
    """
    logger.info(f"Creating Step Functions state machine for pipeline: {pipeline_name}")
    sfn_client = boto3.client("stepfunctions")

    # Sanitize the pipeline name for use in the IAM role name and state machine name
    sanitized_role_name = sanitize_role_name(pipeline_name)
    sanitized_state_machine_name = sanitize_state_machine_name(pipeline_name)

    role_name = f"{resource_prefix}_{sanitized_role_name}_sfn_role"
    logger.info(f"Using sanitized role name: {role_name}")
    logger.info(f"Using sanitized state machine name: {sanitized_state_machine_name}")
    role_arn = create_sfn_role(role_name)

    try:
        # Check if state machine exists
        if check_step_function_exists(sanitized_state_machine_name):
            logger.info(
                f"Found existing Step Function {sanitized_state_machine_name}, deleting it"
            )
            delete_step_function(sanitized_state_machine_name)
            wait_for_state_machine_deletion(sanitized_state_machine_name)

        # Validate states to ensure they have valid Next targets and are reachable
        for state_name, state in definition["States"].items():
            # Handle Choice states
            if state.get("Type") == "Choice":
                # Check Choices
                if "Choices" in state:
                    # Ensure Choices is not empty
                    if not state["Choices"]:
                        # Add a default choice
                        valid_next = next((s for s in definition["States"].keys() if s != state_name), None)
                        if valid_next:
                            state["Choices"] = [{
                                "Variable": "$.status",
                                "StringEquals": "SUCCESS",
                                "Next": valid_next
                            }]
                            logger.info(f"Added default choice to empty Choices array in {state_name}")
                    
                    # Check existing choices
                    for choice in state["Choices"]:
                        if "__PLACEHOLDER__" in str(choice.get("Next", "")):
                            logger.warning(f"Choice state {state_name} has placeholder Next target in Choices")
                            # Find a valid state to use as Next
                            valid_next = next((s for s in definition["States"].keys() if s != state_name), None)
                            if valid_next:
                                choice["Next"] = valid_next
                                logger.info(f"Updated Choice state {state_name} Choices Next to {valid_next}")
                
                # Check Default
                if "__PLACEHOLDER__" in str(state.get("Default", "")):
                    logger.warning(f"Choice state {state_name} has placeholder Default target")
                    # Find a valid state to use as Default
                    valid_default = next((s for s in definition["States"].keys() if s != state_name), None)
                    if valid_default:
                        state["Default"] = valid_default
                        logger.info(f"Updated Choice state {state_name} Default to {valid_default}")
            
            # Handle Map states
            elif state.get("Type") == "Map":
                # Ensure Iterator has required fields
                if "Iterator" in state:
                    iterator = state["Iterator"]
                    if not isinstance(iterator, dict) or "States" not in iterator or "StartAt" not in iterator:
                        # Create a minimal valid Iterator
                        state["Iterator"] = {
                            "StartAt": "PassState",
                            "States": {
                                "PassState": {
                                    "Type": "Pass",
                                    "End": True
                                }
                            }
                        }
                        logger.info(f"Fixed Map state {state_name} Iterator with missing required fields")

        # Print the definition for debugging
        definition_json = json.dumps(definition, indent=2)
        # print(f"Step Function Definition for {pipeline_name}:\n{definition_json}")
        logger.info(f"Step Function Definition for {pipeline_name}:\n{definition_json}")

        # Create new state machine
        logger.info(f"Creating new Step Function: {sanitized_state_machine_name}")
        response = sfn_client.create_state_machine(
            name=sanitized_state_machine_name,
            definition=json.dumps(definition),
            roleArn=role_arn,
        )
        logger.info(
            f"Created state machine for pipeline '{pipeline_name}' with name '{sanitized_state_machine_name}': {response}"
        )
        return response
    except Exception as e:
        logger.exception(
            f"Failed to create/update state machine for pipeline '{pipeline_name}': {e}"
        )
        raise
