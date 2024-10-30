import os
import uuid
import json
import time
import boto3
from datetime import datetime
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.event_handler import (
    APIGatewayRestResolver,
    Response,
    content_types,
)
from aws_lambda_powertools.event_handler.openapi.exceptions import (
    RequestValidationError,
)
from pydantic import BaseModel

tracer = Tracer()
logger = Logger()
app = APIGatewayRestResolver(enable_validation=True)

# Initialize AWS clients
s3_client = boto3.client("s3")
dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')
iam_client = boto3.client('iam')
sqs_client = boto3.client('sqs')
sfn_client = boto3.client('stepfunctions')

class S3PipelineConfig(BaseModel):
    bucket: str


class S3Pipeline(BaseModel):
    configuration: S3PipelineConfig
    name: str
    type: str


@app.exception_handler(RequestValidationError)
def handle_validation_error(ex: RequestValidationError):
    logger.error(
        "Request failed validation",
        path=app.current_event.path,
        errors=ex.errors()
    )
    return Response(
        status_code=422,
        content_type=content_types.APPLICATION_JSON,
        body={
            "status": "422",
            "message": "Invalid data",
            "data": {
                "details": ex.errors(),
            },
        },
    )


def create_sqs_fifo_queue(queue_name: str, tags: dict) -> tuple[str, str]:
    """Create SQS FIFO queue and return queue URL and ARN"""
    try:
        response = sqs_client.create_queue(
            QueueName=f"{queue_name}.fifo",
            Attributes={
                'FifoQueue': 'true',
                'ContentBasedDeduplication': 'true',
                'DeduplicationScope': 'messageGroup',
                'FifoThroughputLimit': 'perMessageGroupId'
            },
            tags=tags
        )
        queue_url = response['QueueUrl']

        # Get queue ARN
        queue_attributes = sqs_client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['QueueArn']
        )
        queue_arn = queue_attributes['Attributes']['QueueArn']

        return queue_url, queue_arn
    except Exception as e:
        logger.error(f"Failed to create SQS FIFO queue: {str(e)}")
        raise


def create_state_machine(
    state_machine_name: str,
    role_arn: str,
    definition: dict,
    tags: dict
) -> str:
    """Create Step Function state machine and return its ARN"""
    try:
        response = sfn_client.create_state_machine(
            name=state_machine_name,
            definition=json.dumps(definition),
            roleArn=role_arn,
            type='STANDARD',
            tags=[{'key': k, 'value': v} for k, v in tags.items()]
        )
        return response['stateMachineArn']
    except Exception as e:
        logger.error(f"Failed to create Step Function: {str(e)}")
        raise


def create_pipeline_role(role_name: str, tags: dict) -> str:
    """Create IAM role for pipeline execution"""
    try:
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {
                    "Service": [
                        "lambda.amazonaws.com",
                        "states.amazonaws.com"
                    ]
                },
                "Action": "sts:AssumeRole"
            }]
        }
        
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
            Tags=[{'Key': k, 'Value': v} for k, v in tags.items()]
        )
        
        # Attach necessary policies
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
        )
        
        # Add Step Functions execution policy
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/service-role/AWSStepFunctionsFullAccess'
        )
        
        return response['Role']['Arn']
    except Exception as e:
        logger.error(f"Failed to create IAM role: {str(e)}")
        raise


@app.post("/pipelines")
def create_pipeline(createpipeline: S3Pipeline) -> dict:
    try:
        # Generate unique ID and timestamps
        pipeline_id = str(uuid.uuid4())
        current_time = datetime.utcnow().isoformat(timespec='seconds')
        
        # Common tags for all resources
        tags = {
            'medialake': 'true',
            'pipeline_id': pipeline_id,
            'pipeline_name': createpipeline.name
        }
        
        # 1. Create SQS FIFO Queue
        queue_name = f"pipeline-{pipeline_id}"
        queue_url, queue_arn = create_sqs_fifo_queue(queue_name, tags)
        
        # 2. Create IAM Role for Lambda and Step Functions
        role_name = f"pipeline-{pipeline_id}-role"
        role_arn = create_pipeline_role(role_name, tags)
        
        # Wait for IAM role propagation
        time.sleep(10)
        
        # 3. Create Lambda Function
        lambda_function_name = f"pipeline-{pipeline_id}-executor"
        lambda_response = lambda_client.create_function(
            FunctionName=lambda_function_name,
            Runtime='python3.9',
            Role=role_arn,
            Handler='index.handler',
            Code={
                'S3Bucket': os.environ['PIPELINE_LAMBDA_BUCKET'],
                'S3Key': os.environ['PIPELINE_LAMBDA_KEY']
            },
            Tags=tags
        )
        
        # Add SQS trigger to Lambda
        lambda_client.create_event_source_mapping(
            EventSourceArn=queue_arn,
            FunctionName=lambda_function_name,
            Enabled=True
        )
        
        # 4. Create Step Function
        state_machine_name = f"pipeline-{pipeline_id}"
        state_machine_definition = {
            "Comment": f"Pipeline {createpipeline.name}",
            "StartAt": "StartPipeline",
            "States": {
                "StartPipeline": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::lambda:invoke",
                    "Parameters": {
                        "FunctionName": lambda_response['FunctionArn'],
                        "Payload": {
                            "pipeline_id.$": "$.pipeline_id",
                            "input.$": "$.input"
                        }
                    },
                    "End": True
                }
            }
        }
        
        state_machine_arn = create_state_machine(
            state_machine_name,
            role_arn,
            state_machine_definition,
            tags
        )
        
        # Save pipeline details to DynamoDB
        table_name = os.environ.get("MEDIALAKE_PIPELINE_TABLE")
        if not table_name:
            raise ValueError("MEDIALAKE_PIPELINE_TABLE environment variable not set")
        
        table = dynamodb.Table(table_name)
        pipeline_item = {
            "id": pipeline_id,
            "name": createpipeline.name,
            "type": createpipeline.type,
            "createdAt": current_time,
            "updatedAt": current_time,
            "configuration": {
                "bucket": createpipeline.configuration.bucket
            },
            "queueUrl": queue_url,
            "queueArn": queue_arn,
            "lambdaArn": lambda_response['FunctionArn'],
            "stateMachineArn": state_machine_arn,
            "roleArn": role_arn
        }
        
        table.put_item(Item=pipeline_item)
        
        logger.info(f"Created pipeline '{createpipeline.name}' with ID {pipeline_id}")
        
        return {
            "status": "200",
            "message": "Pipeline created successfully",
            "data": pipeline_item
        }

    except Exception as e:
        logger.exception(f"Failed to create pipeline: {str(e)}")
        return {
            "statusCode": 500,
            "body": {
                "status": "500",
                "message": f"Failed to create pipeline: {str(e)}",
                "data": {}
            }
        }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)