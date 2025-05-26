import boto3
import os
import argparse
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger

# Initialize logger
logger = Logger(service="group-gsi-migration")

def update_group_gsi_attributes(table_name):
    """
    Update existing group items in DynamoDB to add missing GSI1PK and GSI1SK attributes.
    
    This script fixes groups that were created without the necessary GSI attributes
    that the list_groups Lambda function uses to query groups.
    """
    try:
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(table_name)
        
        logger.info(f"Starting migration for table: {table_name}")
        
        # Scan for all group items
        response = table.scan(
            FilterExpression="begins_with(PK, :pk_prefix) AND SK = :sk",
            ExpressionAttributeValues={
                ":pk_prefix": "GROUP#",
                ":sk": "METADATA"
            }
        )
        
        items = response.get('Items', [])
        
        # Process pagination if there are more results
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression="begins_with(PK, :pk_prefix) AND SK = :sk",
                ExpressionAttributeValues={
                    ":pk_prefix": "GROUP#",
                    ":sk": "METADATA"
                },
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))
        
        logger.info(f"Found {len(items)} group items to update")
        
        # Update each item to add GSI attributes
        updated_count = 0
        for item in items:
            group_id = item.get('id')
            
            # Skip items that already have GSI1PK and GSI1SK
            if 'GSI1PK' in item and 'GSI1SK' in item:
                logger.info(f"Group {group_id} already has GSI attributes, skipping")
                continue
                
            if group_id:
                try:
                    table.update_item(
                        Key={
                            'PK': item['PK'],
                            'SK': item['SK']
                        },
                        UpdateExpression="SET GSI1PK = :gsi1pk, GSI1SK = :gsi1sk",
                        ExpressionAttributeValues={
                            ':gsi1pk': 'GROUPS',
                            ':gsi1sk': f'GROUP#{group_id}'
                        }
                    )
                    logger.info(f"Updated group {group_id}")
                    updated_count += 1
                except ClientError as e:
                    logger.error(f"Error updating group {group_id}: {str(e)}")
            else:
                logger.warning(f"Group item missing id attribute: {item}")
        
        logger.info(f"Migration complete. Updated {updated_count} groups.")
        return updated_count
        
    except Exception as e:
        logger.exception(f"Error during migration: {str(e)}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fix missing GSI attributes for group items in DynamoDB')
    parser.add_argument('--table', required=True, help='DynamoDB table name')
    
    args = parser.parse_args()
    
    print(f"Starting migration for table: {args.table}")
    updated = update_group_gsi_attributes(args.table)
    print(f"Migration complete. Updated {updated} groups.")