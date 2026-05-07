"""
DynamoDB Stream Lambda for Cedar policy synchronization.

This Lambda function is triggered by changes in the authorization DynamoDB table
and automatically generates/updates the corresponding Cedar policies in the AVP Policy Store.
This keeps AVP synchronized with the configuration.
"""

import json
import os
import uuid
from typing import Any, Dict, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

logger = Logger()

# Initialize clients
dynamodb = boto3.resource("dynamodb")
verified_permissions = boto3.client("verifiedpermissions")

# Get environment variables
AUTH_TABLE_NAME = os.environ.get("AUTH_TABLE_NAME")
AVP_POLICY_STORE_ID = os.environ.get("AVP_POLICY_STORE_ID")

# Constants for DynamoDB keys
PREFIX_PERMISSION_SET = "PS#"
PREFIX_USER = "USER#"
PREFIX_GROUP = "GROUP#"
PREFIX_RESOURCE = "RESOURCE#"
PREFIX_COLLECTION = "COLLECTION#"
PREFIX_PERMISSION = "PERMISSION#"
PREFIX_METADATA = "METADATA"
PREFIX_CEDAR = "CEDAR#"

# Action mapping from permission keys to Cedar actions
ACTION_MAPPING = {
    "assets.view": "viewAsset",
    "assets.edit": "editAsset",
    "assets.delete": "deleteAsset",
    "pipelines.view": "viewPipeline",
    "pipelines.edit": "editPipeline",
    "pipelines.delete": "deletePipeline",
    "collections.view": "viewCollection",
    "collections.edit": "editCollection",
    "collections.delete": "deleteCollection",
    "admin.full": "adminAccess",
}


def parse_dynamodb_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a DynamoDB item from the stream record format to a regular Python dict.

    Args:
        item: DynamoDB item in the stream record format

    Returns:
        Parsed item as a regular Python dict
    """
    if not item:
        return {}

    result = {}
    for key, value in item.items():
        # Handle different DynamoDB types
        if "S" in value:
            result[key] = value["S"]
        elif "N" in value:
            result[key] = float(value["N"])
            # Convert to int if it's a whole number
            if result[key].is_integer():
                result[key] = int(result[key])
        elif "BOOL" in value:
            result[key] = value["BOOL"]
        elif "NULL" in value:
            result[key] = None
        elif "M" in value:
            result[key] = parse_dynamodb_item(value["M"])
        elif "L" in value:
            result[key] = [
                (
                    parse_dynamodb_item(item)
                    if "M" in item
                    else item.get("S", item.get("N", item.get("BOOL", None)))
                )
                for item in value["L"]
            ]
        elif "SS" in value:
            result[key] = set(value["SS"])
        elif "NS" in value:
            result[key] = set(map(float, value["NS"]))
        elif "BS" in value:
            result[key] = set(value["BS"])

    return result


def generate_policy_id(item: Dict[str, Any]) -> str:
    """
    Generate a consistent policy ID based on the DynamoDB item.

    Args:
        item: DynamoDB item

    Returns:
        Policy ID string
    """
    pk = item.get("PK", "")
    sk = item.get("SK", "")

    # For permission sets (definitions)
    if pk.startswith(PREFIX_PERMISSION_SET) and sk == PREFIX_METADATA:
        return f"ps-{pk[len(PREFIX_PERMISSION_SET):]}"

    # For permission assignments
    if sk.startswith(PREFIX_PERMISSION):
        principal_id = pk
        resource_id = sk[len(PREFIX_PERMISSION) :]
        return f"perm-{principal_id.replace('#', '-')}-{resource_id.replace('#', '-')}"

    # For permission set assignments
    if sk.startswith("ASSIGNMENT#PS#"):
        principal_id = pk
        permission_set_id = sk[len("ASSIGNMENT#PS#") :]
        return f"assign-{principal_id.replace('#', '-')}-ps-{permission_set_id}"

    # Fallback to a UUID if we can't determine a consistent ID
    return f"policy-{str(uuid.uuid4())}"


def get_principal_entity(principal_id: str) -> Tuple[str, str]:
    """
    Map a principal ID to a Cedar principal entity.

    Args:
        principal_id: Principal ID from DynamoDB (e.g., USER#123, GROUP#456)

    Returns:
        Tuple of (entity_type, entity_id)
    """
    if principal_id.startswith(PREFIX_USER):
        user_id = principal_id[len(PREFIX_USER) :]
        return "User", user_id
    elif principal_id.startswith(PREFIX_GROUP):
        group_id = principal_id[len(PREFIX_GROUP) :]
        return "Group", group_id
    else:
        # Default case
        return "User", principal_id


def get_resource_entity(resource_id: str) -> Tuple[str, str]:
    """
    Map a resource ID to a Cedar resource entity.

    Args:
        resource_id: Resource ID from DynamoDB (e.g., RESOURCE#123, COLLECTION#456)

    Returns:
        Tuple of (entity_type, entity_id)
    """
    if resource_id.startswith(PREFIX_RESOURCE):
        res_id = resource_id[len(PREFIX_RESOURCE) :]
        return "Resource", res_id
    elif resource_id.startswith(PREFIX_COLLECTION):
        coll_id = resource_id[len(PREFIX_COLLECTION) :]
        return "Collection", coll_id
    else:
        # Default case
        return "Resource", resource_id


def map_action(permission_key: str) -> str:
    """
    Map a permission key to a Cedar action entity.

    Args:
        permission_key: Permission key (e.g., assets.view, pipelines.edit)

    Returns:
        Cedar action entity name
    """
    return ACTION_MAPPING.get(permission_key, permission_key.replace(".", ""))


def generate_cedar_policy(item: Dict[str, Any]) -> Optional[str]:
    """
    Generate a Cedar policy string based on the DynamoDB item.

    Args:
        item: DynamoDB item representing a permission set or assignment

    Returns:
        Cedar policy string or None if the item doesn't represent a policy
    """
    pk = item.get("PK", "")
    sk = item.get("SK", "")

    # Handle direct permission assignments (e.g., USER#123 -> PERMISSION#RESOURCE#456)
    if sk.startswith(PREFIX_PERMISSION):
        principal_id = pk
        resource_id = sk[len(PREFIX_PERMISSION) :]
        permissions = item.get("permissions", {})

        # Skip if no permissions defined
        if not permissions:
            logger.warning(f"No permissions defined for {pk} -> {sk}")
            return None

        principal_type, principal_entity_id = get_principal_entity(principal_id)
        resource_type, resource_entity_id = get_resource_entity(resource_id)

        # Determine if this is a permit or forbid policy
        is_deny = permissions.get("deny", False)
        policy_effect = "forbid" if is_deny else "permit"

        # Get the actions from the permissions
        actions = []
        for perm_key, enabled in permissions.items():
            if perm_key != "deny" and enabled:
                cedar_action = map_action(perm_key)
                actions.append(f'MediaLake::Action::"{cedar_action}"')

        # Skip if no actions
        if not actions:
            logger.warning(f"No actions defined for {pk} -> {sk}")
            return None

        # Build the policy
        actions_str = ", ".join(actions)
        policy = f"""{policy_effect} (
    principal == MediaLake::{principal_type}::"{principal_entity_id}",
    action in [{actions_str}],
    resource == MediaLake::{resource_type}::"{resource_entity_id}"
);"""
        return policy

    # Handle permission set assignments (e.g., USER#123 -> ASSIGNMENT#PS#456 or GROUP#123 -> ASSIGNMENT#PS#456)
    elif sk.startswith("ASSIGNMENT#PS#"):
        principal_id = pk
        permission_set_id = sk[len("ASSIGNMENT#PS#") :]

        principal_type, principal_entity_id = get_principal_entity(principal_id)

        # For permission set assignments, we create a template-linked policy
        # that links the principal to the permission set's template policy
        logger.info(
            f"Creating template-linked policy for {principal_type} {principal_entity_id} to PS {permission_set_id}"
        )

        # We don't generate a Cedar policy string here because we'll use the template-linked policy API
        # Return a special marker to indicate this is a template-linked policy
        return f"TEMPLATE_LINKED:{permission_set_id}:{principal_type}:{principal_entity_id}"

    # Handle permission sets (definitions)
    elif pk.startswith(PREFIX_PERMISSION_SET) and sk == PREFIX_METADATA:
        permission_set_id = pk[len(PREFIX_PERMISSION_SET) :]
        item.get("name", "Unnamed Permission Set")
        item.get("description", "")
        permissions = item.get("permissions", {})

        # Skip if no permissions defined
        if not permissions:
            logger.warning(
                f"No permissions defined for permission set {permission_set_id}"
            )
            return None

        # Generate a static policy for this permission set
        # This will be used as a template for assignments
        actions = []
        for perm_key, enabled in permissions.items():
            if perm_key != "deny" and enabled:
                cedar_action = map_action(perm_key)
                actions.append(f'MediaLake::Action::"{cedar_action}"')

        # Skip if no actions
        if not actions:
            logger.warning(f"No actions enabled for permission set {permission_set_id}")
            return None

        # Build the policy
        actions_str = ", ".join(actions)
        policy_effect = "forbid" if permissions.get("deny", False) else "permit"

        policy = f"""{policy_effect} (
    principal,
    action in [{actions_str}],
    resource
);"""

        logger.info(f"Generated template policy for permission set {permission_set_id}")
        return policy

    # Not a policy-related item
    return None


def create_or_update_policy(policy_id: str, policy_string: str) -> bool:
    """
    Create or update a policy in the AVP Policy Store.

    Args:
        policy_id: Policy ID
        policy_string: Cedar policy string or template-linked policy marker

    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if this is a template-linked policy
        if policy_string.startswith("TEMPLATE_LINKED:"):
            # Parse the template-linked policy marker
            parts = policy_string.split(":")
            if len(parts) != 4:
                logger.error(f"Invalid template-linked policy marker: {policy_string}")
                return False

            _, permission_set_id, principal_type, principal_entity_id = parts

            # Check if the template policy exists
            template_policy_id = f"ps-{permission_set_id}"
            try:
                # Try to get the template policy
                verified_permissions.get_policy(
                    policyStoreId=AVP_POLICY_STORE_ID, policyId=template_policy_id
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    logger.error(
                        f"Template policy {template_policy_id} not found for permission set {permission_set_id}"
                    )
                    return False
                else:
                    raise e

            # Create or update the template-linked policy
            try:
                # Check if the policy already exists
                verified_permissions.get_policy(
                    policyStoreId=AVP_POLICY_STORE_ID, policyId=policy_id
                )

                # Policy exists, update it
                logger.info(f"Updating template-linked policy {policy_id}")
                verified_permissions.update_policy(
                    policyStoreId=AVP_POLICY_STORE_ID,
                    policyId=policy_id,
                    definition={
                        "templateLinked": {
                            "policyTemplateId": template_policy_id,
                            "principal": {
                                "entityType": f"MediaLake::{principal_type}",
                                "entityId": principal_entity_id,
                            },
                        }
                    },
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    # Policy doesn't exist, create it
                    logger.info(f"Creating new template-linked policy {policy_id}")
                    verified_permissions.create_policy(
                        policyStoreId=AVP_POLICY_STORE_ID,
                        definition={
                            "templateLinked": {
                                "policyTemplateId": template_policy_id,
                                "principal": {
                                    "entityType": f"MediaLake::{principal_type}",
                                    "entityId": principal_entity_id,
                                },
                            }
                        },
                        policyId=policy_id,
                    )
                else:
                    # Some other error
                    raise e
        else:
            # Regular static policy
            try:
                # Check if the policy already exists
                verified_permissions.get_policy(
                    policyStoreId=AVP_POLICY_STORE_ID, policyId=policy_id
                )

                # Policy exists, update it
                logger.info(f"Updating static policy {policy_id}")
                verified_permissions.update_policy(
                    policyStoreId=AVP_POLICY_STORE_ID,
                    policyId=policy_id,
                    definition={"static": {"statement": policy_string}},
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    # Policy doesn't exist, create it
                    logger.info(f"Creating new static policy {policy_id}")
                    verified_permissions.create_policy(
                        policyStoreId=AVP_POLICY_STORE_ID,
                        definition={"static": {"statement": policy_string}},
                        policyId=policy_id,
                    )
                else:
                    # Some other error
                    raise e

        return True
    except Exception as e:
        logger.error(f"Error creating/updating policy {policy_id}: {str(e)}")
        return False


def delete_policy(policy_id: str) -> bool:
    """
    Delete a policy from the AVP Policy Store.

    Args:
        policy_id: Policy ID

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Deleting policy {policy_id}")
        verified_permissions.delete_policy(
            policyStoreId=AVP_POLICY_STORE_ID, policyId=policy_id
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            # Policy doesn't exist, that's fine
            logger.info(f"Policy {policy_id} not found, nothing to delete")
            return True
        else:
            logger.error(f"Error deleting policy {policy_id}: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"Error deleting policy {policy_id}: {str(e)}")
        return False


def process_insert_or_modify(item: Dict[str, Any]) -> bool:
    """
    Process an INSERT or MODIFY event.

    Args:
        item: DynamoDB item

    Returns:
        True if successful, False otherwise
    """
    # Generate the Cedar policy
    policy_string = generate_cedar_policy(item)
    if not policy_string:
        # Not a policy-related item or no policy could be generated
        return True

    # Generate a consistent policy ID
    policy_id = generate_policy_id(item)

    # Create or update the policy in AVP
    return create_or_update_policy(policy_id, policy_string)


def process_remove(item: Dict[str, Any]) -> bool:
    """
    Process a REMOVE event.

    Args:
        item: DynamoDB item

    Returns:
        True if successful, False otherwise
    """
    # Generate a consistent policy ID
    policy_id = generate_policy_id(item)

    # Delete the policy from AVP
    return delete_policy(policy_id)


@logger.inject_lambda_context
def lambda_handler(event, context):
    """
    Lambda handler for the DynamoDB Stream to AVP Policy Store synchronization.

    Args:
        event: DynamoDB Stream event
        context: Lambda context

    Returns:
        Processing result
    """
    logger.info("Policy Sync Lambda invoked")
    logger.debug(f"Event: {json.dumps(event)}")

    if not AVP_POLICY_STORE_ID:
        error_msg = "AVP_POLICY_STORE_ID environment variable is not set"
        logger.error(error_msg)
        return {"statusCode": 500, "body": json.dumps({"error": error_msg})}

    # Process each record in the DynamoDB Stream event
    success_count = 0
    failure_count = 0

    for record in event.get("Records", []):
        try:
            event_name = record.get("eventName")
            dynamodb_data = record.get("dynamodb", {})

            logger.info(f"Processing {event_name} event")

            # Extract keys and data based on the event type
            if event_name in ["INSERT", "MODIFY"]:
                new_image = parse_dynamodb_item(dynamodb_data.get("NewImage", {}))

                # Process the item
                if process_insert_or_modify(new_image):
                    success_count += 1
                else:
                    failure_count += 1

            elif event_name == "REMOVE":
                old_image = parse_dynamodb_item(dynamodb_data.get("OldImage", {}))

                # Process the item
                if process_remove(old_image):
                    success_count += 1
                else:
                    failure_count += 1

        except Exception as e:
            logger.error(f"Error processing record: {str(e)}")
            failure_count += 1

    logger.info(
        f"Policy synchronization completed: {success_count} succeeded, {failure_count} failed"
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Policy synchronization completed",
                "success_count": success_count,
                "failure_count": failure_count,
            }
        ),
    }
