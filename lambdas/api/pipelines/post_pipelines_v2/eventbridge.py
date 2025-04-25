import json
import time
import re
import shortuuid
from typing import Dict, Any, Optional

import boto3
from aws_lambda_powertools import Logger

from config import INGEST_EVENT_BUS_NAME, NODE_TEMPLATES_BUCKET, IAC_ASSETS_BUCKET, resource_prefix
from iam_operations import get_events_role_arn
from lambda_operations import read_yaml_from_s3, get_zip_file_key

# Initialize logger
logger = Logger()


def get_event_pattern_for_rule(
    rule_name: str, node: Any, pipeline_name: str
) -> Dict[str, Any]:
    """
    Get the event pattern for a specific rule type.

    Args:
        rule_name: Name of the rule
        node: Node object containing configuration
        pipeline_name: Name of the pipeline

    Returns:
        Event pattern dictionary for the rule
    """
    # Base pattern
    pattern = {"source": ["custom.asset.processor"]}

    # Add specific pattern based on rule name
    if rule_name == "ingest_completed":
        pattern.update(
            {
                "detail-type": ["AssetCreated"],
                "detail": {"DigitalSourceAsset": {"MainRepresentation": {}}},
            }
        )
    elif rule_name == "video_ingested":
        pattern.update(
            {
                "detail-type": ["AssetCreated"],
                "detail": {"DigitalSourceAsset": {"Type": ["Video"]}},
            }
        )
    elif rule_name == "video_processing_completed":
        pattern.update(
            {
                "detail-type": ["ProcessingCompleted"],
                "detail": {"DigitalSourceAsset": {"Type": ["Video"]}},
            }
        )
    elif rule_name == "pipeline_execution_completed":
        # Determine asset type and format based on node configuration
        asset_type = "Video"  # Default asset type
        asset_format = None # Default format
        
        # Get parameters from node configuration
        parameters = node.data.configuration.get("parameters", {})
        logger.info(f"Node parameters: {parameters}")
        
        # Check for different asset type parameters in configuration
        if "Image Type" in parameters:
            asset_type = "Image"
            asset_format = parameters.get("Image Type")
            logger.info(f"Using Image asset type with format: {asset_format}")
        elif "Video Type" in parameters:
            asset_type = "Video"
            asset_format = parameters.get("Video Type")
            logger.info(f"Using Video asset type with format: {asset_format}")
        elif "Audio Type" in parameters:
            asset_type = "Audio"
            asset_format = parameters.get("Audio Type")
            logger.info(f"Using Audio asset type with format: {asset_format}")
        else:
            logger.warning(f"No specific asset type found in parameters, defaulting to Video/MP4")
            
        # Check if a prefix is specified
        asset_prefix = parameters.get("Prefix")
        if asset_prefix:
            logger.info(f"Using prefix path: {asset_prefix}")
        
        # Create the base pattern with appropriate asset type and format
        digital_source_asset = {
            "Type": [asset_type],
        }
        
        # Only include MainRepresentation if asset_format is not empty
        if asset_format and asset_format.strip():
            # Handle comma-delimited formats
            if "," in asset_format:
                # Split by comma, trim whitespace, convert to uppercase, and filter out empty items
                format_array = [fmt.strip().upper() for fmt in asset_format.split(",") if fmt.strip()]
                if format_array:  # Only add if there are non-empty items
                    digital_source_asset["MainRepresentation"] = {"Format": format_array}
            else:
                digital_source_asset["MainRepresentation"] = {"Format": [asset_format.upper()]}
        
        # Add StorageInfo path if prefix is specified and not empty
        if asset_prefix and asset_prefix.strip():
            # Create MainRepresentation if it doesn't exist yet
            if "MainRepresentation" not in digital_source_asset:
                digital_source_asset["MainRepresentation"] = {}
            
            # Initialize nested structure if it doesn't exist
            if "StorageInfo" not in digital_source_asset["MainRepresentation"]:
                digital_source_asset["MainRepresentation"]["StorageInfo"] = {}
            
            if "PrimaryLocation" not in digital_source_asset["MainRepresentation"]["StorageInfo"]:
                digital_source_asset["MainRepresentation"]["StorageInfo"]["PrimaryLocation"] = {}
            
            digital_source_asset["MainRepresentation"]["StorageInfo"]["PrimaryLocation"]["ObjectKey"] = {"Path": [asset_prefix]}
            logger.info(f"Added StorageInfo path: {asset_prefix}")
        
        logger.info(f"Created digital source asset pattern: {digital_source_asset}")
        
        # Override the source for pipeline execution completed events
        pattern = {
            "source": ["medialake.pipeline"],
            "detail-type": ["Pipeline Execution Completed"],
            "detail": {
                "outputs": {"input": {"DigitalSourceAsset": digital_source_asset}},
            },
        }
        
        # Skip the rest of the function to avoid adding parameters at the top level
        return pattern
    elif rule_name == "workflow_completed":
        # Get pipeline name from node configuration if available
        target_pipeline = node.data.configuration.get("pipeline_name", "")
        pattern.update({"detail-type": ["WorkflowCompleted"]})

        # Add pipeline name filter if specified and not empty
        if target_pipeline and target_pipeline.strip():
            # Handle comma-delimited pipeline names
            if "," in target_pipeline:
                # Split by comma, trim whitespace, and filter out empty items
                pipeline_array = [name.strip() for name in target_pipeline.split(",") if name.strip()]
                if pipeline_array:  # Only add if there are non-empty items
                    pattern["detail"] = {"pipeline_name": pipeline_array}
            else:
                pattern["detail"] = {"pipeline_name": [target_pipeline]}

    # Add any additional filters from node configuration
    for param in node.data.configuration:
        # Skip pipeline_name, method, and Video Type parameters
        # Video Type is handled separately for pipeline_execution_completed
        if (
            param not in ["pipeline_name", "method", "Video Type"]
            and node.data.configuration[param]
        ):
            if "detail" not in pattern:
                pattern["detail"] = {}

            # Handle parameters differently - they need to be properly formatted for EventBridge
            if param == "parameters":
                # If parameters is a dictionary or list, process it properly
                if isinstance(node.data.configuration[param], dict):
                    # For dictionaries, add each key-value pair directly to detail
                    for key, value in node.data.configuration[param].items():
                        # Skip empty parameters or empty strings
                        if value is not None and value != "":
                            # Handle comma-delimited values
                            if isinstance(value, str) and "," in value:
                                # Split by comma, trim whitespace, and filter out empty items
                                if key == "Format":
                                    # Convert Format values to uppercase
                                    value_array = [item.strip().upper() for item in value.split(",") if item.strip()]
                                    # For ingest_completed rule, place Format in the correct nested structure
                                    if rule_name == "ingest_completed" and value_array:
                                        if "DigitalSourceAsset" not in pattern["detail"]:
                                            pattern["detail"]["DigitalSourceAsset"] = {}
                                        if "MainRepresentation" not in pattern["detail"]["DigitalSourceAsset"]:
                                            pattern["detail"]["DigitalSourceAsset"]["MainRepresentation"] = {}
                                        pattern["detail"]["DigitalSourceAsset"]["MainRepresentation"]["Format"] = value_array
                                    elif value_array:  # Only add if there are non-empty items
                                        pattern["detail"][key] = value_array
                                else:
                                    value_array = [item.strip() for item in value.split(",") if item.strip()]
                                    if value_array:  # Only add if there are non-empty items
                                        pattern["detail"][key] = value_array
                            else:
                                # Convert Format values to uppercase
                                if key == "Format" and isinstance(value, str):
                                    # For ingest_completed rule, place Format in the correct nested structure
                                    if rule_name == "ingest_completed":
                                        if "DigitalSourceAsset" not in pattern["detail"]:
                                            pattern["detail"]["DigitalSourceAsset"] = {}
                                        if "MainRepresentation" not in pattern["detail"]["DigitalSourceAsset"]:
                                            pattern["detail"]["DigitalSourceAsset"]["MainRepresentation"] = {}
                                        pattern["detail"]["DigitalSourceAsset"]["MainRepresentation"]["Format"] = [value.upper()]
                                    else:
                                        pattern["detail"][key] = [value.upper()]
                                else:
                                    pattern["detail"][key] = [value]
                elif isinstance(node.data.configuration[param], list):
                    # For lists of dictionaries, extract and flatten
                    for item in node.data.configuration[param]:
                        if isinstance(item, dict):
                            for key, value in item.items():
                                # Skip empty parameters or empty strings
                                if value is not None and value != "":
                                    # Handle comma-delimited values
                                    if isinstance(value, str) and "," in value:
                                        # Split by comma, trim whitespace, and filter out empty items
                                        if key == "Format":
                                            # Convert Format values to uppercase
                                            value_array = [item.strip().upper() for item in value.split(",") if item.strip()]
                                            # For ingest_completed rule, place Format in the correct nested structure
                                            if rule_name == "ingest_completed" and value_array:
                                                if "DigitalSourceAsset" not in pattern["detail"]:
                                                    pattern["detail"]["DigitalSourceAsset"] = {}
                                                if "MainRepresentation" not in pattern["detail"]["DigitalSourceAsset"]:
                                                    pattern["detail"]["DigitalSourceAsset"]["MainRepresentation"] = {}
                                                pattern["detail"]["DigitalSourceAsset"]["MainRepresentation"]["Format"] = value_array
                                            elif value_array:  # Only add if there are non-empty items
                                                pattern["detail"][key] = value_array
                                        else:
                                            value_array = [item.strip() for item in value.split(",") if item.strip()]
                                            if value_array:  # Only add if there are non-empty items
                                                pattern["detail"][key] = value_array
                                    else:
                                        # Convert Format values to uppercase
                                        if key == "Format" and isinstance(value, str):
                                            # For ingest_completed rule, place Format in the correct nested structure
                                            if rule_name == "ingest_completed":
                                                if "DigitalSourceAsset" not in pattern["detail"]:
                                                    pattern["detail"]["DigitalSourceAsset"] = {}
                                                if "MainRepresentation" not in pattern["detail"]["DigitalSourceAsset"]:
                                                    pattern["detail"]["DigitalSourceAsset"]["MainRepresentation"] = {}
                                                pattern["detail"]["DigitalSourceAsset"]["MainRepresentation"]["Format"] = [value.upper()]
                                            else:
                                                pattern["detail"][key] = [value.upper()]
                                        else:
                                            pattern["detail"][key] = [value]
                else:
                    # For simple values, add as is if not empty
                    if node.data.configuration[param] is not None and node.data.configuration[param] != "":
                        # Handle comma-delimited values
                        value = node.data.configuration[param]
                        if isinstance(value, str) and "," in value:
                            # Split by comma, trim whitespace, and filter out empty items
                            if param == "Format":
                                # Convert Format values to uppercase
                                value_array = [item.strip().upper() for item in value.split(",") if item.strip()]
                                # For ingest_completed rule, place Format in the correct nested structure
                                if rule_name == "ingest_completed" and value_array:
                                    if "DigitalSourceAsset" not in pattern["detail"]:
                                        pattern["detail"]["DigitalSourceAsset"] = {}
                                    if "MainRepresentation" not in pattern["detail"]["DigitalSourceAsset"]:
                                        pattern["detail"]["DigitalSourceAsset"]["MainRepresentation"] = {}
                                    pattern["detail"]["DigitalSourceAsset"]["MainRepresentation"]["Format"] = value_array
                                elif value_array:  # Only add if there are non-empty items
                                    pattern["detail"][param] = value_array
                            else:
                                value_array = [item.strip() for item in value.split(",") if item.strip()]
                                if value_array:  # Only add if there are non-empty items
                                    pattern["detail"][param] = value_array
                        else:
                            # Convert Format values to uppercase
                            if param == "Format" and isinstance(value, str):
                                # For ingest_completed rule, place Format in the correct nested structure
                                if rule_name == "ingest_completed":
                                    if "DigitalSourceAsset" not in pattern["detail"]:
                                        pattern["detail"]["DigitalSourceAsset"] = {}
                                    if "MainRepresentation" not in pattern["detail"]["DigitalSourceAsset"]:
                                        pattern["detail"]["DigitalSourceAsset"]["MainRepresentation"] = {}
                                    pattern["detail"]["DigitalSourceAsset"]["MainRepresentation"]["Format"] = [value.upper()]
                                else:
                                    pattern["detail"][param] = [value.upper()]
                            else:
                                pattern["detail"][param] = [value]
            else:
                # For all other parameters, add as is if not empty
                if node.data.configuration[param] is not None and node.data.configuration[param] != "":
                    # Handle comma-delimited values
                    value = node.data.configuration[param]
                    if isinstance(value, str) and "," in value:
                        # Split by comma, trim whitespace, and filter out empty items
                        if param == "Format":
                            # Convert Format values to uppercase
                            value_array = [item.strip().upper() for item in value.split(",") if item.strip()]
                            # For ingest_completed rule, place Format in the correct nested structure
                            if rule_name == "ingest_completed" and value_array:
                                if "DigitalSourceAsset" not in pattern["detail"]:
                                    pattern["detail"]["DigitalSourceAsset"] = {}
                                if "MainRepresentation" not in pattern["detail"]["DigitalSourceAsset"]:
                                    pattern["detail"]["DigitalSourceAsset"]["MainRepresentation"] = {}
                                pattern["detail"]["DigitalSourceAsset"]["MainRepresentation"]["Format"] = value_array
                            elif value_array:  # Only add if there are non-empty items
                                pattern["detail"][param] = value_array
                        else:
                            value_array = [item.strip() for item in value.split(",") if item.strip()]
                            if value_array:  # Only add if there are non-empty items
                                pattern["detail"][param] = value_array
                    else:
                        # Convert Format values to uppercase
                        if param == "Format" and isinstance(value, str):
                            # For ingest_completed rule, place Format in the correct nested structure
                            if rule_name == "ingest_completed":
                                if "DigitalSourceAsset" not in pattern["detail"]:
                                    pattern["detail"]["DigitalSourceAsset"] = {}
                                if "MainRepresentation" not in pattern["detail"]["DigitalSourceAsset"]:
                                    pattern["detail"]["DigitalSourceAsset"]["MainRepresentation"] = {}
                                pattern["detail"]["DigitalSourceAsset"]["MainRepresentation"]["Format"] = [value.upper()]
                            else:
                                pattern["detail"][param] = [value.upper()]
                        else:
                            pattern["detail"][param] = [value]

    return pattern


def create_eventbridge_rule(
    pipeline_name: str, node: Any, state_machine_arn: str, active: bool = True, execution_uuid: str = None
) -> Optional[Dict[str, Any]]:
    """
    Create an EventBridge rule for a trigger node.

    Args:
        pipeline_name: Name of the pipeline
        node: Node object containing configuration
        state_machine_arn: ARN of the state machine to target
        active: Whether the rule should be enabled (True) or disabled (False)
        execution_uuid: UUID to use for consistent naming across resources

    Returns:
        Dictionary containing:
        - rule_arn: ARN of the created EventBridge rule
        - role_arn: ARN of the IAM role created for EventBridge
        - trigger_lambda_arn: ARN of the Lambda function created for the trigger
        - queue_arn: ARN of the SQS queue created
        - event_source_mapping_uuid: UUID of the event source mapping
        Or None if creation was skipped
    """
    logger.info(f"Creating EventBridge rule for trigger node: {node.id}")

    try:
        # Read YAML file from S3
        yaml_file_path = f"node_templates/{node.data.type.lower()}/{node.data.id}.yaml"
        yaml_data = read_yaml_from_s3(NODE_TEMPLATES_BUCKET, yaml_file_path)

        # Get EventBridge rule configuration
        # Note: Some YAML files use aws_event_bridge and others use aws_eventbridge
        rule_config = yaml_data["node"]["integration"]["config"].get(
            "aws_eventbridge",
            yaml_data["node"]["integration"]["config"].get("aws_event_bridge", {}),
        )

        if not rule_config:
            logger.warning(
                f"No EventBridge rule configuration found for node {node.id}"
            )
            return None

        rule_name = rule_config.get("aws_eventbridge_rule")
        if not rule_name:
            logger.warning(f"No rule name specified for node {node.id}")
            return None

        # Create a unique rule name for this pipeline and node
        # Sanitize the pipeline name to replace spaces with hyphens and remove any other invalid characters
        sanitized_pipeline_name = pipeline_name.replace(" ", "-")
        # Replace any characters that aren't alphanumeric, periods, hyphens, or underscores
        sanitized_pipeline_name = "".join(
            c for c in sanitized_pipeline_name if c.isalnum() or c in ".-_"
        )

        unique_rule_name = f"{sanitized_pipeline_name}-{rule_name}-{node.data.id}"[
            :64
        ]  # Ensure name is not too long

        # Get event pattern based on rule name and node configuration
        event_pattern = get_event_pattern_for_rule(rule_name, node, pipeline_name)

        # Create the EventBridge rule
        events_client = boto3.client("events")

        # Get the event bus name from environment variable
        event_bus_name = INGEST_EVENT_BUS_NAME

        # Create the rule
        rule_response = events_client.put_rule(
            Name=unique_rule_name,
            EventPattern=json.dumps(event_pattern),
            State="ENABLED" if active else "DISABLED",
            EventBusName=event_bus_name,
            Description=f"Rule for pipeline {pipeline_name}, node {node.data.label}",
        )
        
        # Store the rule ARN for later return
        rule_arn = rule_response.get("RuleArn")
        logger.info(f"Created EventBridge rule with ARN: {rule_arn}")

        # Create or get IAM role for EventBridge to invoke Lambda
        role_arn = get_events_role_arn(sanitized_pipeline_name)
        
        # Create a unique trigger lambda name for this pipeline
        
        parts = re.split(r'[^A-Za-z0-9]+', pipeline_name)

        # Take the first character of each non-empty part, uppercase it, join
        abvr=  ''.join(p[0].upper() for p in parts if p)
        uuid = execution_uuid if execution_uuid else shortuuid.uuid()
        trigger_lambda_name = f"{resource_prefix}_{abvr}_{uuid}_trigger".lower()


        # Create the trigger lambda function
        lambda_client = boto3.client("lambda")
        
        # Check if the trigger lambda already exists
        try:
            # Try to get the function
            response = lambda_client.get_function(FunctionName=trigger_lambda_name)
            trigger_lambda_arn = response["Configuration"]["FunctionArn"]
            logger.info(f"Trigger lambda {trigger_lambda_name} already exists")
        except lambda_client.exceptions.ResourceNotFoundException:
            # Create the trigger lambda
            logger.info(f"Creating trigger lambda {trigger_lambda_name}")
            
            # Get the zip file key for the pipeline_trigger Lambda
            zip_file_prefix = "lambda-code/nodes/utility/PipelineTriggerLambdaDeployment"
            try:
                zip_file_key = get_zip_file_key(IAC_ASSETS_BUCKET, zip_file_prefix)
                logger.info(f"Found zip file for pipeline_trigger: {zip_file_key}")
            except Exception as e:
                logger.error(f"Failed to find zip file for pipeline_trigger: {e}")
                return None
            
            # Create a role for the trigger lambda
            iam_client = boto3.client("iam")
            role_name = f"{resource_prefix}_{sanitized_pipeline_name}_trigger_role"
            
            # Check if role already exists
            try:
                existing_role = iam_client.get_role(RoleName=role_name)
                logger.info(f"Found existing role {role_name}, deleting it")
                
                # Import delete_role and wait_for_role_deletion from iam_operations
                from iam_operations import delete_role, wait_for_role_deletion
                
                # Delete the existing role
                delete_role(role_name)
                
                # Wait for role deletion to complete
                wait_for_role_deletion(role_name)
                logger.info(f"Successfully deleted existing role {role_name}")
            except iam_client.exceptions.NoSuchEntityException:
                logger.info(f"Role {role_name} does not exist, will create new role")
            except Exception as e:
                logger.error(f"Error checking/deleting existing role {role_name}: {e}")
                return None
            
            # Create the role
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
            
            try:
                response = iam_client.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy)
                )
                role_arn = response["Role"]["Arn"]
                logger.info(f"Successfully created role {role_name}")
                
                # Attach policies
                iam_client.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                )
                
                # Add policy to allow invoking Step Functions and receiving SQS messages
                policy_document = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "states:StartExecution",
                                "states:ListExecutions"
                            ],
                            "Resource": [state_machine_arn]
                        },
                        {
                            "Effect": "Allow",
                            "Action": [
                                "sqs:ReceiveMessage",
                                "sqs:DeleteMessage",
                                "sqs:GetQueueAttributes",
                                "sqs:ChangeMessageVisibility"
                            ],
                            "Resource": "*"  # Will be restricted to the specific queue once it's created
                        }
                    ]
                }
                
                iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName=f"{role_name}_policy",
                    PolicyDocument=json.dumps(policy_document)
                )
                
                # Wait for role to propagate
                time.sleep(10)
                
                # Create the Lambda function
                response = lambda_client.create_function(
                    FunctionName=trigger_lambda_name,
                    Runtime="python3.12",
                    Role=role_arn,
                    Handler="index.lambda_handler",
                    Code={"S3Bucket": IAC_ASSETS_BUCKET, "S3Key": zip_file_key},
                    Timeout=300,
                    MemorySize=1024,
                    Environment={
                        "Variables": {
                            "MAX_CONCURRENT_EXECUTIONS": "1000",
                            "PIPELINE_NAME": pipeline_name,
                            "SERVICE": "Trigger",  # node Title
                            "STEP_NAME": "Pipeline Trigger"  # friendly name of the node
                        }
                    }
                )
                
                trigger_lambda_arn = response["FunctionArn"]
                logger.info(f"Created trigger lambda with ARN: {trigger_lambda_arn}")
                
            except Exception as e:
                logger.error(f"Failed to create trigger lambda: {e}")
                return None
        
        # Create an SQS queue for the pipeline
        sqs_client = boto3.client('sqs')
        queue_name = f"{resource_prefix}_{sanitized_pipeline_name}_trigger_queue"
        queue_url = None
        queue_arn = None
        max_retries = 3
        retry_delay = 60  # AWS requires 60 seconds after deleting a queue before creating one with the same name
        
        # Check if the queue already exists and delete it
        try:
            # List queues with the name prefix to find if it exists
            response = sqs_client.list_queues(QueueNamePrefix=queue_name)
            if 'QueueUrls' in response and response['QueueUrls']:
                queue_url = response['QueueUrls'][0]
                logger.info(f"Found existing SQS queue: {queue_url}")
                
                # Get the queue ARN
                queue_attrs = sqs_client.get_queue_attributes(
                    QueueUrl=queue_url,
                    AttributeNames=['QueueArn']
                )
                queue_arn = queue_attrs['Attributes']['QueueArn']
                
                # Find and delete any event source mappings to Lambda functions
                try:
                    # List event source mappings for this queue
                    mapping_response = lambda_client.list_event_source_mappings(
                        EventSourceArn=queue_arn
                    )
                    
                    # Delete each event source mapping
                    for mapping in mapping_response.get('EventSourceMappings', []):
                        mapping_uuid = mapping['UUID']
                        lambda_client.delete_event_source_mapping(UUID=mapping_uuid)
                        logger.info(f"Deleted event source mapping {mapping_uuid} for queue {queue_arn}")
                except Exception as mapping_error:
                    logger.warning(f"Error deleting event source mappings for queue {queue_arn}: {mapping_error}")
                
                # Delete the queue
                sqs_client.delete_queue(QueueUrl=queue_url)
                logger.info(f"Deleted existing SQS queue: {queue_url}")
                
                # AWS requires waiting 60 seconds after deleting a queue before creating one with the same name
                logger.info(f"Waiting {retry_delay} seconds for queue deletion to propagate (AWS requirement)...")
                time.sleep(retry_delay)
            
            # Create a new SQS queue with retry logic
            for attempt in range(max_retries):
                try:
                    logger.info(f"Creating new SQS queue: {queue_name} (attempt {attempt+1}/{max_retries})")
                    response = sqs_client.create_queue(
                        QueueName=queue_name,
                        Attributes={
                            'VisibilityTimeout': '300',  # 5 minutes
                            'MessageRetentionPeriod': '86400'  # 1 day
                        }
                    )
                    queue_url = response['QueueUrl']
                    
                    # Get the queue ARN
                    queue_attrs = sqs_client.get_queue_attributes(
                        QueueUrl=queue_url,
                        AttributeNames=['QueueArn']
                    )
                    queue_arn = queue_attrs['Attributes']['QueueArn']
                    logger.info(f"Created new SQS queue with ARN: {queue_arn}")
                    break  # Success, exit the retry loop
                    
                except sqs_client.exceptions.QueueDeletedRecently as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Queue {queue_name} was recently deleted. Waiting {retry_delay} seconds before retry...")
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"Failed to create queue after {max_retries} attempts: {e}")
                        raise
                except Exception as e:
                    logger.error(f"Error creating SQS queue: {e}")
                    raise
            
            # Check if an event source mapping already exists for this Lambda function and queue
            existing_mappings = lambda_client.list_event_source_mappings(
                FunctionName=trigger_lambda_name,
                EventSourceArn=queue_arn
            )
            
            if existing_mappings.get("EventSourceMappings"):
                logger.info(f"Event source mapping already exists for Lambda {trigger_lambda_name} and queue {queue_arn}")
                # Use the existing mapping
                event_source_mapping_uuid = existing_mappings["EventSourceMappings"][0]["UUID"]
                logger.info(f"Using existing event source mapping: {event_source_mapping_uuid}")
            else:
                # Set up Lambda trigger from SQS queue
                response = lambda_client.create_event_source_mapping(
                    EventSourceArn=queue_arn,
                    FunctionName=trigger_lambda_name,
                    Enabled=True,
                    BatchSize=1
                )
                event_source_mapping_uuid = response.get("UUID")
                logger.info(f"Created new event source mapping {event_source_mapping_uuid} from SQS queue to Lambda function")
        except Exception as e:
            logger.error(f"Error creating/finding SQS queue: {e}")
            return None
        
        # Create a policy to allow EventBridge to send messages to the SQS queue
        sqs_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "events.amazonaws.com"},
                    "Action": "sqs:SendMessage",
                    "Resource": queue_arn,
                    "Condition": {
                        "ArnEquals": {"aws:SourceArn": rule_arn}
                    }
                }
            ]
        }
        
        # Set the policy on the SQS queue
        try:
            sqs_client.set_queue_attributes(
                QueueUrl=queue_url,
                Attributes={
                    'Policy': json.dumps(sqs_policy)
                }
            )
            logger.info(f"Set policy on SQS queue to allow EventBridge to send messages")
        except Exception as e:
            logger.error(f"Error setting policy on SQS queue: {e}")
            return None
        
        # Set the SQS queue as the target for the EventBridge rule
        events_client.put_targets(
            Rule=unique_rule_name,
            EventBusName=event_bus_name,
            Targets=[
                {
                    "Id": f"{sanitized_pipeline_name}-target",
                    "Arn": queue_arn,
                    # Add input transformer to include metadata about the trigger and the Step Function ARN
                    "InputTransformer": {
                        "InputPathsMap": {
                            "detail": "$.detail",
                            "source": "$.source",
                            "detailType": "$.detail-type",
                            "time": "$.time",
                        },
                        "InputTemplate": json.dumps(
                            {
                                "Asset": {
                                    "detail": "<detail>",
                                    "source": "<source>",
                                    "detailType": "<detailType>",
                                    "time": "<time>",
                                    "triggerNode": node.data.id,
                                    "pipelineName": pipeline_name,
                                    "pipelineExecutionId.$":"$$.Execution.Id",
                                    "pipelineExecutionStart.$":"$$.Execution.StartTime",
                                    "pipelineId": state_machine_arn,
                                    
                                },
                                "StateMachineArn": state_machine_arn
                            }
                        )
                        .replace('"<detail>"', "<detail>")
                        .replace('"<source>"', "<source>")
                        .replace('"<detailType>"', "<detailType>")
                        .replace('"<time>"', "<time>"),
                    },
                }
            ],
        )

        # We already have the event source mapping UUID from earlier
        if not event_source_mapping_uuid:
            logger.warning(f"No event source mapping UUID found for Lambda {trigger_lambda_name} and queue {queue_arn}")

        logger.info(f"Created EventBridge rule {unique_rule_name} for node {node.id}")
        return {
            "rule_arn": rule_arn,
            "role_arn": role_arn,
            "trigger_lambda_arn": trigger_lambda_arn,
            "queue_arn": queue_arn,
            "event_source_mapping_uuid": event_source_mapping_uuid
        }

    except Exception as e:
        logger.exception(f"Failed to create EventBridge rule for node {node.id}: {e}")
        return None


def update_eventbridge_rule_state(rule_name: str, enabled: bool) -> None:
    """
    Enable or disable an EventBridge rule.
    
    Args:
        rule_name: Name of the rule
        enabled: True to enable, False to disable
    """
    events_client = boto3.client("events")
    event_bus_name = INGEST_EVENT_BUS_NAME
    
    try:
        if enabled:
            events_client.enable_rule(
                Name=rule_name,
                EventBusName=event_bus_name
            )
            logger.info(f"Enabled EventBridge rule: {rule_name}")
        else:
            events_client.disable_rule(
                Name=rule_name,
                EventBusName=event_bus_name
            )
            logger.info(f"Disabled EventBridge rule: {rule_name}")
    except Exception as e:
        logger.error(f"Error updating EventBridge rule state for {rule_name}: {e}")


def delete_eventbridge_rule(rule_name: str) -> None:
    """
    Delete an EventBridge rule, its targets, and associated resources (SQS queue, event source mapping).

    Args:
        rule_name: Name of the rule
    """
    events_client = boto3.client("events")
    sqs_client = boto3.client("sqs")
    lambda_client = boto3.client("lambda")
    event_bus_name = INGEST_EVENT_BUS_NAME

    try:
        # Extract the pipeline name from the rule name (it's usually the first part)
        parts = rule_name.split('-')
        if len(parts) > 0:
            # Use just the first part (pipeline name) for the target ID and queue name
            pipeline_part = parts[0]
            target_id = f"{pipeline_part}-target"
            queue_name = f"{resource_prefix}_{pipeline_part}_trigger_queue"
        else:
            # Fallback to a simple target ID if we can't extract the pipeline name
            target_id = "rule-target"
            queue_name = f"{resource_prefix}_trigger_queue"
            
        logger.info(f"Removing target with ID: {target_id} from rule: {rule_name}")
        
        # Find and delete the SQS queue
        try:
            # Find the queue URL
            response = sqs_client.list_queues(QueueNamePrefix=queue_name)
            if 'QueueUrls' in response and response['QueueUrls']:
                queue_url = response['QueueUrls'][0]
                
                # Get the queue ARN
                queue_attrs = sqs_client.get_queue_attributes(
                    QueueUrl=queue_url,
                    AttributeNames=['QueueArn']
                )
                queue_arn = queue_attrs['Attributes']['QueueArn']
                
                # Find and delete any event source mappings to Lambda functions
                try:
                    # List event source mappings for this queue
                    response = lambda_client.list_event_source_mappings(
                        EventSourceArn=queue_arn
                    )
                    
                    # Delete each event source mapping
                    for mapping in response.get('EventSourceMappings', []):
                        mapping_uuid = mapping['UUID']
                        lambda_client.delete_event_source_mapping(UUID=mapping_uuid)
                        logger.info(f"Deleted event source mapping {mapping_uuid} for queue {queue_arn}")
                except Exception as mapping_error:
                    logger.warning(f"Error deleting event source mappings for queue {queue_arn}: {mapping_error}")
                
                # Delete the queue
                sqs_client.delete_queue(QueueUrl=queue_url)
                logger.info(f"Deleted SQS queue: {queue_url}")
            else:
                logger.info(f"No SQS queue found with name prefix: {queue_name}")
        except Exception as queue_error:
            logger.warning(f"Error deleting SQS queue: {queue_error}")
        
        # Remove targets from the rule
        try:
            events_client.remove_targets(
                Rule=rule_name, EventBusName=event_bus_name, Ids=[target_id]
            )
        except events_client.exceptions.ResourceNotFoundException:
            logger.info(f"No targets found for rule {rule_name}, proceeding with deletion")
        except Exception as target_error:
            logger.warning(f"Error removing targets for rule {rule_name}: {target_error}")
            # Try with a simpler target ID as a fallback
            try:
                events_client.remove_targets(
                    Rule=rule_name, EventBusName=event_bus_name, Ids=["target"]
                )
            except Exception as simple_target_error:
                logger.warning(f"Error removing simple target for rule {rule_name}: {simple_target_error}")

        # Delete the rule
        events_client.delete_rule(Name=rule_name, EventBusName=event_bus_name)
        logger.info(f"Deleted EventBridge rule: {rule_name}")
    except Exception as e:
        logger.error(f"Error deleting EventBridge rule {rule_name}: {e}")
