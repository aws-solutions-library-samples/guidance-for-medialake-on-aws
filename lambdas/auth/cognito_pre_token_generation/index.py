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
    Cognito Pre Token Generation trigger to enrich JWT tokens
    """

    logger.info("Cognito Pre-Token Generation Lambda invoked")
    logger.debug(f"Event: {json.dumps(event)}")

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

    # Add custom claims to the token
    if "claimsOverrideDetails" not in event["response"]:
        event["response"]["claimsOverrideDetails"] = {}

    if "claimsToAddOrOverride" not in event["response"]["claimsOverrideDetails"]:
        event["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"] = {}

    # Add groups claim with the list of group IDs
    event["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"]["groups"] = (
        json.dumps(groups)
    )

    logger.info(f"Added groups claim with {len(groups)} groups")

    return event
