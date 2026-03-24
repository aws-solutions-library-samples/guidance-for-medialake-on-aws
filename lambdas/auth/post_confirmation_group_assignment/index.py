import json
import os
import boto3
from aws_lambda_powertools import Logger

logger = Logger()
cognito_client = boto3.client("cognito-idp")

USER_POOL_ID = os.environ.get("USER_POOL_ID")
IDP_GROUP_MAPPING = json.loads(os.environ.get("IDP_GROUP_MAPPING", "{}"))

@logger.inject_lambda_context
def handler(event, context):
    trigger_source = event.get("triggerSource", "")
    if trigger_source != "PostConfirmation_ConfirmSignUp":
        logger.info(f"Skipping non-confirmation trigger: {trigger_source}")
        return event

    username = event.get("userName", "")
    # Federated usernames: {provider_name}_{provider_user_id}
    provider_name = username.split("_", 1)[0] if "_" in username else None

    if not provider_name:
        logger.info(f"No provider prefix found in userName: {username}")
        return event

    default_group = IDP_GROUP_MAPPING.get(provider_name)
    if not default_group:
        logger.warning(f"No default group configured for provider: {provider_name}")
        return event

    try:
        cognito_client.admin_add_user_to_group(
            UserPoolId=USER_POOL_ID,
            Username=username,
            GroupName=default_group,
        )
        logger.info(f"Assigned user {username} to group {default_group}")
    except Exception as e:
        logger.error(f"Failed to assign user {username} to group {default_group}: {e}")

    return event
