"""
State connector for Step Functions state machines.
"""

from typing import Any, Dict, List, Optional, Set

from aws_lambda_powertools import Logger

logger = Logger()


class StateConnector:
    """
    Handles connecting states in a Step Functions state machine based on pipeline edges.
    """

    def __init__(
        self,
        states: Dict[str, Any],
        node_id_to_state_name: Dict[str, str],
        node_id_to_node: Dict[str, Any],
        map_processor_chains: Optional[Dict[str, List[str]]] = None,
    ):
        """
        Initialize the StateConnector.

        Args:
            states: Dictionary of state definitions
            node_id_to_state_name: Mapping from node IDs to state names
            node_id_to_node: Mapping from node IDs to node objects
        """
        self.states = states
        self.node_id_to_state_name = node_id_to_state_name
        self.node_id_to_node = node_id_to_node
        self.choice_branch_targets = (
            {}
        )  # Map from target state name to source Choice state name
        self.map_processor_chains = (
            map_processor_chains or {}
        )  # Map from Map node ID to list of processor node IDs

    def connect_states(
        self,
        edges: List[Any],
        choice_true_targets: Dict[str, str],
        choice_false_targets: Dict[str, str],
        choice_fail_targets: Dict[str, str] = None,
    ) -> None:
        """
        Connect states based on edges in the pipeline.

        Args:
            edges: List of edges from the pipeline
            choice_true_targets: Dictionary mapping Choice node IDs to their "true" target node IDs
            choice_false_targets: Dictionary mapping Choice node IDs to their "false" target node IDs
            choice_fail_targets: Dictionary mapping Choice node IDs to their "fail" target node IDs
        """
        # Initialize choice_fail_targets if not provided
        if choice_fail_targets is None:
            choice_fail_targets = {}
        logger.info("Connecting states based on edges")

        # Connect states based on edges
        for edge in edges:
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
            source_state_name = self.node_id_to_state_name.get(source_id)
            target_state_name = self.node_id_to_state_name.get(target_id)

            logger.info(
                f"Connecting: {source_id} ({source_state_name}) -> {target_id} ({target_state_name}), sourceHandle: {source_handle}"
            )

            if source_state_name in self.states and target_state_name in self.states:
                source_state = self.states[source_state_name]
                self.node_id_to_node.get(source_id)

                # Skip if the source state is a terminal state
                if source_state.get("Type") in ["Succeed", "Fail"]:
                    continue

                # Handle Choice states specially
                if source_state.get("Type") == "Choice":
                    self._connect_choice_state(
                        source_id,
                        target_id,
                        source_state_name,
                        target_state_name,
                        source_handle,
                        choice_true_targets,
                        choice_false_targets,
                        choice_fail_targets,
                    )
                # Handle Map states specially
                elif source_state.get("Type") == "Map":
                    self._connect_map_state(
                        source_id,
                        target_id,
                        source_state_name,
                        target_state_name,
                        source_handle,
                    )
                else:
                    # For non-Choice states, handle normally
                    # Remove End: True if it exists
                    if "End" in source_state:
                        del source_state["End"]

                    # Add Next property
                    source_state["Next"] = target_state_name
                    logger.info(f"Connected {source_state_name} -> {target_state_name}")

    def _connect_choice_state(
        self,
        source_id: str,
        target_id: str,
        source_state_name: str,
        target_state_name: str,
        source_handle: Optional[str],
        choice_true_targets: Dict[str, str],
        choice_false_targets: Dict[str, str],
        choice_fail_targets: Optional[Dict[str, str]] = None,
    ) -> None:
        # Initialize choice_fail_targets if not provided
        if choice_fail_targets is None:
            choice_fail_targets = {}
        """
        Connect a Choice state to its target states.

        Args:
            source_id: ID of the source node
            target_id: ID of the target node
            source_state_name: Name of the source state
            target_state_name: Name of the target state
            source_handle: Optional handle from the source node
            choice_true_targets: Dictionary mapping Choice node IDs to their "true" target node IDs
            choice_false_targets: Dictionary mapping Choice node IDs to their "false" target node IDs
        """
        source_state = self.states[source_state_name]

        # Check if this node has identified true/false/fail targets from the first pass
        has_true_target = source_id in choice_true_targets
        has_false_target = source_id in choice_false_targets
        has_fail_target = source_id in choice_fail_targets

        if has_true_target and has_false_target:
            true_target_id = choice_true_targets[source_id]
            false_target_id = choice_false_targets[source_id]

            true_target_state = self.node_id_to_state_name.get(true_target_id)
            false_target_state = self.node_id_to_state_name.get(false_target_id)

            # Get fail target if available
            fail_target_state = None
            if has_fail_target:
                fail_target_id = choice_fail_targets[source_id]
                fail_target_state = self.node_id_to_state_name.get(fail_target_id)
                logger.info(
                    f"Found fail target for Choice state {source_state_name}: {fail_target_state}"
                )

            if true_target_state and false_target_state:
                # Set the Choices array to point to the true target
                if "Choices" in source_state and source_state["Choices"]:
                    # First choice is for "Completed" status
                    for choice in source_state["Choices"]:
                        if choice.get("StringEquals") == "Completed":
                            choice["Next"] = true_target_state
                            logger.info(
                                f"Set Choice true path: {source_state_name} -> {true_target_state}"
                            )

                # Set the Default to point to the false target
                source_state["Default"] = false_target_state
                logger.info(
                    f"Set Choice false path: {source_state_name} -> {false_target_state}"
                )

                # Add a Fail condition if we have a fail target
                if fail_target_state:
                    # Check if we already have a Fail condition
                    has_fail_condition = False
                    for choice in source_state["Choices"]:
                        if choice.get("StringEquals") == "Failed":
                            choice["Next"] = fail_target_state
                            has_fail_condition = True
                            logger.info(
                                f"Updated existing Fail condition in Choice state {source_state_name} to point to {fail_target_state}"
                            )

                    # If no Fail condition exists, add one
                    if not has_fail_condition:
                        source_state["Choices"].append(
                            {
                                "Variable": "$.metadata.externalJobStatus",
                                "StringEquals": "Failed",
                                "Next": fail_target_state,
                            }
                        )
                        logger.info(
                            f"Added Fail condition to Choice state {source_state_name} pointing to {fail_target_state}"
                        )

                # Track these targets as Choice branch targets
                self.choice_branch_targets[true_target_state] = source_state_name
                self.choice_branch_targets[false_target_state] = source_state_name
                if fail_target_state:
                    self.choice_branch_targets[fail_target_state] = source_state_name

                return

        # Fall back to the original logic if we don't have identified true/false targets
        # Check if this is a conditional edge (has a sourceHandle)
        if source_handle in ["condition_true", "condition_true_output", "Completed"]:
            # This is the "true" path from the Choice
            if "Choices" in source_state and source_state["Choices"]:
                # Replace the placeholder with the actual target
                for choice in source_state["Choices"]:
                    if "__PLACEHOLDER__" in str(choice.get("Next", "")):
                        choice["Next"] = target_state_name
                        logger.info(
                            f"Connected Choice true path: {source_state_name} -> {target_state_name}"
                        )
            # Track this target as a Choice branch target
            self.choice_branch_targets[target_state_name] = source_state_name
            logger.info(
                f"Tracking Choice branch target: {target_state_name} from {source_state_name}"
            )

        elif source_handle in [
            "condition_false",
            "condition_false_output",
            "In Progress",
        ]:
            # This is the "false" path from the Choice (Default)
            if "Default" in source_state and "__PLACEHOLDER__" in str(
                source_state["Default"]
            ):
                source_state["Default"] = target_state_name
                logger.info(
                    f"Connected Choice default path: {source_state_name} -> {target_state_name}"
                )
            # Track this target as a Choice branch target
            self.choice_branch_targets[target_state_name] = source_state_name
            logger.info(
                f"Tracking Choice branch target: {target_state_name} from {source_state_name}"
            )

        elif source_handle == "Fail":
            # This is the "Fail" path from the Choice
            # We need to add a new choice condition for the Fail path
            if "Choices" in source_state:
                # Check if we already have a Fail condition
                has_fail_condition = False
                for choice in source_state["Choices"]:
                    if choice.get("StringEquals") == "Failed":
                        choice["Next"] = target_state_name
                        has_fail_condition = True
                        logger.info(
                            f"Updated existing Fail condition in Choice state {source_state_name} to point to {target_state_name}"
                        )
                        break

                # If no Fail condition exists, add one
                if not has_fail_condition:
                    source_state["Choices"].append(
                        {
                            "Variable": "$.metadata.externalJobStatus",
                            "StringEquals": "Failed",
                            "Next": target_state_name,
                        }
                    )
                    logger.info(
                        f"Added Fail condition to Choice state {source_state_name} pointing to {target_state_name}"
                    )

            # Track this target as a Choice branch target
            self.choice_branch_targets[target_state_name] = source_state_name
            logger.info(
                f"Tracking Choice Fail branch target: {target_state_name} from {source_state_name}"
            )

        else:
            # If no sourceHandle but it's a Choice state, this might be a regular connection
            logger.warning(
                f"Choice state {source_state_name} has a connection without a sourceHandle"
            )

            # If Choices is empty or Default is not set, set them with the target
            if "Choices" not in source_state or not source_state["Choices"]:
                source_state["Choices"] = [
                    {
                        "Variable": "$.metadata.externalJobStatus",
                        "StringEquals": "Completed",
                        "Next": target_state_name,
                    }
                ]

            if "Default" not in source_state or "__PLACEHOLDER__" in str(
                source_state["Default"]
            ):
                source_state["Default"] = target_state_name

    def _connect_map_state(
        self,
        source_id: str,
        target_id: str,
        source_state_name: str,
        target_state_name: str,
        source_handle: Optional[str],
    ) -> None:
        """
        Connect a Map state to its target states.

        Args:
            source_id: ID of the source node
            target_id: ID of the target node
            source_state_name: Name of the source state
            target_state_name: Name of the target state
            source_handle: Optional handle from the source node
        """
        source_state = self.states[source_state_name]

        # Check if this is a connection from a Map state's special handle
        if source_handle in ["Processor", "Next"]:
            # For "Next" handle, connect to the next state after the Map
            if source_handle == "Next":
                # Remove End: true if it exists
                if "End" in source_state:
                    del source_state["End"]

                # Set Next to the target state
                source_state["Next"] = target_state_name
                logger.info(
                    f"Connected Map state {source_state_name} Next to {target_state_name}"
                )

            # For "Processor" handle, we don't need to do anything here
            # The processor chain is now handled in the state definition creation
            elif source_handle == "Processor":
                logger.info(
                    f"Map state {source_state_name} processor chain is handled in state definitions"
                )
        else:
            # For regular connections, just connect normally
            # Remove End: true if it exists
            if "End" in source_state:
                del source_state["End"]

            # Set Next to the target state
            source_state["Next"] = target_state_name
            logger.info(
                f"Connected Map state {source_state_name} to {target_state_name}"
            )

    def ensure_terminal_states(
        self, execution_path: List[str], leaf_node_ids: Set[str]
    ) -> None:
        """
        Ensure at least one terminal state exists in the state machine.

        Args:
            execution_path: List of state names in execution order
            leaf_node_ids: Set of node IDs that are leaf nodes (no outgoing edges)
        """
        logger.info("Ensuring terminal states exist")

        # Ensure at least one state has End: true or is a terminal state
        has_terminal_state = False

        # First check if any state is already a terminal state
        for state_id, state in self.states.items():
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
                leaf_state_name = self.node_id_to_state_name.get(leaf_id)
                if leaf_state_name and leaf_state_name in self.states:
                    # Only mark as terminal if it doesn't have a Next property
                    if "Next" not in self.states[leaf_state_name]:
                        self.states[leaf_state_name]["End"] = True
                        logger.info(
                            f"Marked leaf node {leaf_state_name} as a terminal state"
                        )
                        has_terminal_state = True
                        break  # One terminal state is enough

        # If still no terminal state, try to find any state without a Next property
        if not has_terminal_state:
            for state_id, state in self.states.items():
                if "Next" not in state and state.get("Type") not in ["Succeed", "Fail"]:
                    state["End"] = True
                    logger.info(f"Marked state {state_id} as a terminal state")
                    has_terminal_state = True
                    break  # One terminal state is enough

        # If still no terminal state, forcibly mark the last state as terminal
        if not has_terminal_state and self.states:
            if execution_path:
                last_state_id = execution_path[-1]
                if last_state_id in self.states:
                    # If it has a Next property, remove it
                    if "Next" in self.states[last_state_id]:
                        del self.states[last_state_id]["Next"]

                    # Add End: true unless it's already a terminal state
                    if self.states[last_state_id].get("Type") not in [
                        "Succeed",
                        "Fail",
                    ]:
                        self.states[last_state_id]["End"] = True
                        logger.info(
                            f"Marked last state in execution path {last_state_id} as End: true"
                        )
            else:
                # If no execution path, use the last state in the dictionary
                last_state_id = list(self.states.keys())[-1]
                # Remove Next if it exists
                if "Next" in self.states[last_state_id]:
                    logger.warning(
                        f"Removing Next from state {last_state_id} to make it terminal"
                    )
                    del self.states[last_state_id]["Next"]

                # Add End: true
                self.states[last_state_id]["End"] = True
                logger.info(
                    f"Forcibly marked last state {last_state_id} as a terminal state"
                )

        # Add a Succeed state as a last resort if there are no states at all
        if not self.states:
            logger.warning("No states found, adding a dummy Succeed state")
            self.states["DummySucceedState"] = {"Type": "Succeed"}
