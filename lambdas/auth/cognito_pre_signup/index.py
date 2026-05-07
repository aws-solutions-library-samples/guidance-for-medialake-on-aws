"""
Cognito Pre-Signup Lambda for Media Lake.

This Lambda function is triggered during the Cognito user signup process
and handles group creation logic during user signup.
"""

import datetime
import json
import os

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
    Lambda handler for the Cognito Pre-Signup trigger.

    This function:
    1. Extracts user information from the event
    2. Ensures default groups exist in the authorization table
    3. Auto-confirms the user and verifies their email

    Args:
        event: Cognito Pre-Signup event
        context: Lambda context

    Returns:
        Event to allow the signup to proceed
    """
    logger.info("Cognito Pre-Signup Lambda invoked")
    logger.debug(f"Event: {json.dumps(event)}")

    # Extract user information
    user_attributes = event.get("request", {}).get("userAttributes", {})
    user_id = user_attributes.get("sub")
    email = user_attributes.get("email")

    logger.info(f"Processing signup for user: {email} (ID: {user_id})")

    # Check if the default "all_users" group exists and create it if not
    try:
        # Check if the default group exists
        default_group_id = "all_users"
        response = auth_table.get_item(
            Key={"PK": f"GROUP#{default_group_id}", "SK": "METADATA"}
        )

        # If the group doesn't exist, create it
        if "Item" not in response:
            logger.info(f"Creating default group: {default_group_id}")

            # Create the group with metadata
            auth_table.put_item(
                Item={
                    "PK": f"GROUP#{default_group_id}",
                    "SK": "METADATA",
                    "groupName": "All Users",
                    "description": "Default group for all users",
                    "createdAt": datetime.datetime.now().isoformat(),
                    "type": "GROUP",
                }
            )
            logger.info(f"Default group '{default_group_id}' created successfully")
        else:
            logger.info(f"Default group '{default_group_id}' already exists")

        # Note: We don't add the user to the group here because the user ID might not be
        # fully created yet. This is typically done in a post-confirmation Lambda or
        # during the first login.

    except Exception as e:
        # Log the error but don't prevent user signup
        logger.error(f"Error checking/creating default group: {str(e)}")
        # We continue with the signup process despite the error

    # Allow the signup to proceed
    event["response"]["autoConfirmUser"] = True

    # Auto-verify email if present
    if email:
        event["response"]["autoVerifyEmail"] = True

    logger.info(f"User signup processed successfully for {email}")
    return event
