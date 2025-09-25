"""
State definition creation for Step Functions state machines.
"""

from typing import Any, Dict, List, Optional

from aws_lambda_powertools import Logger

# Import from lambda_operations for reading YAML files
from lambda_operations import read_yaml_from_s3

from config import NODE_TEMPLATES_BUCKET

logger = Logger()


class StateDefinitionFactory:
    """
    Creates state definitions for Step Functions state machines.

    This class is responsible for creating state definitions based on
    node types and configurations.
    """

    def __init__(
        self,
        pipeline: Any,
        lambda_arns: Dict[str, str],
        first_lambda_node_id: Optional[str] = None,
    ):
        """
        Initialize the StateDefinitionFactory.

        Args:
            pipeline: Pipeline definition object
            lambda_arns: Dictionary mapping node IDs to Lambda ARNs
            first_lambda_node_id: ID of the first Lambda node in the execution path
        """
        self.pipeline = pipeline
        self.lambda_arns = lambda_arns
        self.node_id_to_lambda_key = {}
        self.first_lambda_node_id = first_lambda_node_id

    def _get_previous_nodes(self, node_id: str) -> list:
        """
        Identify nodes that feed into the given node.

        Args:
            node_id: ID of the node to find inputs for

        Returns:
            List of nodes that feed into the given node
        """
        previous_nodes = []

        for edge in self.pipeline.configuration.edges:
            target_id = edge.target if hasattr(edge, "target") else edge.get("target")

            if target_id == node_id:
                source_id = (
                    edge.source if hasattr(edge, "source") else edge.get("source")
                )
                source_node = next(
                    (n for n in self.pipeline.configuration.nodes if n.id == source_id),
                    None,
                )

                if source_node:
                    previous_nodes.append(source_node)

        return previous_nodes

    def _determine_items_path(self, node: Any, previous_nodes: list) -> str:
        """
        Determine the appropriate ItemsPath for a Map state based on previous nodes.

        Args:
            node: The Map node
            previous_nodes: List of nodes that feed into the Map node

        Returns:
            The appropriate ItemsPath
        """
        # First check if there's an explicit configuration
        if "itemsPath" in node.data.configuration:
            configured_path = node.data.configuration["itemsPath"]
            logger.info(f"Using explicitly configured ItemsPath: {configured_path}")
            return configured_path

        # We need to check for both externalPayloadLocation and externalTaskResults
        # Since we can't use intrinsic functions directly in ItemsPath, we'll use a simple approach
        # that works with Step Functions' limitations
        logger.info(f"Using $.payload.data as default ItemsPath for Map node {node.id}")
        return "$.payload.data"

    def create_state_definitions(
        self,
        nodes: list,
        node_id_to_state_name: Dict[str, str],
        map_processor_chains: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """
        Create state definitions for all nodes.

        Args:
            nodes: List of nodes from the pipeline
            node_id_to_state_name: Mapping from node IDs to state names
            map_processor_chains: Mapping from Map node IDs to lists of node IDs in their processor chains

        Returns:
            Dictionary of state definitions
        """
        states = {}

        # Build lambda key mappings
        self._build_lambda_key_mappings(nodes)

        # Track nodes that are used as Map processors to avoid duplicate states
        map_processor_nodes = set()

        # First pass: identify Map processor nodes from the chains
        for map_id, processor_chain in map_processor_chains.items():
            for node_id in processor_chain:
                map_processor_nodes.add(node_id)
                logger.info(
                    f"Identified node {node_id} as part of a Map processor chain, will skip creating it in main state machine"
                )

        # Create state definitions for each node
        for node in nodes:
            # Skip trigger nodes as they don't need to be created as steps
            if node.data.type.lower() == "trigger":
                logger.info(f"Skipping trigger node {node.id}")
                continue

            # Skip nodes that are used exclusively as Map processors
            if node.id in map_processor_nodes:
                logger.info(f"Skipping node {node.id} as it's used as a Map processor")
                continue

            state_name = node_id_to_state_name.get(node.id)
            if not state_name:
                logger.warning(f"No state name found for node {node.id}, skipping")
                continue

            logger.info(f"Creating state definition for {state_name}")

            if node.data.type.lower() == "flow":
                # Handle flow-type nodes
                try:
                    state_def = self.create_flow_state_definition(
                        node, map_processor_chains
                    )
                    # Remove End: true if it exists, we'll set it later if needed
                    if "End" in state_def:
                        del state_def["End"]
                    # Check if this state has additional states in metadata
                    additional_states = {}
                    if (
                        "__metadata__" in state_def
                        and "additionalStates" in state_def["__metadata__"]
                    ):
                        additional_states = state_def["__metadata__"][
                            "additionalStates"
                        ]
                        # Remove the metadata from the state definition
                        del state_def["__metadata__"]
                        logger.info(
                            f"Found additional states for {state_name}: {list(additional_states.keys())}"
                        )

                    # Add the main state
                    states[state_name] = state_def
                    logger.info(f"Created flow state for {state_name}: {state_def}")

                    # Add any additional states
                    for (
                        additional_state_name,
                        additional_state_def,
                    ) in additional_states.items():
                        states[additional_state_name] = additional_state_def
                        logger.info(
                            f"Added additional state {additional_state_name} for {state_name}"
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to create flow state for node {state_name}: {e}"
                    )
                    continue
            else:
                # Handle Lambda function nodes
                # Use the more specific lambda key that includes the method if available
                lambda_key = self.node_id_to_lambda_key.get(node.id, node.data.id)
                lambda_arn = self.lambda_arns.get(lambda_key)

                if not lambda_arn:
                    logger.warning(
                        f"No Lambda ARN found for node {node.data.id} with key {lambda_key}; creating pass state instead."
                    )
                    # Create a Pass state as a fallback - without End: true
                    states[state_name] = {
                        "Type": "Pass",
                        "Result": {"message": f"No Lambda function for {node.data.id}"},
                    }
                else:
                    # Create the base Task state
                    task_state = {
                        "Type": "Task",
                        "Resource": lambda_arn,
                        "Retry": [
                            {
                                "ErrorEquals": ["Lambda.TooManyRequestsException"],
                                "IntervalSeconds": 1,
                                "MaxAttempts": 5,
                                "BackoffRate": 2.0,
                            },
                            {
                                "ErrorEquals": ["States.ALL"],
                                "IntervalSeconds": 2,
                                "MaxAttempts": self.pipeline.configuration.settings.retryAttempts,
                                "BackoffRate": 2.0,
                            },
                        ],
                    }

                    # Add execution context properties to the first Lambda in the step function
                    if (
                        self.first_lambda_node_id
                        and node.id == self.first_lambda_node_id
                    ):
                        # Check if Parameters already exists
                        if "Parameters" in task_state:
                            # Add execution context properties to existing Parameters
                            task_state["Parameters"].update(
                                {
                                    "executionName.$": "$$.Execution.Name",
                                    "stateMachineArn.$": "$$.StateMachine.Id",
                                }
                            )
                        else:
                            # Create new Parameters with execution context properties
                            # Also include the original event as input
                            task_state["Parameters"] = {
                                "executionName.$": "$$.Execution.Name",
                                "stateMachineArn.$": "$$.StateMachine.Id",
                                # Pass the original event as input
                                "payload.$": "$",
                            }
                        logger.info(
                            f"Added execution context properties to first Lambda task state: {state_name}"
                        )

                    states[state_name] = task_state
                    logger.info(f"Created task state for {state_name}")

        return states

    def _build_lambda_key_mappings(self, nodes: list) -> None:
        """
        Build mappings from node IDs to Lambda ARN keys.

        Args:
            nodes: List of nodes from the pipeline
        """
        for node in nodes:
            if node.id and node.data and node.data.id:
                # Create a more specific key for Lambda ARN mapping that includes the method
                # This ensures different operations (GET, POST) for the same node type get different Lambda functions
                lambda_key = node.data.id
                if (
                    node.data.type.lower() == "integration"
                    and "method" in node.data.configuration
                ):
                    lambda_key = f"{node.data.id}_{node.data.configuration['method']}"
                    # Add operationId to the key if available
                    if (
                        "operationId" in node.data.configuration
                        and node.data.configuration["operationId"]
                    ):
                        lambda_key = (
                            f"{lambda_key}_{node.data.configuration['operationId']}"
                        )
                self.node_id_to_lambda_key[node.id] = lambda_key

    def create_flow_state_definition(
        self, node: Any, map_processor_chains: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """
        Create a Step Function state definition for a flow-type node.

        Args:
            node: Node object containing configuration

        Returns:
            State definition dictionary for the flow node
        """
        logger.info(f"Creating flow state definition for node: {node.id}")

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
                logger.error(
                    f"Failed to read generic YAML for flow node {node.id}: {e}"
                )
                raise ValueError(f"No YAML template found for flow node {node.id}")

        # Get the Step Function step type from the YAML
        step_name = yaml_data["node"]["integration"]["config"]["aws_stepfunction"][
            "step_name"
        ]

        # Create the state definition based on the step type
        state_def = {}

        if step_name == "wait":
            # Wait state
            # Check for Duration first, then fall back to seconds
            # Make sure to convert to int as it might be a string in the configuration
            # Step Functions requires Seconds to be an integer

            duration_value = node.data.configuration.get("parameters").get(
                "Duration", 1
            )
            logger.info(f"Using duration value: {duration_value}")
            try:
                # Convert to integer for Step Functions compatibility
                seconds = int(float(duration_value))
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid duration value: {duration_value}, using default of 1 second"
                )
                seconds = 1

            # Don't set End: true for Wait states, as they often need to loop back to another state
            state_def = {"Type": "Wait", "Seconds": seconds}
        elif step_name == "choice":
            # Choice state
            choices = node.data.configuration.get("choices", [])

            # Ensure we have at least one choice in the Choices array
            if not choices:
                choices = [
                    {"variable": "$.metadata.externalJobStatus", "value": "Completed"}
                ]

            # For Choice states, we'll set placeholder Next values that will be updated later
            # when we connect the edges. We use the node ID as a prefix to ensure uniqueness.
            state_def = {
                "Type": "Choice",
                "Choices": [
                    {
                        "Variable": choice.get(
                            "variable", "$.metadata.externalJobStatus"
                        ),
                        "StringEquals": choice.get("value", "Completed"),
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

            # Check if this Map node has a processor chain
            processor_chain = []
            if map_processor_chains and node.id in map_processor_chains:
                processor_chain = map_processor_chains[node.id]
                logger.info(
                    f"Found processor chain for Map node {node.id}: {processor_chain}"
                )

            if processor_chain:
                # Build a complete iterator with all nodes in the processor chain
                iterator_states = {}
                previous_state_name = None
                first_state_name = None

                for i, processor_id in enumerate(processor_chain):
                    # Find the processor node
                    processor_node = next(
                        (
                            n
                            for n in self.pipeline.configuration.nodes
                            if n.id == processor_id
                        ),
                        None,
                    )
                    if not processor_node:
                        logger.warning(
                            f"Processor node {processor_id} not found in pipeline nodes"
                        )
                        continue

                    # Get the Lambda ARN for this processor node
                    lambda_key = self.node_id_to_lambda_key.get(
                        processor_id, processor_node.data.id
                    )
                    processor_lambda_arn = self.lambda_arns.get(lambda_key)

                    if not processor_lambda_arn:
                        logger.warning(
                            f"No Lambda ARN found for processor node {processor_id} with key {lambda_key}"
                        )
                        continue

                    # Create a state name for this processor
                    processor_label = (
                        processor_node.data.label
                        if hasattr(processor_node.data, "label")
                        and processor_node.data.label
                        else processor_node.data.id
                    )
                    processor_state_name = f"Processor_{i}_{processor_label}"
                    processor_state_name = "".join(
                        c if c.isalnum() else "_" for c in processor_state_name
                    )

                    # Store the first state name for the StartAt property
                    if i == 0:
                        first_state_name = processor_state_name

                    # Create the processor state
                    processor_state = {
                        "Type": "Task",
                        "Resource": processor_lambda_arn,
                        "Retry": [
                            {
                                "ErrorEquals": ["Lambda.TooManyRequestsException"],
                                "IntervalSeconds": 1,
                                "MaxAttempts": 5,
                                "BackoffRate": 2.0,
                            },
                            {
                                "ErrorEquals": ["States.ALL"],
                                "IntervalSeconds": 2,
                                "MaxAttempts": self.pipeline.configuration.settings.retryAttempts,
                                "BackoffRate": 2.0,
                            },
                        ],
                    }

                    # Connect to the previous state if this isn't the first one
                    if previous_state_name:
                        iterator_states[previous_state_name][
                            "Next"
                        ] = processor_state_name
                    # Only mark the last state as End: true
                    if i == len(processor_chain) - 1:
                        processor_state["End"] = True
                        logger.info(
                            f"Marked processor state {processor_state_name} as End: true (last in chain)"
                        )

                    iterator_states[processor_state_name] = processor_state
                    previous_state_name = processor_state_name

                # After the loop, ensure the last state has End: true
                if iterator_states and previous_state_name:
                    if "Next" in iterator_states[previous_state_name]:
                        logger.warning(
                            f"Last state {previous_state_name} in Iterator has Next, removing it and setting End: true"
                        )
                        del iterator_states[previous_state_name]["Next"]

                    if "End" not in iterator_states[previous_state_name]:
                        logger.warning(
                            f"Last state {previous_state_name} in Iterator missing End: true, adding it"
                        )
                        iterator_states[previous_state_name]["End"] = True

                # Create the iterator with all the states
                # Create the iterator with all the states
                if iterator_states and first_state_name:
                    iterator = {"StartAt": first_state_name, "States": iterator_states}
                    logger.info(
                        f"Created complete iterator for Map node {node.id} with {len(iterator_states)} states"
                    )
                else:
                    # Fallback to default iterator if we couldn't build the chain
                    iterator = {
                        "StartAt": "PassState",
                        "States": {"PassState": {"Type": "Pass", "End": True}},
                    }
                    logger.info(
                        f"Created default iterator for Map node {node.id} (no valid processor chain)"
                    )
            else:
                # No processor chain found, create a minimal valid Iterator
                iterator = {
                    "StartAt": "PassState",
                    "States": {"PassState": {"Type": "Pass", "End": True}},
                }
                logger.info(
                    f"Created default Iterator for Map node {node.id} (no processor chain)"
                )

            # Identify previous nodes and determine appropriate ItemsPath
            previous_nodes = self._get_previous_nodes(node.id)
            items_path = self._determine_items_path(node, previous_nodes)
            logger.info(f"Using ItemsPath {items_path} for Map node {node.id}")

            # Check if we need to handle both externalPayloadLocation and externalTaskResults
            if node.data.configuration.get("supportExternalPayload", False):
                logger.info(
                    f"Creating Map state with support for externalPayloadLocation for node {node.id}"
                )

                # Create a state definition that includes a Choice state to check for externalTaskResults
                state_def = {
                    "Type": "Choice",
                    "Choices": [
                        {
                            "Variable": "$.payload.data",
                            "IsPresent": True,
                            "Next": f"{node.id}_Map",
                        }
                    ],
                    "Default": f"{node.id}_StandardMap",
                }

                # Get concurrency limit from parameters in configuration, default to 0
                parameters = node.data.configuration.get("parameters", {})
                concurrency_limit = parameters.get("ConcurrencyLimit", 0)
                # Cap at maximum of 40
                if concurrency_limit > 40:
                    concurrency_limit = 40
                    logger.info(
                        f"Capped concurrency limit to maximum value of 40 for Map node {node.id}"
                    )

                logger.info(
                    f"Using concurrency limit: {concurrency_limit} for Map node {node.id} with external payload support"
                )

                # We'll need to add these states to the state machine later
                # Store them as metadata in the state definition
                map_state = {
                    "Type": "Map",
                    "ItemsPath": "$.payload.data",
                    "Iterator": iterator,
                    "ResultPath": None,
                    "End": True,
                    "Parameters": {"item.$": "$$.Map.Item.Value"},
                    "Retry": [
                        {
                            "ErrorEquals": ["Lambda.TooManyRequestsException"],
                            "IntervalSeconds": 1,
                            "MaxAttempts": 5,
                            "BackoffRate": 2.0,
                        },
                        {
                            "ErrorEquals": ["States.ALL"],
                            "IntervalSeconds": 2,
                            "MaxAttempts": 5,
                            "BackoffRate": 2.0,
                        },
                    ],
                }

                # Only add MaxConcurrency if it's not zero
                if concurrency_limit > 0:
                    map_state["MaxConcurrency"] = concurrency_limit
                    logger.info(
                        f"Set MaxConcurrency to {concurrency_limit} for Map node {node.id}"
                    )

                # Create both Map states with the same configuration
                state_def["__metadata__"] = {
                    "additionalStates": {
                        f"{node.id}_Map": map_state,
                        f"{node.id}_StandardMap": {
                            **map_state  # Use the same configuration
                        },
                    }
                }
            else:
                # Standard Map state without support for externalPayloadLocation
                # Get concurrency limit from parameters in configuration, default to 0
                parameters = node.data.configuration.get("parameters", {})
                concurrency_limit = parameters.get("ConcurrencyLimit", 0)
                # Cap at maximum of 40
                if concurrency_limit > 40:
                    concurrency_limit = 40
                    logger.info(
                        f"Capped concurrency limit to maximum value of 40 for Map node {node.id}"
                    )

                logger.info(
                    f"Using concurrency limit: {concurrency_limit} for Map node {node.id}"
                )

                # Create base state definition
                state_def = {
                    "Type": "Map",
                    "ItemsPath": items_path,
                    "Iterator": iterator,
                    "ResultPath": None,
                    "End": True,
                    # Add Parameters with InputPath to handle potential path mismatches
                    "Parameters": {"item.$": "$$.Map.Item.Value"},
                    "Retry": [
                        {
                            "ErrorEquals": ["Lambda.TooManyRequestsException"],
                            "IntervalSeconds": 1,
                            "MaxAttempts": 5,
                            "BackoffRate": 2.0,
                        },
                        {
                            "ErrorEquals": ["States.ALL"],
                            "IntervalSeconds": 2,
                            "MaxAttempts": 5,
                            "BackoffRate": 2.0,
                        },
                    ],
                }

                # Only add MaxConcurrency if it's not zero
                if concurrency_limit > 0:
                    state_def["MaxConcurrency"] = concurrency_limit
                    logger.info(
                        f"Set MaxConcurrency to {concurrency_limit} for Map node {node.id}"
                    )
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
