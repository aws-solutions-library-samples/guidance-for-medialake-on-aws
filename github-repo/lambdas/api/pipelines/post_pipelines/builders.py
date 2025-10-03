"""
State machine builder for Step Functions.
"""

from typing import Any, Dict

from aws_lambda_powertools import Logger
from graph_utils import GraphAnalyzer
from sanitizers import sanitize_state_name
from state_connector import StateConnector
from state_definitions import StateDefinitionFactory
from validators import StateMachineValidator

logger = Logger()


class StateMachineBuilder:
    """
    Orchestrates the building of AWS Step Functions state machines from pipeline definitions.

    This class coordinates the process of analyzing the pipeline graph, creating state
    definitions, connecting states, and validating the final state machine.
    """

    def __init__(
        self, pipeline: Any, lambda_arns: Dict[str, str], resource_prefix: str
    ):
        """
        Initialize the StateMachineBuilder.

        Args:
            pipeline: Pipeline definition object
            lambda_arns: Dictionary mapping node IDs to Lambda ARNs
            resource_prefix: Resource prefix for naming
        """
        self.pipeline = pipeline
        self.lambda_arns = lambda_arns
        self.resource_prefix = resource_prefix
        self.graph_analyzer = GraphAnalyzer(pipeline)
        # Initialize without first_lambda_node_id, will set it later
        self.state_factory = StateDefinitionFactory(pipeline, lambda_arns)
        self.validator = StateMachineValidator()

        # Will be populated during the build process
        self.node_id_to_state_name = {}
        self.data_id_to_unique_states = {}
        self.states = {}
        self.start_at = None

    def build(self) -> Dict[str, Any]:
        """
        Build the complete state machine definition.

        Returns:
            Complete state machine definition
        """
        logger.info(
            f"Building Step Functions state machine for pipeline: {self.pipeline.name}"
        )

        # Step 1: Create node mappings and analyze graph
        self._create_node_mappings()
        self.graph_analyzer.analyze()

        # Step 2: Identify the root node and determine start state
        root_node_id = self.graph_analyzer.get_root_node()

        # Step 3: Find special edge types
        (
            choice_true_targets,
            choice_false_targets,
            choice_fail_targets,
            map_processor_chains,
        ) = self.graph_analyzer.find_special_edges()

        # Step 3.5: Find first and last Lambda nodes
        first_lambda_node_id, last_lambda_node_id = (
            self.graph_analyzer.find_first_and_last_lambdas()
        )
        logger.info(
            f"Identified first lambda node for execution context properties: {first_lambda_node_id}"
        )

        # Update the state factory with the first Lambda node ID
        self.state_factory.first_lambda_node_id = first_lambda_node_id

        # Step 4: Create state definitions for each node
        self.states = self.state_factory.create_state_definitions(
            self.pipeline.configuration.nodes,
            self.node_id_to_state_name,
            map_processor_chains,
        )

        # Step 5: Determine the start state
        self.start_at = self._determine_start_state(root_node_id)

        # Step 6: Connect states based on edges
        state_connector = StateConnector(
            self.states,
            self.node_id_to_state_name,
            self.graph_analyzer.node_id_to_node,
            map_processor_chains,
        )
        state_connector.connect_states(
            self.pipeline.configuration.edges,
            choice_true_targets,
            choice_false_targets,
            choice_fail_targets,
        )

        # Step 7: Find execution path
        execution_path = self.graph_analyzer.find_execution_path(
            root_node_id, self.node_id_to_state_name
        )

        # Step 8: Ensure terminal states exist
        state_connector.ensure_terminal_states(
            execution_path, self.graph_analyzer.leaf_nodes
        )

        # Step 9: Validate and fix the state machine
        self.validator.validate(self.states, self.start_at)
        self.validator.fix_invalid_states(self.states, self.start_at)

        # Step 10: Build the final definition
        definition = {
            "Comment": f"State machine for pipeline {self.pipeline.name}",
            "StartAt": self.start_at,
            "States": self.states,
        }

        logger.info(f"Built state machine definition with {len(self.states)} states")
        return definition

    def _create_node_mappings(self) -> None:
        """Create mappings between different node ID formats and state names."""
        logger.info("Creating node mappings")

        # First pass: create unique state names for each node
        for node in self.pipeline.configuration.nodes:
            # Create a unique state name that combines the node label and node ID
            # This ensures that each node gets a descriptive and unique state name
            operation_id = node.data.configuration.get("operationId", "")
            label = node.data.label or node.data.type

            # Use sanitize_state_name to create a valid state name
            sanitized_state_name = sanitize_state_name(
                f"{label} {operation_id}", node.id
            )

            # Store the mapping from node ID to unique state name
            self.node_id_to_state_name[node.id] = sanitized_state_name

            # Also store the reverse mapping using data.id for backward compatibility
            if node.data.id not in self.data_id_to_unique_states:
                self.data_id_to_unique_states[node.data.id] = []
            self.data_id_to_unique_states[node.data.id].append(sanitized_state_name)

            logger.info(
                f"Created unique state name for node {node.id}: {sanitized_state_name} (from label: {node.data.label})"
            )

    def _determine_start_state(self, root_node_id: str) -> str:
        """
        Determine the start state based on the root node.

        Args:
            root_node_id: ID of the root node

        Returns:
            Name of the start state
        """
        logger.info(f"Determining start state from root node: {root_node_id}")

        # If the root node is a trigger, find the first non-trigger node connected to it
        if (
            root_node_id
            and root_node_id in self.graph_analyzer.node_id_to_node
            and self.graph_analyzer.node_id_to_node[root_node_id].data.type.lower()
            == "trigger"
        ):
            logger.info(f"Root node {root_node_id} is a trigger, finding next node")
            if (
                root_node_id in self.graph_analyzer.graph
                and self.graph_analyzer.graph[root_node_id]
            ):
                # Get the first target from the graph
                next_node_id = self.graph_analyzer.graph[root_node_id][0]
                next_state_name = self.node_id_to_state_name.get(next_node_id)

                logger.info(f"Using {next_state_name} as start state")
                return next_state_name
            else:
                logger.warning(
                    f"Trigger root node {root_node_id} has no outgoing edges, using first available state"
                )
                # Use the first available state as start state
                first_state = next(iter(self.states)) if self.states else None
                return first_state
        else:
            # For non-trigger root nodes, use the root node's state name
            start_at = self.node_id_to_state_name.get(root_node_id)
            if start_at:
                logger.info(f"Using {start_at} as start state")
                return start_at
            else:
                logger.warning(
                    f"Could not find state name for root node {root_node_id}, using first available state"
                )
                first_state = next(iter(self.states)) if self.states else None
                return first_state
