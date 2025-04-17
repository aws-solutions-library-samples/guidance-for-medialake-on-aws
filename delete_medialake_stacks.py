#!/usr/bin/env python3
import argparse
import time
import boto3
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger

logger = Logger()

def list_medialake_stacks(cf_client):
    """List all CloudFormation stacks with the prefix MediaLake."""
    stacks = []
    
    try:
        paginator = cf_client.get_paginator('list_stacks')
        for page in paginator.paginate(
            StackStatusFilter=[
                'CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE',
                'ROLLBACK_COMPLETE', 'IMPORT_COMPLETE', 'IMPORT_ROLLBACK_COMPLETE'
            ]
        ):
            for stack in page['StackSummaries']:
                if stack['StackName'].startswith('MediaLake'):
                    stacks.append(stack['StackName'])
    except ClientError as e:
        logger.error(f"Error listing stacks: {e}")
        raise
    
    return stacks

def delete_stack(cf_client, stack_name):
    """Delete a CloudFormation stack."""
    try:
        logger.info(f"Deleting stack: {stack_name}")
        cf_client.delete_stack(StackName=stack_name)
        return True
    except ClientError as e:
        logger.error(f"Error deleting stack {stack_name}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Delete all MediaLake CloudFormation stacks')
    parser.add_argument('--profile', required=True, help='AWS profile name')
    parser.add_argument('--region', required=True, help='AWS region')
    
    args = parser.parse_args()
    
    # Create session with specified profile
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    cf_client = session.client('cloudformation')
    
    while True:
        stacks = list_medialake_stacks(cf_client)
        
        if not stacks:
            logger.info("No MediaLake stacks remaining. Deletion complete.")
            break
        
        logger.info(f"Found {len(stacks)} MediaLake stacks: {', '.join(stacks)}")
        
        # Attempt to delete all stacks
        deleted_any = False
        for stack_name in stacks:
            if delete_stack(cf_client, stack_name):
                deleted_any = True
        
        if not deleted_any and stacks:
            logger.warning("Failed to delete any stacks in this iteration. Check for dependencies.")
        
        logger.info(f"Waiting 60 seconds before checking again...")
        time.sleep(60)

if __name__ == "__main__":
    main() 