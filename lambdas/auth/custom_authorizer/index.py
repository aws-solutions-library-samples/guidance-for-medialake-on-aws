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
from typing import Dict, Any, List, Tuple, Optional, Union
from jose import jwt, JWTError
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

logger = Logger()

# Initialize clients
dynamodb = boto3.resource('dynamodb')
cognito_idp = boto3.client('cognito-idp')

# Get environment variables
AUTH_TABLE_NAME = os.environ.get('AUTH_TABLE_NAME')
POLICY_STORE_ID = os.environ.get('POLICY_STORE_ID')
NAMESPACE = os.environ.get('NAMESPACE')
TOKEN_TYPE = os.environ.get('TOKEN_TYPE')
DEBUG_MODE = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'
BYPASS_ALL = os.environ.get('BYPASS_ALL', 'false').lower() == 'true'

# Define resource and action types using namespace
RESOURCE_TYPE = f"{NAMESPACE}::Application" if NAMESPACE else "MediaLake::Application"
RESOURCE_ID = NAMESPACE if NAMESPACE else "MediaLake"
ACTION_TYPE = f"{NAMESPACE}::Action" if NAMESPACE else "MediaLake::Action"

# Initialize Verified Permissions client with optional endpoint
if os.environ.get('ENDPOINT'):
    verified_permissions = boto3.client(
        'verifiedpermissions',
        endpoint_url=f"https://{os.environ.get('ENDPOINT')}ford.{os.environ.get('AWS_REGION')}.amazonaws.com"
    )
else:
    verified_permissions = boto3.client('verifiedpermissions')

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
    # Per RFC 6750 section 2.1, "Authorization" header should contain:
    # "Bearer" 1*SP b64token
    # However, match behavior of COGNITO_USER_POOLS authorizer allowing "Bearer" to be optional
    if auth_header.lower().startswith('bearer '):
        return auth_header.split(' ')[1]
    
    return auth_header

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
        
        # Parse the token using base64 decoding similar to the JS implementation
        try:
            # Try using jose library first
            header = jwt.get_unverified_header(token)
            claims = jwt.get_unverified_claims(token)
        except JWTError:
            # Fallback to manual parsing like in JS
            token_parts = token.split('.')
            if len(token_parts) >= 2:
                # Add padding if needed
                payload = token_parts[1]
                payload += '=' * ((4 - len(payload) % 4) % 4)
                decoded_bytes = base64.b64decode(payload)
                claims = json.loads(decoded_bytes.decode('utf-8'))
            else:
                raise Exception("Invalid token format")
        
        logger.debug(f"Token claims: {json.dumps(claims)}")
        
        return claims
    except Exception as e:
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

def get_context_map(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Transform path parameters and query string parameters into the format expected by AVP.
    
    Args:
        event: API Gateway event
        
    Returns:
        Context map for AVP or None if no parameters exist
    """
    path_parameters = event.get('pathParameters', {}) or {}
    query_string_parameters = event.get('queryStringParameters', {}) or {}
    
    # If no parameters, return None
    if not path_parameters and not query_string_parameters:
        return None
    
    # Transform path parameters into smithy format
    path_params_obj = {}
    if path_parameters:
        path_params_obj = {
            "pathParameters": {
                "record": {
                    param_key: {
                        "string": param_value
                    }
                    for param_key, param_value in path_parameters.items()
                }
            }
        }
    
    # Transform query string parameters into smithy format
    query_params_obj = {}
    if query_string_parameters:
        query_params_obj = {
            "queryStringParameters": {
                "record": {
                    param_key: {
                        "string": param_value
                    }
                    for param_key, param_value in query_string_parameters.items()
                }
            }
        }
    
    # Combine both parameter types
    return {
        "contextMap": {
            **query_params_obj,
            **path_params_obj
        }
    }

def check_authorization_with_avp(
    token: str,
    action_id: str,
    event: Dict[str, Any]
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check authorization using Amazon Verified Permissions with token.
    
    Args:
        token: Bearer token
        action_id: Action ID to check
        event: API Gateway event
        
    Returns:
        Tuple of (is_authorized, decision_details)
    """
    if DEBUG_MODE:
        logger.warning(f"DEBUG_MODE enabled: Bypassing AVP authorization check for action {action_id}")
        return True, {"reason": "DEBUG_MODE enabled, authorization check bypassed"}
        
    if not POLICY_STORE_ID:
        logger.warning("POLICY_STORE_ID not set, skipping authorization check")
        return True, {"reason": "POLICY_STORE_ID not set"}
    
    try:
        # Get context map from event
        context = get_context_map(event)
        
        # Prepare input for isAuthorizedWithToken
        input_params = {
            "policyStoreId": POLICY_STORE_ID,
            "action": {
                "actionType": ACTION_TYPE,
                "actionId": action_id
            },
            "resource": {
                "entityType": RESOURCE_TYPE,
                "entityId": RESOURCE_ID
            }
        }
        
        # Add token parameter based on TOKEN_TYPE
        if TOKEN_TYPE:
            input_params[TOKEN_TYPE] = token
        else:
            # Default to bearer token if TOKEN_TYPE not specified
            input_params["bearerToken"] = token
            
        # Add context if available
        if context:
            input_params["context"] = context
        
        logger.info(f"AVP IsAuthorizedWithToken request: {json.dumps(input_params)}")
        
        # Call AVP IsAuthorizedWithToken API
        response = verified_permissions.is_authorized_with_token(**input_params)
        
        decision = response.get('decision', 'DENY')
        is_authorized = decision.upper() == 'ALLOW'
        
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
def handler(event, context):
    """
    Lambda handler for the Custom API Gateway Authorizer.
    
    This implementation:
    1. If BYPASS_ALL is enabled, automatically authorizes all requests
    2. Otherwise:
       a. Extracts bearer token from the Authorization header
       b. Parses the token
       c. Constructs the action ID from HTTP method and resource path
       d. Calls AVP for authorization decision using isAuthorizedWithToken
       e. Returns an IAM policy document allowing or denying access based on the decision
    
    Args:
        event: API Gateway authorizer event
        context: Lambda context
        
    Returns:
        IAM policy document
    """
    logger.info("========== CUSTOM AUTHORIZER INVOKED ==========")
    logger.info(f"Event: {json.dumps(event)}")
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
        context_data = {
            "userId": "bypass_user",
            "bypassMode": "true",
            "resourcePath": resource_path,
            "httpMethod": http_method
        }
        
        policy = generate_policy("bypass_user", "Allow", method_arn, context_data)
        logger.info("Generated ALLOW policy due to BYPASS_ALL mode")
        return policy
    
    try:
        # Extract the bearer token from the Authorization header
        auth_header = event.get('headers', {}).get('Authorization') or event.get('headers', {}).get('authorization')
        auth_token = event.get('authorizationToken')
        
        logger.info(f"Auth header: {auth_header}")
        
        bearer_token = None
        if auth_header:
            bearer_token = extract_token_from_header(auth_header)
        elif auth_token:
            bearer_token = extract_token_from_header(auth_token)
        
        if not bearer_token:
            logger.error("No bearer token found in authorization sources")
            raise Exception("Unauthorized: No bearer token found")
        
        # Parse the token to get claims
        try:
            parsed_token = decode_and_verify_token(bearer_token)
            
            # Extract HTTP method and resource path
            http_method = event.get('requestContext', {}).get('httpMethod', 'GET').lower()
            resource_path = event.get('requestContext', {}).get('resourcePath', '/')
            
            # Construct action ID as in the JS code
            action_id = f"{http_method} {resource_path}"
            
            logger.info(f"Action ID: {action_id}")
            
            # Check authorization with AVP
            is_authorized, auth_response = check_authorization_with_avp(
                bearer_token, action_id, event
            )
            
            # Extract principal ID from token or response
            principal_id = f"{parsed_token.get('iss', '').split('/')[3] if '/' in parsed_token.get('iss', '') else ''}|{parsed_token.get('sub', '')}"
            
            if auth_response.get('principal'):
                principal_entity = auth_response.get('principal')
                principal_id = f"{principal_entity.get('entityType')}::\"{principal_entity.get('entityId')}\""
            
            # Generate policy based on authorization decision
            effect = "Allow" if is_authorized else "Deny"
            
            return {
                "principalId": principal_id,
                "policyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "execute-api:Invoke",
                            "Effect": effect,
                            "Resource": method_arn
                        }
                    ]
                },
                "context": {
                    "actionId": action_id,
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing token: {str(e)}")
            return {
                "principalId": "",
                "policyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "execute-api:Invoke",
                            "Effect": "Deny",
                            "Resource": method_arn
                        }
                    ]
                },
                "context": {}
            }
            
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
            return {
                "principalId": "",
                "policyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "execute-api:Invoke",
                            "Effect": "Deny",
                            "Resource": method_arn
                        }
                    ]
                },
                "context": {
                    "error": str(e)
                }
            }

# For backward compatibility
lambda_handler = handler
