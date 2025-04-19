#!/usr/bin/env python3
"""
Script to manually create a new deployment for the MediaLake API Gateway.
This ensures all resources are included in the deployment and available via the stage.
"""
import argparse
import boto3
import json
import time
from config import config

def get_rest_api_id(profile_name):
    """Get the ID of the MediaLake API Gateway"""
    session = boto3.Session(profile_name=profile_name)
    api_client = session.client('apigateway')
    
    apis = api_client.get_rest_apis()
    for api in apis.get('items', []):
        if api.get('name') == 'MediaLakeApi':
            return api.get('id')
    
    return None

def create_deployment(api_id, stage_name, profile_name):
    """Create a new deployment for the API and associate it with the stage"""
    session = boto3.Session(profile_name=profile_name)
    api_client = session.client('apigateway')
    
    # Check if stage already exists
    try:
        stages = api_client.get_stages(restApiId=api_id)
        stage_exists = any(stage.get('stageName') == stage_name for stage in stages.get('item', []))
    except Exception as e:
        print(f"Error checking stages: {e}")
        stage_exists = False
    
    # Create deployment
    try:
        response = api_client.create_deployment(
            restApiId=api_id,
            stageName=stage_name if not stage_exists else None,
            description=f"Manual deployment to {stage_name} stage"
        )
        deployment_id = response.get('id')
        print(f"Successfully created deployment {deployment_id}")
        
        # If stage exists, update it to use the new deployment
        if stage_exists:
            api_client.update_stage(
                restApiId=api_id,
                stageName=stage_name,
                patchOperations=[
                    {
                        'op': 'replace',
                        'path': '/deploymentId',
                        'value': deployment_id
                    }
                ]
            )
            print(f"Updated stage {stage_name} to use deployment {deployment_id}")
        
        return deployment_id
    except Exception as e:
        print(f"Error creating deployment: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Create a new deployment for MediaLake API Gateway')
    parser.add_argument('--profile', dest='profile', required=True, help='AWS profile to use')
    parser.add_argument('--stage', dest='stage', default=config.api_path, help=f'Stage name (default: {config.api_path})')
    
    args = parser.parse_args()
    
    print(f"Finding MediaLake API using profile {args.profile}...")
    api_id = get_rest_api_id(args.profile)
    
    if not api_id:
        print("MediaLakeApi not found. Make sure the API Gateway has been deployed.")
        return
    
    print(f"Found MediaLake API ID: {api_id}")
    print(f"Creating new deployment for stage: {args.stage}")
    
    deployment_id = create_deployment(api_id, args.stage, args.profile)
    
    if deployment_id:
        print(f"\nDeployment successfully created!")
        api_url = f"https://{api_id}.execute-api.{boto3.Session(profile_name=args.profile).region_name}.amazonaws.com/{args.stage}"
        print(f"API now available at: {api_url}")
    else:
        print("Failed to create deployment.")

if __name__ == "__main__":
    main() 