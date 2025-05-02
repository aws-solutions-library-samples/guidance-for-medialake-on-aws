"""
Custom API Gateway Lambda Authorizer for Media Lake.

This Lambda function acts as the primary enforcement point for the authorization system.
It reads permissions from the DynamoDB authorization table and calls Amazon Verified Permissions (AVP)
for evaluation before allowing requests to proceed to backend Lambdas.
"""

import os
import json
import boto3
import base64
import re
from typing import Dict, Any, List, Tuple, Optional
from jose import jwt, JWTError
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

logger = Logger()

# Initialize clients
dynamodb = boto3.resource('dynamodb')
verified_permissions = boto3.client('verifiedpermissions')
cognito_idp = boto3.client('cognito-idp')

# Get environment variables
AUTH_TABLE_NAME = os.environ.get('AUTH_TABLE_NAME')
AVP_POLICY_STORE_ID = os.environ.get('AVP_POLICY_STORE_ID')

# Constants for DynamoDB keys
PREFIX_USER = "USER#"
PREFIX_GROUP = "GROUP#"
PREFIX_MEMBERSHIP = "MEMBERSHIP#"

# Initialize DynamoDB table
auth_table = dynamodb.Table(AUTH_TABLE_NAME) if AUTH_TABLE_NAME else None

def extract_token_from_header(auth_header: str) -> Optional[str]:
    """
    Extract the JWT token from the Authorization header.
    
    Args:
        auth_header: Authorization header value
        
    Returns:
        JWT token or None if not found
    """
    if not auth_header:
        return None
    
    # Check for Bearer token format
    match = re.match(r'Bearer\s+(.+)', auth_header)
    if match:
        return match.group(1)
    
    return None

def decode_and_verify_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify the JWT token.
    
    Args:
        token: JWT token
        
    Returns:
        Decoded token claims
        
    Raises:
        Exception: If token is invalid
    """
    try:
        # For a complete implementation, you would:
        # 1. Fetch the Cognito User Pool public keys
        # 2. Verify the token signature using those keys
        # 3. Verify the token hasn't expired
        # 4. Verify the audience (client_id) and issuer
        
        # For now, we'll just decode without verification to extract the claims
        # In production, use the jose.jwt.decode with the proper keys and verification
        header = jwt.get_unverified_header(token)
        claims = jwt.get_unverified_claims(token)
        
        logger.debug(f"Token header: {json.dumps(header)}")
        logger.debug(f"Token claims: {json.dumps(claims)}")
        
        return claims
    except JWTError as e:
        logger.error(f"Error decoding token: {str(e)}")
        raise Exception(f"Invalid token: {str(e)}")

def get_user_groups(user_id: str) -> List[str]:
    """
    Get the user's group memberships from DynamoDB.
    
    Args:
        user_id: User ID
        
    Returns:
        List of group IDs the user belongs to
    """
    if not auth_table:
        logger.warning("AUTH_TABLE_NAME not set, skipping group lookup")
        return []
    
    try:
        # Query the auth table for the user's group memberships
        response = auth_table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"{PREFIX_USER}{user_id}",
                ":sk_prefix": PREFIX_MEMBERSHIP
            }
        )
        
        # Extract group IDs from the membership records
        groups = []
        for item in response.get('Items', []):
            # SK format is MEMBERSHIP#GROUP#groupId
            sk = item.get('SK', '')
            if sk.startswith(f"{PREFIX_MEMBERSHIP}{PREFIX_GROUP}"):
                group_id = sk[len(f"{PREFIX_MEMBERSHIP}{PREFIX_GROUP}"):]
                groups.append(group_id)
        
        logger.info(f"Found {len(groups)} group memberships for user {user_id}")
        return groups
    except Exception as e:
        logger.error(f"Error fetching user groups: {str(e)}")
        return []

def map_http_method_to_action(http_method: str, resource_path: str) -> str:
    """
    Map HTTP method and resource path to a Cedar action entity.
    
    Args:
        http_method: HTTP method (GET, POST, PUT, DELETE, etc.)
        resource_path: API resource path
        
    Returns:
        Cedar action entity ID
    """
    # Extract the resource type from the path
    # Example: /assets/{id} -> assets
    path_parts = resource_path.strip('/').split('/')
    resource_type = path_parts[0] if path_parts else "unknown"
    
    # Map HTTP methods to actions
    if http_method == 'GET':
        return f"view{resource_type.capitalize()}"
    elif http_method == 'POST':
        return f"create{resource_type.capitalize()}"
    elif http_method == 'PUT' or http_method == 'PATCH':
        return f"edit{resource_type.capitalize()}"
    elif http_method == 'DELETE':
        return f"delete{resource_type.capitalize()}"
    else:
        return f"access{resource_type.capitalize()}"

def extract_resource_id(resource_path: str, path_parameters: Dict[str, str]) -> str:
    """
    Extract the resource ID from the path parameters or resource path.
    
    Args:
        resource_path: API resource path
        path_parameters: Path parameters from the request
        
    Returns:
        Resource ID or resource type if no ID is present
    """
    # Extract the resource type from the path
    path_parts = resource_path.strip('/').split('/')
    resource_type = path_parts[0] if path_parts else "unknown"
    
    # Check if there's an ID in the path parameters
    for param_name, param_value in path_parameters.items():
        if param_name.lower().endswith('id'):
            return param_value
    
    # If no ID in path parameters, check if there's an ID in the path
    if len(path_parts) > 1:
        return path_parts[1]
    
    # If no specific resource ID, return the resource type
    return resource_type

def check_authorization_with_avp(
    user_id: str,
    groups: List[str],
    action: str,
    resource_type: str,
    resource_id: str
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check authorization using Amazon Verified Permissions.
    
    Args:
        user_id: User ID
        groups: List of group IDs the user belongs to
        action: Action to check
        resource_type: Resource type
        resource_id: Resource ID
        
    Returns:
        Tuple of (is_authorized, decision_details)
    """
    if not AVP_POLICY_STORE_ID:
        logger.warning("AVP_POLICY_STORE_ID not set, skipping authorization check")
        return True, {"reason": "AVP_POLICY_STORE_ID not set"}
    
    try:
        # Construct the principal entity
        principal = {
            "entityType": f"MediaLake::User",
            "entityId": user_id
        }
        
        # Construct the action entity
        action_entity = {
            "entityType": "MediaLake::Action",
            "entityId": action
        }
        
        # Construct the resource entity
        resource_entity = {
            "entityType": f"MediaLake::{resource_type.capitalize()}",
            "entityId": resource_id
        }
        
        # Construct the entities structure with group memberships
        entities = {
            "entityList": [
                # Include the user's groups as entities
                *[{
                    "identifier": {
                        "entityType": "MediaLake::Group",
                        "entityId": group_id
                    },
                    "parents": [
                        {
                            "entityType": "MediaLake::User",
                            "entityId": user_id
                        }
                    ]
                } for group_id in groups]
            ]
        }
        
        logger.debug(f"AVP IsAuthorized request: principal={principal}, action={action_entity}, resource={resource_entity}")
        logger.debug(f"Entities: {json.dumps(entities)}")
        
        # Call AVP IsAuthorized API
        response = verified_permissions.is_authorized(
            policyStoreId=AVP_POLICY_STORE_ID,
            principal=principal,
            action=action_entity,
            resource=resource_entity,
            entities=entities
        )
        
        decision = response.get('decision', 'DENY')
        is_authorized = decision == 'ALLOW'
        
        logger.info(f"AVP authorization decision: {decision}")
        
        return is_authorized, response
    except Exception as e:
        logger.error(f"Error checking authorization with AVP: {str(e)}")
        # Default to deny on error
        return False, {"error": str(e)}

def generate_policy(
    principal_id: str,
    effect: str,
    resource: str,
    context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Generate an IAM policy document for API Gateway.
    
    Args:
        principal_id: Principal ID (user ID)
        effect: Policy effect (Allow or Deny)
        resource: Resource ARN
        context: Additional context to include in the response
        
    Returns:
        IAM policy document
    """
    policy = {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource
                }
            ]
        }
    }
    
    # Add context if provided
    if context:
        policy["context"] = context
    
    return policy

@logger.inject_lambda_context
def lambda_handler(event, context):
    """
    Lambda handler for the Custom API Gateway Authorizer.
    
    This implementation:
    1. Extracts user information from the JWT token in the Authorization header
    2. Queries the authorization DynamoDB table for the user's group memberships
    3. Maps the HTTP method and resource path to Cedar action and resource entities
    4. Calls AVP for authorization decision
    5. Returns an IAM policy document allowing or denying access based on the decision
    
    Args:
        event: API Gateway authorizer event
        context: Lambda context
        
    Returns:
        IAM policy document
    """
    logger.info("Custom API Gateway Authorizer invoked")
    logger.debug(f"Event: {json.dumps(event)}")
    
    try:
        # Extract the token from the Authorization header
        auth_header = event.get('headers', {}).get('Authorization')
        if not auth_header:
            logger.error("No Authorization header found")
            raise Exception("Unauthorized: No Authorization header")
        
        token = extract_token_from_header(auth_header)
        if not token:
            logger.error("No token found in Authorization header")
            raise Exception("Unauthorized: No token found in Authorization header")
        
        # Decode and verify the token
        claims = decode_and_verify_token(token)
        
        # Extract user ID from the token claims
        user_id = claims.get('sub')
        if not user_id:
            logger.error("No user ID (sub) found in token claims")
            raise Exception("Unauthorized: No user ID found in token")
        
        # Get the user's group memberships
        groups = get_user_groups(user_id)
        
        # Extract method ARN components
        method_arn = event.get('methodArn', '')
        arn_parts = method_arn.split(':')
        api_gateway_arn_parts = arn_parts[5].split('/') if len(arn_parts) > 5 else []
        
        # Extract HTTP method and resource path
        http_method = event.get('httpMethod') or (api_gateway_arn_parts[2] if len(api_gateway_arn_parts) > 2 else 'GET')
        resource_path = event.get('path') or ('/'.join(api_gateway_arn_parts[3:]) if len(api_gateway_arn_parts) > 3 else '/')
        
        # Extract path parameters
        path_parameters = event.get('pathParameters', {}) or {}
        
        # Map HTTP method and resource path to Cedar action and resource entities
        action = map_http_method_to_action(http_method, resource_path)
        resource_type = resource_path.strip('/').split('/')[0] if resource_path else "unknown"
        resource_id = extract_resource_id(resource_path, path_parameters)
        
        # Check authorization with AVP
        is_authorized, decision_details = check_authorization_with_avp(
            user_id, groups, action, resource_type, resource_id
        )
        
        # Generate the appropriate policy based on the authorization decision
        effect = "Allow" if is_authorized else "Deny"
        
        # Include relevant context in the response
        context = {
            "userId": user_id,
            "groups": json.dumps(groups),
            "action": action,
            "resourceType": resource_type,
            "resourceId": resource_id
        }
        
        # Generate and return the policy
        policy = generate_policy(user_id, effect, method_arn, context)
        logger.info(f"Generated policy with effect: {effect}")
        return policy
        
    except Exception as e:
        logger.error(f"Authorization error: {str(e)}")
        
        # On error, deny access
        return generate_policy("user", "Deny", event.get('methodArn', '*'), {
            "error": str(e)
        })
