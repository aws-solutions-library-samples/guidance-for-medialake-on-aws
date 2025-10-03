"""
Validation utilities for Step Functions state machines.
"""

from typing import Any, Dict, Set

from aws_lambda_powertools import Logger

logger = Logger()


class StateMachineValidator:
    """
    Validates Step Functions state machine definitions.

    This class provides utilities for validating state machine definitions
    to ensure they are valid and will work correctly in AWS Step Functions.
    """

    def __init__(self):
        """Initialize the StateMachineValidator."""

    def validate(self, states: Dict[str, Any], start_at: str) -> bool:
        """
        Validate a state machine definition.

        Args:
            states: Dictionary of state definitions
            start_at: Name of the start state

        Returns:
            True if the state machine is valid, False otherwise
        """
        logger.info("Validating state machine definition")

        # Check if start state exists
        if not start_at or start_at not in states:
            logger.error(f"Start state {start_at} does not exist in states dictionary")
            return False

        # Validate each state
        for state_name, state in states.items():
            if not self._validate_state(state_name, state, states):
                return False

        # Ensure there is at least one terminal state
        if not self._has_terminal_state(states):
            logger.error("State machine has no terminal states")
            return False

        logger.info("State machine validation successful")
        return True

    def _validate_state(
        self, state_name: str, state: Dict[str, Any], states: Dict[str, Any]
    ) -> bool:
        """
        Validate a single state definition.

        Args:
            state_name: Name of the state
            state: State definition
            states: Dictionary of all state definitions

        Returns:
            True if the state is valid, False otherwise
        """
        # Check if state has a Type
        if "Type" not in state:
            logger.error(f"State {state_name} has no Type")
            return False

        # Validate based on state type
        state_type = state.get("Type")

        # Validate Choice states
        if state_type == "Choice":
            return self._validate_choice_state(state_name, state, states)

        # Validate Map states
        elif state_type == "Map":
            return self._validate_map_state(state_name, state, states)

        # Validate Task states
        elif state_type == "Task":
            return self._validate_task_state(state_name, state, states)

        # Validate other state types
        else:
            return self._validate_basic_state(state_name, state, states)

    def _validate_choice_state(
        self, state_name: str, state: Dict[str, Any], states: Dict[str, Any]
    ) -> bool:
        """
        Validate a Choice state.

        Args:
            state_name: Name of the state
            state: State definition
            states: Dictionary of all state definitions

        Returns:
            True if the state is valid, False otherwise
        """
        # Check if Choices array exists and is not empty
        if "Choices" not in state or not state["Choices"]:
            logger.error(
                f"Choice state {state_name} has no Choices array or it is empty"
            )
            return False

        # Check if Default exists
        if "Default" not in state:
            logger.warning(f"Choice state {state_name} has no Default path")

        # Validate each choice in Choices array
        for i, choice in enumerate(state["Choices"]):
            # Check if Next exists and points to a valid state
            if "Next" not in choice:
                logger.error(f"Choice {i} in state {state_name} has no Next property")
                return False

            next_state = choice["Next"]
            if next_state not in states:
                logger.error(
                    f"Choice {i} in state {state_name} points to non-existent state {next_state}"
                )
                return False

            # Check if Variable exists
            if "Variable" not in choice:
                logger.error(
                    f"Choice {i} in state {state_name} has no Variable property"
                )
                return False

            # Check if at least one comparison operator exists
            has_comparison = False
            for op in [
                "StringEquals",
                "StringLessThan",
                "StringGreaterThan",
                "StringLessThanEquals",
                "StringGreaterThanEquals",
                "NumericEquals",
                "NumericLessThan",
                "NumericGreaterThan",
                "NumericLessThanEquals",
                "NumericGreaterThanEquals",
                "BooleanEquals",
                "TimestampEquals",
                "TimestampLessThan",
                "TimestampGreaterThan",
                "TimestampLessThanEquals",
                "TimestampGreaterThanEquals",
            ]:
                if op in choice:
                    has_comparison = True
                    break

            if not has_comparison:
                logger.error(
                    f"Choice {i} in state {state_name} has no comparison operator"
                )
                return False

        # If Default exists, check if it points to a valid state
        if "Default" in state:
            default_state = state["Default"]
            if default_state not in states:
                logger.error(
                    f"Default in state {state_name} points to non-existent state {default_state}"
                )
                return False

        return True

    def _validate_map_state(
        self, state_name: str, state: Dict[str, Any], states: Dict[str, Any]
    ) -> bool:
        """
        Validate a Map state.

        Args:
            state_name: Name of the state
            state: State definition
            states: Dictionary of all state definitions

        Returns:
            True if the state is valid, False otherwise
        """
        # Check if Iterator exists
        if "Iterator" not in state:
            logger.error(f"Map state {state_name} has no Iterator property")
            return False

        iterator = state["Iterator"]

        # Check if Iterator has States and StartAt
        if "States" not in iterator:
            logger.error(f"Iterator in Map state {state_name} has no States property")
            return False

        if "StartAt" not in iterator:
            logger.error(f"Iterator in Map state {state_name} has no StartAt property")
            return False

        # Check if StartAt points to a valid state in the Iterator
        start_at = iterator["StartAt"]
        if start_at not in iterator["States"]:
            logger.error(
                f"StartAt in Iterator of Map state {state_name} points to non-existent state {start_at}"
            )
            return False

        # Validate each state in the Iterator
        for iter_state_name, iter_state in iterator["States"].items():
            # Check if state has a Type
            if "Type" not in iter_state:
                logger.error(
                    f"State {iter_state_name} in Iterator of Map state {state_name} has no Type"
                )
                return False
                # Check if Next points to a valid state in the Iterator
                if (
                    "Next" in iter_state
                    and iter_state["Next"] not in iterator["States"]
                ):
                    logger.error(
                        f"Next in state {iter_state_name} of Iterator in Map state {state_name} points to non-existent state {iter_state['Next']}"
                    )
                    return False

                # Check if state has either Next or End property (unless it's a terminal state)
                if (
                    iter_state.get("Type") not in ["Succeed", "Fail"]
                    and "Next" not in iter_state
                    and "End" not in iter_state
                ):
                    logger.warning(
                        f"State {iter_state_name} in Iterator of Map state {state_name} has neither Next nor End property, adding End: true"
                    )
                    iter_state["End"] = True

            # Check if Next exists and points to a valid state
        # Check if Next exists and points to a valid state
        if "Next" in state and state["Next"] not in states:
            logger.error(
                f"Next in Map state {state_name} points to non-existent state {state['Next']}"
            )
            return False

        # Validate ItemsPath
        if "ItemsPath" not in state:
            logger.warning(
                f"Map state {state_name} has no ItemsPath, adding default $.payload.data"
            )
            state["ItemsPath"] = "$.payload.data"
        elif not state["ItemsPath"].startswith("$"):
            logger.warning(
                f"Map state {state_name} has invalid ItemsPath {state['ItemsPath']}, fixing to $.payload.data"
            )
            state["ItemsPath"] = "$.payload.data"

        # Ensure Parameters exists for fallback mechanism
        if "Parameters" not in state:
            logger.info(
                f"Adding Parameters with InputPath to Map state {state_name} for fallback mechanism"
            )
            state["Parameters"] = {"item.$": "$$.Map.Item.Value"}

        # Ensure the last state in the Iterator has End: true
        if "States" in iterator:
            # Find the last state in the execution path
            current_state = iterator.get("StartAt")
            last_state = None

            while current_state:
                last_state = current_state
                current_state_def = iterator["States"].get(current_state, {})
                current_state = current_state_def.get("Next")

            # If we found a last state, ensure it has End: true
            if last_state and last_state in iterator["States"]:
                last_state_def = iterator["States"][last_state]
                if "Type" not in last_state_def or last_state_def.get("Type") not in [
                    "Succeed",
                    "Fail",
                ]:
                    if "Next" in last_state_def:
                        logger.warning(
                            f"Last state {last_state} in Iterator of Map state {state_name} has Next, removing it"
                        )
                        del last_state_def["Next"]

                    if "End" not in last_state_def:
                        logger.warning(
                            f"Last state {last_state} in Iterator of Map state {state_name} missing End: true, adding it"
                        )
                        last_state_def["End"] = True

        return True

    def _validate_task_state(
        self, state_name: str, state: Dict[str, Any], states: Dict[str, Any]
    ) -> bool:
        """
        Validate a Task state.

        Args:
            state_name: Name of the state
            state: State definition
            states: Dictionary of all state definitions

        Returns:
            True if the state is valid, False otherwise
        """
        # Check if Resource exists
        if "Resource" not in state:
            logger.error(f"Task state {state_name} has no Resource property")
            return False

        # Check if Next exists and points to a valid state
        if "Next" in state and state["Next"] not in states:
            logger.error(
                f"Next in Task state {state_name} points to non-existent state {state['Next']}"
            )
            return False

        # Check if End exists when Next doesn't
        if "Next" not in state and "End" not in state:
            logger.error(f"Task state {state_name} has neither Next nor End property")
            return False

        return True

    def _validate_basic_state(
        self, state_name: str, state: Dict[str, Any], states: Dict[str, Any]
    ) -> bool:
        """
        Validate a basic state (Pass, Wait, Succeed, Fail).

        Args:
            state_name: Name of the state
            state: State definition
            states: Dictionary of all state definitions

        Returns:
            True if the state is valid, False otherwise
        """
        state_type = state.get("Type")

        # Succeed and Fail states don't need Next or End
        if state_type in ["Succeed", "Fail"]:
            return True

        # Pass and Wait states need either Next or End
        if state_type in ["Pass", "Wait"]:
            if "Next" in state:
                # Check if Next points to a valid state
                next_state = state["Next"]
                if next_state not in states:
                    logger.error(
                        f"Next in {state_type} state {state_name} points to non-existent state {next_state}"
                    )
                    return False
            elif "End" not in state:
                logger.error(
                    f"{state_type} state {state_name} has neither Next nor End property"
                )
                return False

        return True

    def _has_terminal_state(self, states: Dict[str, Any]) -> bool:
        """
        Check if the state machine has at least one terminal state.

        A terminal state is either a Succeed or Fail state, or a state with End: true.

        Args:
            states: Dictionary of state definitions

        Returns:
            True if the state machine has at least one terminal state, False otherwise
        """
        for state_name, state in states.items():
            if state.get("Type") in ["Succeed", "Fail"] or state.get("End") is True:
                return True

        return False

    def fix_invalid_states(self, states: Dict[str, Any], start_at: str) -> None:
        """
        Fix common issues in state machine definitions.

        Args:
            states: Dictionary of state definitions
            start_at: Name of the start state
        """
        logger.info("Fixing invalid states in state machine definition")

        # Fix Choice states with placeholder Next values
        for state_name, state in states.items():
            if state.get("Type") == "Choice":
                # Fix Choices array
                if "Choices" in state:
                    for choice in state["Choices"]:
                        if "__PLACEHOLDER__" in str(choice.get("Next", "")):
                            # Find a valid state to use as Next
                            valid_next = next(
                                (s for s in states.keys() if s != state_name), None
                            )
                            if valid_next:
                                choice["Next"] = valid_next
                                logger.info(
                                    f"Fixed Choice state {state_name} Choices Next to {valid_next}"
                                )

                # Fix Default
                if "__PLACEHOLDER__" in str(state.get("Default", "")):
                    # Look for a Wait state to use as Default
                    wait_state = next(
                        (
                            s
                            for s, st in states.items()
                            if st.get("Type") == "Wait" and s != state_name
                        ),
                        None,
                    )
                    if wait_state:
                        state["Default"] = wait_state
                        logger.info(
                            f"Fixed Choice state {state_name} Default to Wait state {wait_state}"
                        )
                    else:
                        # If no Wait state, find any valid state
                        valid_default = next(
                            (s for s in states.keys() if s != state_name), None
                        )
                        if valid_default:
                            state["Default"] = valid_default
                            logger.info(
                                f"Fixed Choice state {state_name} Default to {valid_default}"
                            )

        # Fix states that have neither Next nor End properties
        for state_name, state in states.items():
            if (
                state.get("Type") not in ["Succeed", "Fail", "Choice"]
                and "Next" not in state
                and "End" not in state
            ):
                logger.warning(
                    f"State {state_name} has neither Next nor End property, adding End: true"
                )
                state["End"] = True

        # Ensure no state has both End and Next properties
        for state_name, state in states.items():
            if "End" in state and "Next" in state:
                logger.warning(
                    f"State {state_name} has both End and Next properties, removing End"
                )
                del state["End"]

        # Fix Map states with unreachable PassState
        for state_name, state in states.items():
            if (
                state.get("Type") == "Map"
                and "Iterator" in state
                and "States" in state["Iterator"]
            ):
                iterator_states = state["Iterator"]["States"]

                # Check if PassState exists but is not reachable
                if (
                    "PassState" in iterator_states
                    and state["Iterator"].get("StartAt") != "PassState"
                ):
                    # Either remove PassState or make it reachable
                    if len(iterator_states) > 1:
                        # If there are other states, remove PassState
                        del iterator_states["PassState"]
                        logger.info(
                            f"Removed unreachable PassState from Map state {state_name} Iterator"
                        )
                    else:
                        # If PassState is the only state, make it the StartAt
                        state["Iterator"]["StartAt"] = "PassState"
                        logger.info(
                            f"Made PassState reachable in Map state {state_name} Iterator"
                        )

        # Find and handle unreachable states
        reachable_states = self._find_reachable_states(states, start_at)
        unreachable_states = set(states.keys()) - reachable_states

        if unreachable_states:
            logger.warning(f"Found unreachable states: {unreachable_states}")

            # Simply remove all unreachable states from the state machine definition
            # This is the most robust approach as it doesn't rely on specific node names
            for state_name in unreachable_states:
                if state_name in states:
                    logger.info(f"Removing unreachable state: {state_name}")
                    del states[state_name]

        # Ensure at least one terminal state exists
        has_terminal_state = self._has_terminal_state(states)
        if not has_terminal_state and states:
            # Add a Succeed state
            states["SucceedState"] = {"Type": "Succeed"}
            logger.info(
                "Added a Succeed state to ensure at least one terminal state exists"
            )

    def _find_reachable_states(self, states: Dict[str, Any], start_at: str) -> Set[str]:
        """
        Find all states that are reachable from the start state.

        Args:
            states: Dictionary of state definitions
            start_at: Name of the start state

        Returns:
            Set of reachable state names
        """
        if not start_at or start_at not in states:
            return set()

        reachable = set()

        def dfs(state_name):
            if state_name in reachable:
                return

            reachable.add(state_name)
            state = states[state_name]

            # Follow Next if it exists
            if "Next" in state:
                next_state = state["Next"]
                if next_state in states:
                    dfs(next_state)

            # For Choice states, follow all branches
            if state.get("Type") == "Choice":
                # Follow all Choices
                for choice in state.get("Choices", []):
                    if "Next" in choice and choice["Next"] in states:
                        dfs(choice["Next"])

                # Follow Default
                if "Default" in state and state["Default"] in states:
                    dfs(state["Default"])

            # For Map states, follow Next
            if (
                state.get("Type") == "Map"
                and "Next" in state
                and state["Next"] in states
            ):
                dfs(state["Next"])

        dfs(start_at)
        return reachable
