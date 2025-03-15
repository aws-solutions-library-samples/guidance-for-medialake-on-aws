"""
State definition creation for Step Functions state machines.
"""

from typing import Dict, Any, Optional
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
    
    def __init__(self, pipeline: Any, lambda_arns: Dict[str, str]):
        """
        Initialize the StateDefinitionFactory.
        
        Args:
            pipeline: Pipeline definition object
            lambda_arns: Dictionary mapping node IDs to Lambda ARNs
        """
        self.pipeline = pipeline
        self.lambda_arns = lambda_arns
        self.node_id_to_lambda_key = {}
        
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
            target_id = edge.target if hasattr(edge, 'target') else edge.get('target')
            
            if target_id == node_id:
                source_id = edge.source if hasattr(edge, 'source') else edge.get('source')
                source_node = next((n for n in self.pipeline.configuration.nodes if n.id == source_id), None)
                
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
            
        # Always use $.payload.externalTaskResults for Map states
        # This ensures compatibility with 12Labs and similar integrations
        logger.info(f"Using $.payload.externalTaskResults as ItemsPath for Map node {node.id}")
        return "$.payload.externalTaskResults"
        
    def create_state_definitions(self, nodes: list, node_id_to_state_name: Dict[str, str]) -> Dict[str, Any]:
        """
        Create state definitions for all nodes.
        
        Args:
            nodes: List of nodes from the pipeline
            node_id_to_state_name: Mapping from node IDs to state names
            
        Returns:
            Dictionary of state definitions
        """
        states = {}
        
        # Build lambda key mappings
        self._build_lambda_key_mappings(nodes)
        
        # Track nodes that are used as Map processors to avoid duplicate states
        map_processor_nodes = set()
        
        # First pass: identify Map processor nodes
        for node in nodes:
            if node.data.type.lower() == "flow" and node.data.id == "map":
                # Find edges where this Map node is the source with a "Processor" handle
                for edge in self.pipeline.configuration.edges:
                    source_id = edge.source if hasattr(edge, 'source') else edge.get('source')
                    source_handle = edge.sourceHandle if hasattr(edge, 'sourceHandle') else edge.get('sourceHandle')
                    target_id = edge.target if hasattr(edge, 'target') else edge.get('target')
                    
                    if source_id == node.id and source_handle == "Processor":
                        # This target node is used as a Map processor
                        map_processor_nodes.add(target_id)
                        logger.info(f"Identified node {target_id} as a Map processor, will skip creating it in main state machine")
        
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
                    state_def = self.create_flow_state_definition(node)
                    # Remove End: true if it exists, we'll set it later if needed
                    if "End" in state_def:
                        del state_def["End"]
                    states[state_name] = state_def
                    logger.info(f"Created flow state for {state_name}: {state_def}")
                except Exception as e:
                    logger.error(f"Failed to create flow state for node {state_name}: {e}")
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
                    states[state_name] = {
                        "Type": "Task",
                        "Resource": lambda_arn,
                        "Retry": [
                            {
                                "ErrorEquals": ["States.ALL"],
                                "IntervalSeconds": 2,
                                "MaxAttempts": self.pipeline.configuration.settings.retryAttempts,
                                "BackoffRate": 2.0,
                            }
                        ],
                    }
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
                if node.data.type.lower() == "integration" and "method" in node.data.configuration:
                    lambda_key = f"{node.data.id}_{node.data.configuration['method']}"
                    # Add operationId to the key if available
                    if "operationId" in node.data.configuration and node.data.configuration["operationId"]:
                        lambda_key = f"{lambda_key}_{node.data.configuration['operationId']}"
                self.node_id_to_lambda_key[node.id] = lambda_key
                
    def create_flow_state_definition(self, node: Any) -> Dict[str, Any]:
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
            # Check for Duration first, then fall back to seconds
            # Make sure to convert to int as it might be a string in the configuration
            # Step Functions requires Seconds to be an integer

            duration_value = node.data.configuration.get("parameters").get("Duration", 1)
            logger.info(f"Using duration value: {duration_value}")
            try:
                # Convert to integer for Step Functions compatibility
                seconds = int(float(duration_value))
            except (ValueError, TypeError):
                logger.warning(f"Invalid duration value: {duration_value}, using default of 1 second")
                seconds = 1
            
            # Don't set End: true for Wait states, as they often need to loop back to another state
            state_def = {"Type": "Wait", "Seconds": seconds}
        elif step_name == "choice":
            # Choice state
            choices = node.data.configuration.get("choices", [])
            
            # Ensure we have at least one choice in the Choices array
            if not choices:
                choices = [{"variable": "$.payload.externalTaskStatus", "value": "ready"}]
            
            # For Choice states, we'll set placeholder Next values that will be updated later
            # when we connect the edges. We use the node ID as a prefix to ensure uniqueness.
            state_def = {
                "Type": "Choice",
                "Choices": [
                    {
                        "Variable": choice.get("variable", "$.payload.externalTaskStatus"),
                        "StringEquals": choice.get("value", "ready"),
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
            
            # For Map states, we need to check if there's a processor node connected to it
            processor_node_id = None
            processor_lambda_arn = None
            
            # Look for edges where this Map node is the source with a "Processor" handle
            for edge in self.pipeline.configuration.edges:
                source_id = edge.source if hasattr(edge, 'source') else edge.get('source')
                source_handle = edge.sourceHandle if hasattr(edge, 'sourceHandle') else edge.get('sourceHandle')
                target_id = edge.target if hasattr(edge, 'target') else edge.get('target')
                
                if source_id == node.id and source_handle == "Processor":
                    processor_node_id = target_id
                    logger.info(f"Found processor node {processor_node_id} for Map node {node.id}")
                    break
            
            # If we found a processor node, get its Lambda ARN
            if processor_node_id:
                # Find the target node in the pipeline nodes
                processor_node = next((n for n in self.pipeline.configuration.nodes if n.id == processor_node_id), None)
                if processor_node:
                    # Get the Lambda ARN for this node
                    lambda_key = processor_node.data.id
                    if processor_node.data.type.lower() == "integration" and "method" in processor_node.data.configuration:
                        lambda_key = f"{processor_node.data.id}_{processor_node.data.configuration['method']}"
                        if "operationId" in processor_node.data.configuration and processor_node.data.configuration["operationId"]:
                            lambda_key = f"{lambda_key}_{processor_node.data.configuration['operationId']}"
                    
                    processor_lambda_arn = self.lambda_arns.get(lambda_key)
                    logger.info(f"Found Lambda ARN for processor node: {processor_lambda_arn}")
            
            # Create a custom Iterator with the processor node if found
            if processor_lambda_arn:
                # Create a more descriptive state name based on the processor node's label or ID
                if processor_node:
                    # Use the processor node's label if available, otherwise use its ID
                    processor_label = processor_node.data.label if hasattr(processor_node.data, 'label') and processor_node.data.label else processor_node.data.id
                    # Sanitize the label to create a valid state name
                    processor_state_name = "".join(c if c.isalnum() else "_" for c in processor_label)
                    # Ensure it starts with a letter
                    if not processor_state_name[0].isalpha():
                        processor_state_name = f"Processor_{processor_state_name}"
                else:
                    # Fallback to a generic name if processor_node is not available
                    processor_state_name = "ProcessorState"
                
                iterator = {
                    "StartAt": processor_state_name,
                    "States": {
                        processor_state_name: {
                            "Type": "Task",
                            "Resource": processor_lambda_arn,
                            "Retry": [
                                {
                                    "ErrorEquals": ["States.ALL"],
                                    "IntervalSeconds": 2,
                                    "MaxAttempts": self.pipeline.configuration.settings.retryAttempts,
                                    "BackoffRate": 2.0
                                }
                            ],
                            "End": True
                        }
                    }
                }
                logger.info(f"Created custom Iterator with processor '{processor_state_name}' for Map node {node.id}")
            else:
                # Create a minimal valid Iterator if no processor node found
                iterator = {
                    "StartAt": "PassState",
                    "States": {
                        "PassState": {
                            "Type": "Pass",
                            "End": True
                        }
                    }
                }
                logger.info(f"Created default Iterator for Map node {node.id}")
            
            # Identify previous nodes and determine appropriate ItemsPath
            previous_nodes = self._get_previous_nodes(node.id)
            items_path = self._determine_items_path(node, previous_nodes)
            logger.info(f"Using ItemsPath {items_path} for Map node {node.id}")
            
            state_def = {
                "Type": "Map",
                "ItemsPath": items_path,
                "MaxConcurrency": node.data.configuration.get("maxConcurrency", 0),
                "Iterator": iterator,
                "End": True,
                # Add Parameters with InputPath to handle potential path mismatches
                "Parameters": {
                    "item.$": "$$.Map.Item.Value"
                }
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