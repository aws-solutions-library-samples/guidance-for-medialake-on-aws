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

        # Create AWS clients in the specified region
        lambda_client = boto3.client('lambda', region_name=region)
        iam = boto3.client('iam', region_name=region)
        s3 = boto3.client('s3', region_name=region)
        sqs = boto3.client('sqs', region_name=region)

        errors = []

        # Delete Lambda
        try:
            lambda_client.delete_function(FunctionName=lambda_arn.split(':')[-1])
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                errors.append(f"Error deleting Lambda: {str(e)}")

        # Delete IAM role
        role_name = iam_role_arn.split('/')[-1]
        try:
            # Detach all managed policies
            attached_policies = iam.list_attached_role_policies(RoleName=role_name)['AttachedPolicies']
            for policy in attached_policies:
                iam.detach_role_policy(RoleName=role_name, PolicyArn=policy['PolicyArn'])
            
            # Delete all inline policies
            inline_policies = iam.list_role_policies(RoleName=role_name)['PolicyNames']
            for policy_name in inline_policies:
                iam.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
            
            # Delete the role
            iam.delete_role(RoleName=role_name)
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchEntity':
                errors.append(f"Error deleting IAM role: {str(e)}")

        # Delete SQS queue
        try:
            sqs.delete_queue(QueueUrl=queue_url)
        except ClientError as e:
            if e.response['Error']['Code'] != 'AWS.SimpleQueueService.NonExistentQueue':
                errors.append(f"Error deleting SQS queue: {str(e)}")

        # Remove S3 bucket notification
        try:
            s3.put_bucket_notification_configuration(
                Bucket=bucket_name,
                NotificationConfiguration={}  # Empty config removes all notifications
            )
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchBucket':
                errors.append(f"Error removing S3 bucket notification: {str(e)}")

        # Delete connector from DynamoDB only if all other resources are cleaned up
        if not errors:
            table.delete_item(Key={'id': connector_id})
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Connector deleted successfully'})
            }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'message': 'Error deleting connector',
                    'errors': errors
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