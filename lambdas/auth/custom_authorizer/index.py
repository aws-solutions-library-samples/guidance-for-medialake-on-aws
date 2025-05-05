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
DEBUG_MODE = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'
BYPASS_ALL = os.environ.get('BYPASS_ALL', 'false').lower() == 'true'

if DEBUG_MODE:
    logger.warning("DEBUG_MODE is enabled - all requests with valid JWT will be allowed")
    
if BYPASS_ALL:
    logger.warning("⚠️ BYPASS_ALL is enabled - ALL requests will be authorized without any checks ⚠️")

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
    
    logger.info(f"Mapping HTTP method to action: method={http_method}, path={resource_path}, resource_type={resource_type}")
    
    # Map HTTP methods to actions
    action = None
    if http_method == 'GET':
        action = f"view{resource_type.capitalize()}"
    elif http_method == 'POST':
        action = f"create{resource_type.capitalize()}"
    elif http_method == 'PUT' or http_method == 'PATCH':
        action = f"edit{resource_type.capitalize()}"
    elif http_method == 'DELETE':
        action = f"delete{resource_type.capitalize()}"
    else:
        action = f"access{resource_type.capitalize()}"
    
    logger.info(f"Mapped to Cedar action: {action}")
    return action

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
    if DEBUG_MODE:
        logger.warning(f"DEBUG_MODE enabled: Bypassing AVP authorization check for user {user_id}, action {action}, resource {resource_type}/{resource_id}")
        return True, {"reason": "DEBUG_MODE enabled, authorization check bypassed"}
        
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
        
        logger.info(f"User ID: {user_id}")
        logger.info(f"User Groups: {groups}")
        logger.info(f"Action: {action}")
        logger.info(f"Resource Type: {resource_type}")
        logger.info(f"Resource ID: {resource_id}")
        logger.info(f"AVP Policy Store ID: {AVP_POLICY_STORE_ID}")
        
        logger.info(f"AVP IsAuthorized request: principal={json.dumps(principal)}, action={json.dumps(action_entity)}, resource={json.dumps(resource_entity)}")
        logger.info(f"Entities: {json.dumps(entities)}")
        
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
        
        # Log more details about the decision
        if not is_authorized:
            errors = response.get('errors', [])
            if errors:
                logger.error(f"AVP authorization errors: {json.dumps(errors)}")
            
            # Log the decision details
            decision_details = response.get('decisionDetails', {})
            logger.info(f"Decision details: {json.dumps(decision_details)}")
        
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
    1. If BYPASS_ALL is enabled, automatically authorizes all requests
    2. Otherwise:
       a. Extracts user information from the JWT token in the Authorization header
       b. Queries the authorization DynamoDB table for the user's group memberships
       c. Maps the HTTP method and resource path to Cedar action and resource entities
       d. Calls AVP for authorization decision
       e. Returns an IAM policy document allowing or denying access based on the decision
    
    Args:
        event: API Gateway authorizer event
        context: Lambda context
        
    Returns:
        IAM policy document
    """
    logger.info("========== CUSTOM AUTHORIZER INVOKED ==========")
    logger.info(f"Event: {json.dumps(event)}")
    logger.info(f"Context: {context}")
    logger.info(f"Environment: DEBUG_MODE={DEBUG_MODE}, BYPASS_ALL={BYPASS_ALL}")
    logger.info("===============================================")
    
    # Extract method ARN for policy generation
    method_arn = event.get('methodArn', '*')
    
    # If BYPASS_ALL is enabled, automatically authorize all requests
    if BYPASS_ALL:
        logger.warning("⚠️ BYPASS_ALL mode active - Automatically authorizing ALL requests ⚠️")
        
        # Extract HTTP method and resource path for logging purposes only
        arn_parts = method_arn.split(':')
        api_gateway_arn_parts = arn_parts[5].split('/') if len(arn_parts) > 5 else []
        http_method = event.get('httpMethod') or (api_gateway_arn_parts[2] if len(api_gateway_arn_parts) > 2 else 'GET')
        resource_path = event.get('path') or ('/'.join(api_gateway_arn_parts[3:]) if len(api_gateway_arn_parts) > 3 else '/')
        
        logger.info(f"Auto-authorizing request: {http_method} {resource_path}")
        
        # Generate an Allow policy with minimal context
        context = {
            "userId": "bypass_user",
            "groups": "[]",
            "bypassMode": "true",
            "resourcePath": resource_path,
            "httpMethod": http_method
        }
        
        policy = generate_policy("bypass_user", "Allow", method_arn, context)
        logger.info("Generated ALLOW policy due to BYPASS_ALL mode")
        return policy
    
    try:
        # Extract the token from either the Authorization header or authorizationToken field
        auth_header = event.get('headers', {}).get('Authorization')
        auth_token = event.get('authorizationToken')
        
        logger.info(f"Auth header: {auth_header}")
        logger.info(f"Auth token: {auth_token}")
        
        if auth_header:
            token = extract_token_from_header(auth_header)
        elif auth_token:
            token = extract_token_from_header(auth_token)
        else:
            if BYPASS_ALL:
                logger.warning("No authorization token found, but BYPASS_ALL is enabled - proceeding with authorization")
                token = "bypass_token"
            else:
                logger.error("No Authorization header or authorizationToken found")
                raise Exception("Unauthorized: No Authorization token found")
        
        if not token and not BYPASS_ALL:
            logger.error("No token extracted from authorization sources")
            raise Exception("Unauthorized: No token found in authorization sources")
        
        # Decode and verify the token (unless using bypass token)
        if token == "bypass_token" and BYPASS_ALL:
            claims = {"sub": "bypass_user"}
            user_id = "bypass_user"
            logger.warning("Using bypass user ID due to BYPASS_ALL mode")
        else:
            # Decode and verify the token
            claims = decode_and_verify_token(token)
            
            # Extract user ID from the token claims
            user_id = claims.get('sub')
            if not user_id and not BYPASS_ALL:
                logger.error("No user ID (sub) found in token claims")
                raise Exception("Unauthorized: No user ID found in token")
            elif not user_id and BYPASS_ALL:
                user_id = "bypass_user"
                logger.warning("No user ID found in token, using bypass user due to BYPASS_ALL mode")
        
        # Get the user's group memberships
        groups = get_user_groups(user_id)
        
        # Extract method ARN components
        arn_parts = method_arn.split(':')
        api_gateway_arn_parts = arn_parts[5].split('/') if len(arn_parts) > 5 else []
        
        # Extract HTTP method and resource path
        http_method = event.get('httpMethod') or (api_gateway_arn_parts[2] if len(api_gateway_arn_parts) > 2 else 'GET')
        resource_path = event.get('path') or ('/'.join(api_gateway_arn_parts[3:]) if len(api_gateway_arn_parts) > 3 else '/')
        
        logger.info(f"HTTP Method: {http_method}")
        logger.info(f"Resource Path: {resource_path}")
        
        # Extract path parameters
        path_parameters = event.get('pathParameters', {}) or {}
        logger.info(f"Path Parameters: {json.dumps(path_parameters)}")
        
        # Map HTTP method and resource path to Cedar action and resource entities
        action = map_http_method_to_action(http_method, resource_path)
        resource_type = resource_path.strip('/').split('/')[0] if resource_path else "unknown"
        resource_id = extract_resource_id(resource_path, path_parameters)
        
        logger.info(f"Mapped Cedar Action: {action}")
        logger.info(f"Resource Type: {resource_type}")
        logger.info(f"Resource ID: {resource_id}")
        
        # If BYPASS_ALL is enabled, always authorize
        if BYPASS_ALL:
            is_authorized = True
            decision_details = {"reason": "BYPASS_ALL mode enabled - all requests are authorized"}
            logger.warning("⚠️ BYPASS_ALL mode enabled - automatically authorizing request ⚠️")
        else:
            # Check authorization with AVP (will be bypassed if DEBUG_MODE is enabled)
            is_authorized, decision_details = check_authorization_with_avp(
                user_id, groups, action, resource_type, resource_id
            )
        
        # Generate the appropriate policy based on the authorization decision
        effect = "Allow" if is_authorized else "Deny"
        
        # Log the authorization decision
        logger.info(f"Authorization decision: {effect}, reason: {json.dumps(decision_details)}")
        
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
        
        # On error, deny access unless BYPASS_ALL is enabled
        if BYPASS_ALL:
            logger.warning(f"⚠️ Error occurred but BYPASS_ALL is enabled - authorizing anyway: {str(e)} ⚠️")
            return generate_policy("bypass_user", "Allow", method_arn, {
                "bypassMode": "true",
                "error": str(e)
            })
        else:
            return generate_policy("user", "Deny", method_arn, {
                "error": str(e)
            })
