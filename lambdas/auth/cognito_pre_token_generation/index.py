"""
Cognito Pre-Token Generation Lambda for Media Lake.

This Lambda function is triggered during the Cognito token generation process
and inserts custom claims (e.g., group memberships) into the ID token.
"""

import os
import json
import boto3
from aws_lambda_powertools import Logger

logger = Logger()

# Initialize clients
dynamodb = boto3.resource("dynamodb")

# Get environment variables
AUTH_TABLE_NAME = os.environ.get("AUTH_TABLE_NAME")

auth_table = dynamodb.Table(AUTH_TABLE_NAME)


@logger.inject_lambda_context
def lambda_handler(event, context):
    """
    Cognito Pre Token Generation trigger to enrich JWT tokens (V2_0)
    """

    logger.info("Cognito Pre-Token Generation Lambda invoked")
    logger.info(f"Full event: {json.dumps(event)}")
    
    # Check if this is a V2_0 event
    version = event.get("version", "1")
    logger.info(f"Pre Token Generation version: {version}")
    
    # Log the event structure for debugging
    logger.info(f"Event keys: {list(event.keys())}")
    logger.info(f"Request keys: {list(event.get('request', {}).keys())}")
    logger.info(f"Response keys: {list(event.get('response', {}).keys())}")

    # Extract user information
    user_attributes = event.get("request", {}).get("userAttributes", {})
    # Use sub as the primary user identifier
    user_id = user_attributes.get("sub")

    if not user_id:
        logger.warning("No user ID found in the event")
        return event

    logger.info(f"Processing token for user: {user_id}")

    # Initialize empty lists for groups and permissions
    groups = []
    permissions = []

    try:
        # Query DynamoDB for user's group memberships
        # Format: PK=USER#{user_id}, SK begins_with(MEMBERSHIP#)
        response = auth_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(
                f"USER#{user_id}"
            )
            & boto3.dynamodb.conditions.Key("SK").begins_with("MEMBERSHIP#")
        )

        # Extract group IDs from the query results
        for item in response.get("Items", []):
            # SK format is MEMBERSHIP#{group_id}
            sk = item.get("SK", "")
            if sk.startswith("MEMBERSHIP#"):
                group_id = sk[len("MEMBERSHIP#") :]
                groups.append(group_id)
                logger.info(f"Found group membership: {group_id}")

        # Optionally, query for directly assigned permission sets
        # This could be expanded in the future to calculate effective roles

    except Exception as e:
        logger.error(f"Error querying DynamoDB: {str(e)}")
        # Continue with empty groups rather than failing the token generation

    # Add custom claims to the token based on version
    if version in ["2", "3"]:
        # V2_0/V3 format
        # Initialize claimsAndScopeOverrideDetails if it's null or doesn't exist
        if event["response"].get("claimsAndScopeOverrideDetails") is None:
            event["response"]["claimsAndScopeOverrideDetails"] = {}
        
        if "idTokenGeneration" not in event["response"]["claimsAndScopeOverrideDetails"]:
            event["response"]["claimsAndScopeOverrideDetails"]["idTokenGeneration"] = {}
        
        if "claimsToAddOrOverride" not in event["response"]["claimsAndScopeOverrideDetails"]["idTokenGeneration"]:
            event["response"]["claimsAndScopeOverrideDetails"]["idTokenGeneration"]["claimsToAddOrOverride"] = {}
        
        claims = event["response"]["claimsAndScopeOverrideDetails"]["idTokenGeneration"]["claimsToAddOrOverride"]
        
        # Add groups claim with the list of group IDs
        if groups:
            claims["cognito:groups"] = groups
        
        # Add custom permissions claim - for now, statically assign admin permissions
        permissions = [
            "asset:admin",
            "pipeline:admin",
            "integration:admin",
            "settings:admin"
        ]
        
        # Custom claims should use string values in V2
        claims["custom:permissions"] = json.dumps(permissions)
        
        # Also add to access token if needed
        if "accessTokenGeneration" not in event["response"]["claimsAndScopeOverrideDetails"]:
            event["response"]["claimsAndScopeOverrideDetails"]["accessTokenGeneration"] = {}
        
        if "claimsToAddOrOverride" not in event["response"]["claimsAndScopeOverrideDetails"]["accessTokenGeneration"]:
            event["response"]["claimsAndScopeOverrideDetails"]["accessTokenGeneration"]["claimsToAddOrOverride"] = {}
        
        access_claims = event["response"]["claimsAndScopeOverrideDetails"]["accessTokenGeneration"]["claimsToAddOrOverride"]
        access_claims["custom:permissions"] = json.dumps(permissions)
        
    else:
        # V1 format (legacy)
        if "claimsOverrideDetails" not in event["response"]:
            event["response"]["claimsOverrideDetails"] = {}

        if "claimsToAddOrOverride" not in event["response"]["claimsOverrideDetails"]:
            event["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"] = {}

        # Add groups claim with the list of group IDs
        if groups:
            event["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"]["cognito:groups"] = groups

        # Add custom permissions claim
        permissions = [
            "asset:admin",
            "pipeline:admin",
            "integration:admin",
            "settings:admin"
        ]
        
        event["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"]["custom:permissions"] = json.dumps(permissions)

    logger.info(f"Added groups claim with {len(groups)} groups")
    logger.info(f"Added custom:permissions claim with {len(permissions)} permissions")
    
    # Log the response structure for debugging
    logger.info(f"Final response structure: {json.dumps(event.get('response', {}))}")
    
    # For V2/V3, we should only have claimsAndScopeOverrideDetails
    if version in ["2", "3"] and "claimsOverrideDetails" in event["response"]:
        logger.warning("Removing claimsOverrideDetails from V2/V3 response")
        del event["response"]["claimsOverrideDetails"]

    return event
