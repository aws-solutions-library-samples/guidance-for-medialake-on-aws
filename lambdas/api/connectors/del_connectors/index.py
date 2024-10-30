import json
import boto3
import os
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['MEDIALAKE_CONNECTOR_TABLE'])

def lambda_handler(event, context):
    try:
        # Parse request body
        body = json.loads(event['body'])
        connector_id = body.get('id')
        
        if not connector_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Connector ID is required'})
            }

        # Get connector details from DynamoDB
        response = table.get_item(Key={'id': connector_id})
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'body': json.dumps({'message': 'Connector not found'})
            }

        connector = response['Item']
        region = connector.get('region', 'us-east-1')  # Default to us-east-1 if not specified
        queue_url = connector.get('queueUrl')
        bucket_name = connector.get('storageIdentifier')
        lambda_arn = connector.get('lambdaArn')
        iam_role_arn = connector.get('iamRoleArn')

        if not all([queue_url, bucket_name, lambda_arn, iam_role_arn]):
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Invalid connector configuration'})
            }

        # Create S3 and SQS clients in the specified region
        # Create AWS clients in the specified region
        lambda_client = boto3.client('lambda', region_name=region)
        iam = boto3.client('iam', region_name=region)
        s3 = boto3.client('s3', region_name=region)
        sqs = boto3.client('sqs', region_name=region)

        try:
            # Delete Lambda 
            lambda_client.delete_function(FunctionName=lambda_arn.split(':')[-1])
            # Delete IAM role
            role_name = iam_role_arn.split('/')[-1]
            # Get queue ARN
            queue_attributes = sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['QueueArn']
            )
            queue_arn = queue_attributes['Attributes']['QueueArn']
            for policy in iam.list_attached_role_policies(RoleName=role_name)['AttachedPolicies']:
                iam.detach_role_policy(RoleName=role_name, PolicyArn=policy['PolicyArn'])
            iam.delete_role(RoleName=role_name)
            
            # Delete SQS queue
            sqs.delete_queue(QueueUrl=queue_url)
            
            # Remove S3 bucket notification
            s3.put_bucket_notification_configuration(
                Bucket=bucket_name,
                NotificationConfiguration={}  # Empty config removes all notifications
            )

            # Delete SQS queue
            # sqs.delete_queue(QueueUrl=queue_url)

            # Delete connector from DynamoDB
            table.delete_item(Key={'id': connector_id})

            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Connector deleted successfully'})
            }

        except ClientError as e:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'message': 'Error deleting connector',
                    'error': str(e)
                })
            }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Internal server error',
                'error': str(e)
            })
        }