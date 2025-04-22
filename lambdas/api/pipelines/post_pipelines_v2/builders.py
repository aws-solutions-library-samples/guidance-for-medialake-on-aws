"""
State machine builder for Step Functions.
"""

from typing import Dict, Any, List, Set, Optional
import shortuuid
import boto3
import json
import os
from lambda_operations import get_zip_file_key
from config import IAC_ASSETS_BUCKET, INGEST_EVENT_BUS_NAME, EXTERNAL_PAYLOAD_BUCKET
from aws_lambda_powertools import Logger

from graph_utils import GraphAnalyzer
from state_definitions import StateDefinitionFactory
from state_connector import StateConnector
from validators import StateMachineValidator
from sanitizers import sanitize_state_name

logger = Logger()


class StateMachineBuilder:
    """
    Orchestrates the building of AWS Step Functions state machines from pipeline definitions.
    
    This class coordinates the process of analyzing the pipeline graph, creating state
    definitions, connecting states, and validating the final state machine.
    """
    
    def __init__(self, pipeline: Any, lambda_arns: Dict[str, str], resource_prefix: str):
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
        logger.info(f"Building Step Functions state machine for pipeline: {self.pipeline.name}")
        
        # Step 1: Create node mappings and analyze graph
        self._create_node_mappings()
        self.graph_analyzer.analyze()
        
        # Step 2: Identify the root node and determine start state
        root_node_id = self.graph_analyzer.get_root_node()
        
        # Step 3: Find special edge types
        choice_true_targets, choice_false_targets, map_processor_chains = self.graph_analyzer.find_special_edges()
        
        # Step 4: Create state definitions for each node
        self.states = self.state_factory.create_state_definitions(
            self.pipeline.configuration.nodes,
            self.node_id_to_state_name,
            map_processor_chains
        )
        
        # Step 5: Determine the start state
        self.start_at = self._determine_start_state(root_node_id)
        
        # Step 6: Connect states based on edges
        state_connector = StateConnector(
            self.states,
            self.node_id_to_state_name,
            self.graph_analyzer.node_id_to_node,
            map_processor_chains
        )
        state_connector.connect_states(
            self.pipeline.configuration.edges,
            choice_true_targets,
            choice_false_targets
        )
        
        # Step 7: Find execution path
        execution_path = self.graph_analyzer.find_execution_path(
            root_node_id,
            self.node_id_to_state_name
        )
        
        # Step 8: Ensure terminal states exist
        state_connector.ensure_terminal_states(
            execution_path,
            self.graph_analyzer.leaf_nodes
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
                f"{label} {operation_id}",
                node.id
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
        
        # Create the pipeline_input_formatter state
        input_formatter_state_name = "PipelineInputFormatter"
        
        # Get environment variables
        account_id = os.environ.get("ACCOUNT_ID", "")
        region = os.environ.get("AWS_REGION", "us-east-1")
        resource_prefix = os.environ.get("RESOURCE_PREFIX", "")
        
        # Get the zip file key for the pipeline_input_formatter Lambda
        zip_file_prefix = "lambda-code/nodes/utility/PipelineInputFormatterLambdaDeployment"
        try:
            zip_file_key = get_zip_file_key(IAC_ASSETS_BUCKET, zip_file_prefix)
            logger.info(f"Found zip file for pipeline_input_formatter: {zip_file_key}")
        except Exception as e:
            logger.error(f"Failed to find zip file for pipeline_input_formatter: {e}")
            # Fallback to a default ARN pattern if we can't find the zip file
            zip_file_key = None
        
        # Construct the ARN for the pipeline_input_formatter Lambda
        if zip_file_key:
            # Use the zip file to create a unique function name with shortuuid
            uuid = shortuuid.uuid()
            function_name = f"{resource_prefix}_{uuid}_pipeline_input_formatter"
            
            # Create the Lambda function if it doesn't exist
            lambda_client = boto3.client("lambda")
            try:
                # Check if the function already exists and delete it if it does
                try:
                    lambda_client.get_function(FunctionName=function_name)
                    logger.info(f"Lambda function {function_name} already exists, deleting it")
                    lambda_client.delete_function(FunctionName=function_name)
                    logger.info(f"Deleted Lambda function {function_name}")
                except lambda_client.exceptions.ResourceNotFoundException:
                    # Create the Lambda function
                    logger.info(f"Creating Lambda function {function_name}")
                    
                    # Create a role for the Lambda function
                    iam_client = boto3.client("iam")
                    role_name = f"{resource_prefix}_pipeline_input_formatter_role"
                    
                    # Check if the role already exists
                    try:
                        response = iam_client.get_role(RoleName=role_name)
                        role_arn = response["Role"]["Arn"]
                        logger.info(f"Role {role_name} already exists with ARN: {role_arn}")
                    except iam_client.exceptions.NoSuchEntityException:
                        # Create the role
                        logger.info(f"Creating role {role_name}")
                        trust_policy = {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Principal": {"Service": "lambda.amazonaws.com"},
                                    "Action": "sts:AssumeRole"
                                }
                            ]
                        }
                        
                        response = iam_client.create_role(
                            RoleName=role_name,
                            AssumeRolePolicyDocument=json.dumps(trust_policy)
                        )
                        role_arn = response["Role"]["Arn"]
                        
                        # Attach policies to the role
                        iam_client.attach_role_policy(
                            RoleName=role_name,
                            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                        )
                        
                        # Wait for the role to propagate
                        logger.info(f"Waiting for role {role_name} to propagate")
                        import time
                        time.sleep(10)
                    
                    # Create the Lambda function
                    lambda_client.create_function(
                        FunctionName=function_name,
                        Runtime="python3.12",
                        Role=role_arn,
                        Handler="index.lambda_handler",
                        Code={"S3Bucket": IAC_ASSETS_BUCKET, "S3Key": zip_file_key},
                        Timeout=300,
                        MemorySize=1024,
                        Environment={
                            "Variables": {
                                "EVENT_BUS_NAME": INGEST_EVENT_BUS_NAME or "default",
                                "EXTERNAL_PAYLOAD_BUCKET": EXTERNAL_PAYLOAD_BUCKET or ""
                            }
                        }
                    )
                    logger.info(f"Created Lambda function {function_name}")
                
                # Get the Lambda function ARN
                response = lambda_client.get_function(FunctionName=function_name)
                input_formatter_arn = response["Configuration"]["FunctionArn"]
                logger.info(f"Using Lambda function ARN: {input_formatter_arn}")
            except Exception as e:
                logger.error(f"Failed to create/get Lambda function: {e}")
                
                raise Exception(f"Failed to create or get pipeline_input_formatter Lambda function: {e}")
        else:
            # Hard fail if zip file key is not found
            raise Exception("Failed to find zip file for pipeline_input_formatter Lambda function")
        
        # Add the pipeline_input_formatter state to the states dictionary
        self.states[input_formatter_state_name] = {
            "Type": "Task",
            "Resource": input_formatter_arn,
            "Next": None,  # Will be set later
            "Comment": "Format the trigger input event to the middleware payload format",
            "Retry": [
                {
                    "ErrorEquals": ["Lambda.TooManyRequestsException"],
                    "IntervalSeconds": 1,
                    "MaxAttempts": 5,
                    "BackoffRate": 2.0
                },
                {
                    "ErrorEquals": ["States.ALL"],
                    "IntervalSeconds": 2,
                    "MaxAttempts": 5,
                    "BackoffRate": 2.0
                }
            ]
        }
        
        # If the root node is a trigger, find the first non-trigger node connected to it
        if (
            root_node_id
            and root_node_id in self.graph_analyzer.node_id_to_node
            and self.graph_analyzer.node_id_to_node[root_node_id].data.type.lower() == "trigger"
        ):
            logger.info(f"Root node {root_node_id} is a trigger, finding next node")
            if root_node_id in self.graph_analyzer.graph and self.graph_analyzer.graph[root_node_id]:
                # Get the first target from the graph
                next_node_id = self.graph_analyzer.graph[root_node_id][0]
                next_state_name = self.node_id_to_state_name.get(next_node_id)
                
                # Set the Next field of the input_formatter state to the next state
                self.states[input_formatter_state_name]["Next"] = next_state_name
                
                logger.info(
                    f"Using PipelineInputFormatter as start state, which will then go to {next_state_name}"
                )
                return input_formatter_state_name
            else:
                logger.warning(
                    f"Trigger root node {root_node_id} has no outgoing edges, using first available state"
                )
                # Use the first available state as start state
                first_state = next(iter(self.states)) if self.states else None
                if first_state and first_state != input_formatter_state_name:
                    self.states[input_formatter_state_name]["Next"] = first_state
                    return input_formatter_state_name
                return first_state
        else:
            # For non-trigger root nodes, still insert the input formatter as the first step
            start_at = self.node_id_to_state_name.get(root_node_id)
            if start_at:
                self.states[input_formatter_state_name]["Next"] = start_at
                logger.info(f"Using PipelineInputFormatter as start state, which will then go to {start_at}")
                return input_formatter_state_name
            else:
                logger.warning(f"Could not find state name for root node {root_node_id}, using first available state")
                first_state = next(iter(self.states)) if self.states else None
                if first_state and first_state != input_formatter_state_name:
                    self.states[input_formatter_state_name]["Next"] = first_state
                    return input_formatter_state_name
                return first_state