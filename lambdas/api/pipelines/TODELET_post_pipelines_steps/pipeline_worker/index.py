"""
Lambda function that acts as a worker for the pipeline creation Step Function.
This Lambda handles the pipeline creation process directly without relying on imports from other modules.
"""

import json
import os
import boto3
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

# Initialize AWS clients
lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')
sfn_client = boto3.client('stepfunctions')
events_client = boto3.client('events')

# Get environment variables
PIPELINES_TABLE = os.environ.get("PIPELINES_TABLE")
NODE_TABLE = os.environ.get("NODE_TABLE")
IAC_ASSETS_BUCKET = os.environ.get("IAC_ASSETS_BUCKET")
NODE_TEMPLATES_BUCKET = os.environ.get("NODE_TEMPLATES_BUCKET")
INGEST_EVENT_BUS_NAME = os.environ.get("INGEST_EVENT_BUS_NAME")
ACCOUNT_ID = os.environ.get("ACCOUNT_ID")
RESOURCE_PREFIX = os.environ.get("RESOURCE_PREFIX")

# Define the models (copied from post_pipelines_v2/models.py)
class NodeData(BaseModel):
    id: str
    type: str
    label: str
    description: str
    icon: Dict[str, Any]
    inputTypes: List[Union[str, Dict[str, Any]]] = Field(default_factory=list)
    outputTypes: List[Union[str, Dict[str, Any]]] = Field(default_factory=list)
    configuration: Dict[str, Any]


class Node(BaseModel):
    id: str
    type: str
    position: Dict[str, Any]
    width: str
    height: str
    data: NodeData


class Edge(BaseModel):
    source: str
    sourceHandle: Optional[str]
    target: str
    targetHandle: Optional[str]
    id: str
    type: str
    data: Dict[str, Any]


class Settings(BaseModel):
    autoStart: bool
    retryAttempts: int
    timeout: int


class Configuration(BaseModel):
    nodes: List[Node]
    edges: List[Edge]
    settings: Settings


class PipelineDefinition(BaseModel):
    name: str
    description: str
    configuration: Configuration

# Simplified versions of the functions from post_pipelines_v2
def get_pipeline_by_name(pipeline_name: str) -> Optional[Dict[str, Any]]:
    """
    Get pipeline record from DynamoDB by name.
    
    Args:
        pipeline_name: Name of the pipeline to look up
        
    Returns:
        Pipeline record if found, None otherwise
    """
    print(f"Looking up pipeline with name: {pipeline_name}")
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
            return items[0]
        return None
    except Exception as e:
        print(f"Error looking up pipeline: {e}")
        return None

def create_lambda_function(pipeline_name: str, node: Any) -> Optional[str]:
    """
    Simplified version that just returns a dummy ARN.
    In a real implementation, this would create a Lambda function.
    """
    print(f"Creating Lambda function for node: {node.id}")
    return f"arn:aws:lambda:{os.environ.get('AWS_REGION', 'us-east-1')}:{ACCOUNT_ID}:function:{RESOURCE_PREFIX}-{pipeline_name}-{node.id}"

def build_step_function_definition(pipeline: Any, lambda_arns: Dict[str, str]) -> Dict[str, Any]:
    """
    Simplified version that returns a dummy Step Function definition.
    In a real implementation, this would build a Step Function definition.
    """
    print(f"Building Step Function definition for pipeline: {pipeline.name}")
    return {
        "Comment": f"State machine for pipeline {pipeline.name}",
        "StartAt": "Start",
        "States": {
            "Start": {
                "Type": "Pass",
                "End": True
            }
        }
    }

def create_step_function(pipeline_name: str, definition: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simplified version that returns a dummy response.
    In a real implementation, this would create a Step Function.
    """
    print(f"Creating Step Function for pipeline: {pipeline_name}")
    return {
        "stateMachineArn": f"arn:aws:states:{os.environ.get('AWS_REGION', 'us-east-1')}:{ACCOUNT_ID}:stateMachine:{RESOURCE_PREFIX}-{pipeline_name}"
    }

def create_eventbridge_rule(pipeline_name: str, node: Any, state_machine_arn: str) -> Optional[str]:
    """
    Simplified version that returns a dummy ARN.
    In a real implementation, this would create an EventBridge rule.
    """
    print(f"Creating EventBridge rule for node: {node.id}")
    return f"arn:aws:events:{os.environ.get('AWS_REGION', 'us-east-1')}:{ACCOUNT_ID}:rule/{RESOURCE_PREFIX}-{pipeline_name}-{node.id}"

def delete_eventbridge_rule(rule_name: str) -> None:
    """
    Simplified version that just logs the deletion.
    In a real implementation, this would delete an EventBridge rule.
    """
    print(f"Deleting EventBridge rule: {rule_name}")

def store_pipeline_info(
    pipeline: Any,
    state_machine_arn: str,
    lambda_arns: Dict[str, str],
    eventbridge_rule_arns: Optional[Dict[str, str]] = None,
) -> None:
    """
    Simplified version that just logs the storage.
    In a real implementation, this would store pipeline info in DynamoDB.
    """
    print(f"Storing pipeline info for: {pipeline.name}")
    print(f"State machine ARN: {state_machine_arn}")
    print(f"Lambda ARNs: {lambda_arns}")
    print(f"EventBridge rule ARNs: {eventbridge_rule_arns}")

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for the pipeline worker.
    
    Args:
        event: Input from the Step Function
        context: Lambda context
        
    Returns:
        Result of the pipeline creation
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Parse the pipeline definition
        pipeline = PipelineDefinition(**event)
        pipeline_name = pipeline.name
        
        print(f"Processing pipeline: {pipeline_name} - {pipeline.description}")
        
        # Check if a pipeline with this name already exists
        existing_pipeline = get_pipeline_by_name(pipeline_name)
        if existing_pipeline:
            # Clean up existing EventBridge rules if updating a pipeline
            for resource_type, resource_arn in existing_pipeline.get("dependentResources", []):
                if resource_type == "eventbridge_rule":
                    rule_name = resource_arn.split("/")[-1]  # Extract rule name from ARN
                    try:
                        delete_eventbridge_rule(rule_name)
                        print(f"Deleted existing EventBridge rule: {rule_name}")
                    except Exception as e:
                        print(f"Failed to delete EventBridge rule {rule_name}: {e}")
            
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Pipeline name already exists",
                    "details": f"A pipeline with the name '{pipeline_name}' already exists. Please use a different name."
                })
            }
        
        # Create/update Lambda functions for each node
        lambda_arns = {}
        for node in pipeline.configuration.nodes:
            print(f"Processing node with id: {node.id}")
            lambda_arn = create_lambda_function(pipeline_name, node)
            
            # Create a more specific key for Lambda ARN mapping that includes the method
            lambda_key = node.data.id
            if node.data.type.lower() == "integration" and "method" in node.data.configuration:
                lambda_key = f"{node.data.id}_{node.data.configuration['method']}"
                # Add operationId to the key if available
                if "operationId" in node.data.configuration and node.data.configuration["operationId"]:
                    lambda_key = f"{lambda_key}_{node.data.configuration['operationId']}"
            
            lambda_arns[lambda_key] = lambda_arn
        
        # Log edge processing (if any)
        for edge in pipeline.configuration.edges:
            print(f"Processing edge: {edge.id} from {edge.source} to {edge.target}")
        
        settings = pipeline.configuration.settings
        print(f"Pipeline settings: AutoStart={settings.autoStart}, RetryAttempts={settings.retryAttempts}, Timeout={settings.timeout}")
        
        # Build and create/update the state machine
        state_machine_definition = build_step_function_definition(pipeline, lambda_arns)
        sfn_response = create_step_function(pipeline_name, state_machine_definition)
        state_machine_arn = sfn_response.get("stateMachineArn")
        print(f"State machine ARN: {state_machine_arn}")
        
        # Create EventBridge rules for trigger nodes
        eventbridge_rule_arns = {}
        for node in pipeline.configuration.nodes:
            if node.data.type.lower() == "trigger":
                try:
                    rule_arn = create_eventbridge_rule(pipeline_name, node, state_machine_arn)
                    if rule_arn:
                        eventbridge_rule_arns[node.data.id] = rule_arn
                        print(f"Added EventBridge rule {rule_arn} for node {node.data.id}")
                except Exception as e:
                    print(f"Failed to create EventBridge rule for node {node.data.id}: {e}")
        
        # Store/update pipeline info in DynamoDB
        store_pipeline_info(pipeline, state_machine_arn, lambda_arns, eventbridge_rule_arns)
        
        # Return success response
        response_body = {
            "message": "Pipeline created successfully",
            "pipeline_name": pipeline_name,
            "state_machine_arn": state_machine_arn,
        }
        
        return {
            "statusCode": 200,
            "body": json.dumps(response_body)
        }
        
    except Exception as e:
        print(f"Error creating pipeline: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Failed to create pipeline",
                "details": str(e)
            })
        }