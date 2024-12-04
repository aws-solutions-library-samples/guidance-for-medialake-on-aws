import boto3
import cfnresponse
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)
dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    try:
        logger.info('Received event: %s', event)  # Changed to use %s formatting instead of f-string
        request_type = event['RequestType']
        
        if request_type == 'Delete':
            table_name = event['ResourceProperties']['TableName']
            table = dynamodb.Table(table_name)
            
            # Scan the table to get all resources that need cleanup
            response = table.scan()
            items = response['Items']
            
            # Continue scanning if we haven't got all items
            while 'LastEvaluatedKey' in response:
                response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                items.extend(response['Items'])
            
            # Process each resource for cleanup
            for item in items:
                # Here you would implement the specific cleanup logic
                # based on the resource type and identifier stored in DynamoDB
                logger.info('Cleaning up resource: %s', item)  # Changed to use %s formatting
                # Example: if item contains AWS resource IDs, use boto3 to delete them
            
            logger.info('Cleanup completed successfully')
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
        else:
            # For Create/Update events, just respond success
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
    
    except Exception as e:
        logger.error('Error during cleanup: %s', str(e))  # Changed to use %s formatting
        cfnresponse.send(event, context, cfnresponse.FAILED, {})