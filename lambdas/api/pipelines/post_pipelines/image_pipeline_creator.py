import os
import uuid
import json
import time
from datetime import datetime
from boto3.dynamodb.conditions import Key
import boto3
from decimal import Decimal

# Import necessary functions and modules
from image_pipeline_definitions import get_state_machine_definition
from utils import check_resource_exists, create_sqs_fifo_queue, create_eventbridge_rule, create_pipeline_role, create_state_machine, float_to_decimal

# Initialize AWS clients
lambda_client = boto3.client('lambda')
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

def create_pipeline(createpipeline):
    # Generate names for resources
    queue_name = f"medialake-pipeline-{createpipeline.name}"
    rule_name = f"medialake-pipeline-{createpipeline.name}-rule"
    role_name = f"medialake-pipeline-{createpipeline.name}-role"
    state_machine_name = f"medialake-pipeline-{createpipeline.name}"
    image_proxy_lambda_name = f"medialake-pipeline-{createpipeline.name}-image-proxy"
    pipeline_trigger_lambda_name = f"medialake-pipeline-{createpipeline.name}-executor"

    # Check if resources exist
    resources_exist, error_message = check_resource_exists(
        createpipeline.name,
        queue_name,
        rule_name,
        role_name,
        state_machine_name,
        [
            image_proxy_lambda_name,
            pipeline_trigger_lambda_name,
            f"medialake-pipeline-{createpipeline.name}-metadata"
        ]
    )

    if resources_exist:
        return {
            "status": "409",
            "message": "Resource conflict",
            "data": {
                "error": error_message
            }
        }
        
    # Generate unique ID and timestamps
    pipeline_id = str(uuid.uuid4())
    current_time = datetime.utcnow().isoformat(timespec='seconds')
    deployment_bucket = os.environ.get('IAC_ASSETS_BUCKET')
    pipeline_trigger_deployment_zip = os.environ.get('PIPELINE_TRIGGER_LAMBDA')
    image_metadata_extractor_deployment_zip = os.environ.get('IMAGE_METADATA_EXTRACTOR_LAMBDA')
    image_proxy_deployment_zip = os.environ.get('IMAGE_PROXY_LAMBDA')
    ingest_event_bus_name = os.environ.get('INGEST_EVENT_BUS')
    exiftool_layer_arn = os.environ.get('EXIFTOOL_LAYER_ARN')
    exempitool_layer_arn = os.environ.get('EXEMPITOOL_LAYER_ARN')
    powertools_layer_arn = os.environ.get('POWERTOOLS__LAYER_ARN')
    
    # Common tags for all resources
    tags = {
        'medialake': 'true',
        'pipeline_id': pipeline_id,
        'pipeline_name': createpipeline.name
    }
    
    # Create SQS FIFO Queue
    queue_url, queue_arn = create_sqs_fifo_queue(queue_name, tags)
    
    # Create EventBridge rule
    rule_arn = create_eventbridge_rule(
        rule_name,
        ingest_event_bus_name,
        queue_arn,
        tags
    )
    
    # Create IAM Role for Lambda and Step Functions
    role_arn = create_pipeline_role(
        role_name,
        queue_arn,
        state_machine_name,
        tags
    )
    
    # Wait for IAM role propagation
    time.sleep(10)
    
    # Create metadata extractor lambda
    image_metadata_extractor_lambda_function_name = f"medialake-pipeline-{createpipeline.name}-metadata"
    image_metadata_extractor_lambda_response = create_metadata_extractor_lambda(
        lambda_client,
        image_metadata_extractor_lambda_function_name,
        role_arn,
        deployment_bucket,
        image_metadata_extractor_deployment_zip,
        exiftool_layer_arn,
        exempitool_layer_arn,
        {"MEDIALAKE_ASSET_TABLE": os.environ.get('MEDIALAKE_ASSET_TABLE')},
        tags
    )

    # Create image proxy lambda
    image_proxy_lambda_function_name = f"medialake-pipeline-{createpipeline.name}-image-proxy"
    image_proxy_lambda_response = create_image_proxy_lambda(
        lambda_client,
        image_proxy_lambda_function_name,
        role_arn,
        deployment_bucket,
        image_proxy_deployment_zip,
        {"MEDIALAKE_ASSET_TABLE": os.environ.get('MEDIALAKE_ASSET_TABLE')},
        tags
    )
    
    # Update S3 bucket policy
    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowLambdaWriteAccess",
                "Effect": "Allow",
                "Principal": {
                    "Service": "lambda.amazonaws.com"
                },
                "Action": [
                    "s3:PutObject",
                    "s3:PutObjectAcl"
                ],
                "Resource": [
                    f"arn:aws:s3:::{os.environ.get('MEDIA_ASSETS_BUCKET_NAME')}/*",
                    f"arn:aws:s3:::{os.environ.get('MEDIA_ASSETS_BUCKET_NAME')}"
                ],
                "Condition": {
                    "ArnLike": {
                        "aws:SourceArn": image_proxy_lambda_response['FunctionArn']
                    }
                }
            }
        ]
    }
    s3_client.put_bucket_policy(
        Bucket=os.environ.get('MEDIA_ASSETS_BUCKET_NAME'),
        Policy=json.dumps(bucket_policy)
    )
    
    # Create Step Function
    state_machine_name = f"medialake-pipeline-{createpipeline.name}"
    state_machine_definition = get_state_machine_definition(
        image_metadata_extractor_lambda_response['FunctionArn'],
        image_proxy_lambda_response['FunctionArn'],
        createpipeline.name,
        os.environ.get('MEDIALAKE_ASSET_TABLE'),
        os.environ.get('MEDIA_ASSETS_BUCKET_NAME')
    )
    state_machine_arn = create_state_machine(
        state_machine_name,
        role_arn,
        state_machine_definition,
        tags
    )
    
    # Create Pipeline Trigger Lambda Function
    pipeline_trigger_lambda_function_name = f"medialake-pipeline-{createpipeline.name}-executor"
    pipeline_trigger_lambda_response = lambda_client.create_function(
        FunctionName=pipeline_trigger_lambda_function_name,
        Runtime='python3.12',
        Role=role_arn,
        Handler='index.lambda_handler',
        Code={
            'S3Bucket': deployment_bucket,
            'S3Key': pipeline_trigger_deployment_zip
        },
        Environment={
            'Variables': {
                'STEP_FUNCTION_ARN': state_machine_arn
            }
        },
        Tags=tags
    )
    
    # Add SQS trigger to Lambda
    lambda_client.create_event_source_mapping(
        EventSourceArn=queue_arn,
        FunctionName=pipeline_trigger_lambda_function_name,
        Enabled=True
    )
    
    # Save pipeline details to DynamoDB
    table_name = os.environ.get("MEDIALAKE_PIPELINE_TABLE")
    if not table_name:
        raise ValueError("MEDIALAKE_PIPELINE_TABLE environment variable not set")
    
    # Convert the definition's float values to Decimal
    definition = float_to_decimal(createpipeline.definition)
    
    table = dynamodb.Table(table_name)
    pipeline_item = {
        "id": pipeline_id,
        "name": createpipeline.name,
        "type": createpipeline.type,
        "createdAt": current_time,
        "updatedAt": current_time,
        "definition": definition,
        "queueUrl": queue_url,
        "queueArn": queue_arn,
        "eventBridgeRuleArn": rule_arn,
        "triggerLambdaArn": pipeline_trigger_lambda_response['FunctionArn'],
        "stateMachineArn": state_machine_arn,
        "roleArn": role_arn
    }
    
    table.put_item(Item=pipeline_item)
    
    return {
        "status": "200",
        "message": "Pipeline created successfully",
        "data": {
            "pipeline_id": pipeline_id,
            "name": createpipeline.name,
            "type": createpipeline.type
        }
    }
    

def create_metadata_extractor_lambda(lambda_client, function_name, role_arn, deployment_bucket, deployment_zip, exiftool_layer_arn, exempitool_layer_arn, environment, tags):
    return lambda_client.create_function(
        FunctionName=function_name,
        Runtime='python3.12',
        Role=role_arn,
        Handler='index.lambda_handler',
        Code={
            'S3Bucket': deployment_bucket,
            'S3Key': deployment_zip
        },
        Environment={
            'Variables': environment
        },
        Layers=[exiftool_layer_arn, exempitool_layer_arn],
        Tags=tags
    )

def create_image_proxy_lambda(lambda_client, function_name, role_arn, deployment_bucket, deployment_zip, environment, tags):
    return lambda_client.create_function(
        FunctionName=function_name,
        Runtime='python3.12',
        Role=role_arn,
        Handler='index.lambda_handler',
        Code={
            'S3Bucket': deployment_bucket,
            'S3Key': deployment_zip
        },
        Environment={
            'Variables': environment
        },
        Tags=tags
    )