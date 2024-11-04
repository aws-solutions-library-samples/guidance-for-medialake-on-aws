import os
import uuid
import json
import time
import boto3
from decimal import Decimal
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

from image_pipeline_definitions import (
    get_state_machine_definition,
    create_metadata_extractor_lambda,
    create_image_proxy_lambda
)

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


class S3Pipeline(BaseModel):
    definition: dict
    name: str
    type: str

def float_to_decimal(obj):
    """Convert float values to Decimal for DynamoDB compatibility"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [float_to_decimal(x) for x in obj]
    return obj

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
        # Create the queue first
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

        # Add permission for EventBridge to send messages
        queue_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "EventBridgeToSQS",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "events.amazonaws.com"
                    },
                    "Action": "sqs:SendMessage",
                    "Resource": queue_arn
                }
            ]
        }

        # Set the queue policy
        sqs_client.set_queue_attributes(
            QueueUrl=queue_url,
            Attributes={
                'Policy': json.dumps(queue_policy)
            }
        )

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

def create_eventbridge_rule(
    rule_name: str, 
    event_bus_name: str, 
    queue_arn: str,
    tags: dict
) -> str:
    """Create EventBridge rule to send all events to SQS FIFO queue"""
    try:
        eventbridge = boto3.client('events')
        
        # Create the rule
        response = rule = eventbridge.put_rule(
            Name=rule_name,
            EventBusName=event_bus_name,
            EventPattern=json.dumps({
                "detail": {
                    "eventType": ["AssetIngested"]
                }
            }),
            State='ENABLED',
            Tags=[{'Key': k, 'Value': v} for k, v in tags.items()]
        )
        
        # Add target (SQS queue)
        eventbridge.put_targets(
            Rule=rule_name,
            EventBusName=event_bus_name,
            Targets=[
                {
                    'Id': f"{rule_name}-target",
                    'Arn': queue_arn,
                    'SqsParameters': {
                        'MessageGroupId': 'default'  # Required for FIFO queues
                    }
                }
            ]
        )
        
        return response['RuleArn']
    except Exception as e:
        logger.error(f"Failed to create EventBridge rule: {str(e)}")
        raise


def create_pipeline_role(role_name: str, queue_arn: str, state_machine_name: str, tags: dict) -> str:
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
        
        # Create and attach SQS policy
        sqs_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                        "sqs:GetQueueAttributes",
                        "sqs:ChangeMessageVisibility",
                        "sqs:SendMessage" 
                    ],
                    "Resource": queue_arn
                }
            ]
        }
        
        # Create and attach Step Functions execution policy
        step_functions_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "states:StartExecution",
                        "states:DescribeExecution",
                        "states:StopExecution"
                    ],
                    "Resource": [
                        f"arn:aws:states:{os.environ['AWS_REGION']}:{os.environ['AWS_ACCOUNT_ID']}:stateMachine:{state_machine_name}",
                        f"arn:aws:states:{os.environ['AWS_REGION']}:{os.environ['AWS_ACCOUNT_ID']}:execution:{state_machine_name}:*"
                    ]
                }
            ]
        }
        
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}-sqs-policy",
            PolicyDocument=json.dumps(sqs_policy)
        )

        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}-stepfunctions-policy",
            PolicyDocument=json.dumps(step_functions_policy)
        )
        
        # Create and attach DynamoDB policy
        dynamodb_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "dynamodb:UpdateItem",
                        "dynamodb:GetItem",  
                        "dynamodb:PutItem"   
                    ],
                    "Resource": [
                        f"{os.environ['MEDIALAKE_ASSET_TABLE']}"
                    ]
                }
            ]
        }

        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}-dynamodb-policy",
            PolicyDocument=json.dumps(dynamodb_policy)
        )
        
        lambda_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "lambda:InvokeFunction"
                    ],
                    "Resource": [
                        f"arn:aws:lambda:{os.environ['AWS_REGION']}:{os.environ['AWS_ACCOUNT_ID']}:function:medialake-pipeline-*"
                    ]
                }
            ]
        }

        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}-lambda-policy",
            PolicyDocument=json.dumps(lambda_policy)
        )
        
        # Create and attach S3 policy
        s3_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                    ],
                    "Resource": [
                        "arn:aws:s3:::*/*"
                    ]
                }
            ]
        }

        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}-read-s3-policy",
            PolicyDocument=json.dumps(s3_policy)
        )
        
        s3_write_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:PutObject",
                        "s3:PutObjectAcl"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{os.environ['MEDIA_ASSETS_BUCKET_NAME']}/*",
                        f"arn:aws:s3:::{os.environ.get('MEDIA_ASSETS_BUCKET_NAME')}"
                    ]
                }
            ]
        }

        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}-write-s3-policy",
            PolicyDocument=json.dumps(s3_write_policy)
        )
        
        
        kms_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "kms:GenerateDataKey"
                    ],
                    "Resource": [
                        os.environ['MEDIA_ASSETS_BUCKET_NAME_KMS_KEY']
                    ]
                }
            ]
        }

        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}-kms-policy",
            PolicyDocument=json.dumps(kms_policy)
        )

        
        
        return response['Role']['Arn']
    except Exception as e:
        logger.error(f"Failed to create IAM role: {str(e)}")
        raise


def check_resource_exists(
    pipeline_name: str,
    queue_name: str,
    rule_name: str,
    role_name: str,
    state_machine_name: str,
    lambda_names: list
) -> tuple[bool, str]:
    """Check if any of the resources already exist"""
    try:
        # Check SQS Queue
        try:
            sqs_client.get_queue_url(QueueName=f"{queue_name}.fifo")
            return True, f"SQS Queue {queue_name}.fifo already exists"
        except sqs_client.exceptions.QueueDoesNotExist:
            pass

        # Check EventBridge Rule
        try:
            eventbridge = boto3.client('events')
            eventbridge.describe_rule(Name=rule_name)
            return True, f"EventBridge Rule {rule_name} already exists"
        except eventbridge.exceptions.ResourceNotFoundException:
            pass

        # Check IAM Role
        try:
            iam_client.get_role(RoleName=role_name)
            return True, f"IAM Role {role_name} already exists"
        except iam_client.exceptions.NoSuchEntityException:
            pass

        # Check Step Function
        try:
            sfn_client.describe_state_machine(
                stateMachineArn=f"arn:aws:states:{os.environ['AWS_REGION']}:{os.environ['AWS_ACCOUNT_ID']}:stateMachine:{state_machine_name}"
            )
            return True, f"State Machine {state_machine_name} already exists"
        except sfn_client.exceptions.StateMachineDoesNotExist:
            pass

        # Check Lambda Functions
        for lambda_name in lambda_names:
            try:
                lambda_client.get_function(FunctionName=lambda_name)
                return True, f"Lambda Function {lambda_name} already exists"
            except lambda_client.exceptions.ResourceNotFoundException:
                pass

        # Check DynamoDB for pipeline name
        table_name = os.environ.get("MEDIALAKE_PIPELINE_TABLE")
        if table_name:
            table = dynamodb.Table(table_name)
            response = table.scan(
                FilterExpression='#name = :name',
                ExpressionAttributeNames={'#name': 'name'},
                ExpressionAttributeValues={':name': pipeline_name}
            )
            if response['Items']:
                return True, f"Pipeline with name {pipeline_name} already exists"

        return False, ""

    except Exception as e:
        logger.error(f"Error checking resource existence: {str(e)}")
        raise

@app.post("/pipelines")
def create_pipeline(createpipeline: S3Pipeline) -> dict:
    try:
        
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
                f"medialake-pipeline-{createpipeline.name}-metadata"  # Add this
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
        
        
        # Common tags for all resources
        tags = {
            'medialake': 'true',
            'pipeline_id': pipeline_id,
            'pipeline_name': createpipeline.name
        }
        
        # Create SQS FIFO Queue
        queue_name = f"medialake-pipeline-{createpipeline.name}"
        queue_url, queue_arn = create_sqs_fifo_queue(queue_name, tags)
        
        # Create EventBridge rule
        rule_name = f"medialake-pipeline-{createpipeline.name}-rule"
        rule_arn = create_eventbridge_rule(
            rule_name,
            ingest_event_bus_name,
            queue_arn,
            tags
        )
        
        # Create IAM Role for Lambda and Step Functions
        role_name = f"medialake-pipeline-{createpipeline.name}-role"
        state_machine_name = f"medialake-pipeline-{createpipeline.name}"
        role_arn = create_pipeline_role(
            role_name,
            queue_arn,
            state_machine_name,
            tags
        )
        
        # Wait for IAM role propagation
        time.sleep(10)
        
        # Add this before creating the image proxy lambda
        image_metadata_extractor_lambda_function_name = f"medialake-pipeline-{createpipeline.name}-metadata"
        # image_metadata_extractor_lambda_response = lambda_client.create_function(
        #     FunctionName=image_metadata_extractor_lambda_function_name,
        #     Runtime='python3.12',
        #     Role=role_arn,
        #     Handler='index.lambda_handler',
        #     Code={
        #         'S3Bucket': deployment_bucket,
        #         'S3Key': image_metadata_extractor_deployment_zip
        #     },
        #     Tags=tags
        # )

        
        image_proxy_lambda_function_name = f"medialake-pipeline-{createpipeline.name}-image-proxy"
        # image_proxy_lambda_response = lambda_client.create_function(
        #     FunctionName=image_proxy_lambda_function_name,
        #     Runtime='python3.12',
        #     Role=role_arn,
        #     Handler='index.lambda_handler',
        #     Code={
        #         'S3Bucket': deployment_bucket,
        #         'S3Key': image_proxy_deployment_zip
        #     },
        #     Tags=tags
        # ) 
        
        # Create metadata extractor lambda
        image_metadata_extractor_lambda_response = create_metadata_extractor_lambda(
            lambda_client,
            image_metadata_extractor_lambda_function_name,
            role_arn,
            deployment_bucket,
            image_metadata_extractor_deployment_zip,
            exiftool_layer_arn,
            tags
        )

        # Create image proxy lambda
        image_proxy_lambda_response = create_image_proxy_lambda(
            lambda_client,
            image_proxy_lambda_function_name,
            role_arn,
            deployment_bucket,
            image_proxy_deployment_zip,
            tags
        )
        
        # media_assets_bucket = s3_client.get_bucket(os.environ.get('AWS_ACCOUNT_ID'),os.environ.get('MEDIA_ASSETS_BUCKET_NAME'))

        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowLambdaWriteAccess",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "lambda.amazonaws.com"  # Use service principal
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
        # In post_pipelines/index.py, update the state_machine_definition:

        # state_machine_definition = {
        #     "Comment": f"Pipeline {createpipeline.name}",
        #     "StartAt": "ExtractMetadata",
        #     "States": {
        #         "ExtractMetadata": {
        #             "Type": "Task",
        #             "Resource": "arn:aws:states:::lambda:invoke",
        #             "Parameters": {
        #                 "FunctionName": image_metadata_extractor_lambda_response['FunctionArn'],
        #                 "Payload": {
        #                     "pipeline_id.$": "$.pipeline_id",
        #                     "input.$": "$.input",
        #                     "parameters": {
        #                         "s3_uri.$": "States.Format('s3://{}/{}', $.input.sourceLocation.bucket, $.input.sourceLocation.path)"
        #                     }
        #                 }
        #             },
        #             "ResultPath": "$.metadataResult",
        #             "Next": "CreateProxy"
        #         },
        #         "CreateProxy": {
        #             "Type": "Task",
        #             "Resource": "arn:aws:states:::lambda:invoke",
        #             "Parameters": {
        #                 "FunctionName": image_proxy_lambda_response['FunctionArn'],
        #                 "Payload": {
        #                     "pipeline_id.$": "$.pipeline_id",
        #                     "input.$": "$.input",
        #                     "metadata.$": "$.metadataResult.body",
        #                     "parameters": {
        #                         "s3_uri.$": "States.Format('s3://{}/{}', $.input.sourceLocation.bucket, $.input.sourceLocation.path)",
        #                         "mode": "proxy",
        #                         "output_bucket": "YOUR_OUTPUT_BUCKET"
        #                     }
        #                 }
        #             },
        #             "ResultPath": "$.proxyResult",
        #             "Next": "UpdateDynamoDB"
        #         },
        #         "UpdateDynamoDB": {
        #             "Type": "Task",
        #             "Resource": "arn:aws:states:::dynamodb:updateItem",
        #             "Parameters": {
        #                 "TableName": "${process.env.MEDIALAKE_ASSET_TABLE}",
        #                 "Key": {
        #                     "id": {"S.$": "$.input.id"}
        #                 },
        #                 "UpdateExpression": "SET proxyLocation = :proxyLocation, metadata = :metadata",
        #                 "ExpressionAttributeValues": {
        #                     ":proxyLocation": {
        #                         "M": {
        #                             "bucket": {"S.$": "$.proxyResult.body.bucket"},
        #                             "key": {"S.$": "$.proxyResult.body.key"},
        #                             "type": {"S": "S3"}
        #                         }
        #                     },
        #                     ":metadata": {"M.$": "$.metadataResult.body"}
        #                 }
        #             },
        #             "End": true
        #         }
        #     }
        # }


        # Get state machine definition

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
        

        
        # Create Lambda Function
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