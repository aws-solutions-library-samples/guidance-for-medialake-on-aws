"""
Debug Configuration for MediaLake Custom Authorizer

This file contains configuration options to enable enhanced logging
for troubleshooting authorization issues.
"""

import os

# Enable debug mode by setting this environment variable
# Set DEBUG_MODE=true in your Lambda environment variables
DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"

# Enable detailed logging for specific components
ENABLE_JWT_DEBUG = os.environ.get("ENABLE_JWT_DEBUG", "false").lower() == "true"
ENABLE_AVP_DEBUG = os.environ.get("ENABLE_AVP_DEBUG", "false").lower() == "true"
ENABLE_API_KEY_DEBUG = os.environ.get("ENABLE_API_KEY_DEBUG", "false").lower() == "true"
ENABLE_PERMISSION_DEBUG = (
    os.environ.get("ENABLE_PERMISSION_DEBUG", "false").lower() == "true"
)

# Log level configuration
LOG_LEVEL = "DEBUG" if DEBUG_MODE else "INFO"


# Debug logging functions
def log_debug_info(logger, component: str, message: str, **kwargs):
    """Log debug information if debug mode is enabled for the component."""
    if DEBUG_MODE:
        logger.info(f"🔍 [{component}] {message}", **kwargs)


def log_environment_config(logger):
    """Log environment configuration for debugging."""
    if DEBUG_MODE:
        logger.info("🔧 Environment Configuration:")
        logger.info(f"   - DEBUG_MODE: {DEBUG_MODE}")
        logger.info(f"   - ENVIRONMENT: {os.environ.get('ENVIRONMENT', 'dev')}")
        logger.info(f"   - POLICY_STORE_ID: {os.environ.get('AVP_POLICY_STORE_ID')}")
        logger.info(f"   - NAMESPACE: {os.environ.get('NAMESPACE')}")
        logger.info(f"   - TOKEN_TYPE: {os.environ.get('TOKEN_TYPE', 'identityToken')}")
        logger.info(
            f"   - COGNITO_USER_POOL_ID: {os.environ.get('COGNITO_USER_POOL_ID')}"
        )
        logger.info(f"   - COGNITO_CLIENT_ID: {os.environ.get('COGNITO_CLIENT_ID')}")
        logger.info(
            f"   - API_KEYS_TABLE_NAME: {os.environ.get('API_KEYS_TABLE_NAME')}"
        )
        logger.info(f"   - AWS_REGION: {os.environ.get('AWS_REGION', 'us-east-1')}")


def log_request_details(logger, event, correlation_id: str):
    """Log detailed request information for debugging."""
    if DEBUG_MODE:
        logger.info(f"🔍 Request Details:", extra={"correlation_id": correlation_id})
        logger.info(
            f"   - Method ARN: {event.get('methodArn', 'Not found')}",
            extra={"correlation_id": correlation_id},
        )
        logger.info(
            f"   - HTTP Method: {event.get('requestContext', {}).get('httpMethod', 'Not found')}",
            extra={"correlation_id": correlation_id},
        )
        logger.info(
            f"   - Resource Path: {event.get('requestContext', {}).get('resourcePath', 'Not found')}",
            extra={"correlation_id": correlation_id},
        )
        logger.info(
            f"   - Stage: {event.get('requestContext', {}).get('stage', 'Not found')}",
            extra={"correlation_id": correlation_id},
        )
        logger.info(
            f"   - Account ID: {event.get('requestContext', {}).get('accountId', 'Not found')}",
            extra={"correlation_id": correlation_id},
        )
        logger.info(
            f"   - API ID: {event.get('requestContext', {}).get('apiId', 'Not found')}",
            extra={"correlation_id": correlation_id},
        )


def log_auth_flow(logger, auth_type: str, correlation_id: str, **kwargs):
    """Log authentication flow information."""
    if DEBUG_MODE:
        logger.info(
            f"🔐 Authentication Flow: {auth_type}",
            extra={"correlation_id": correlation_id},
            **kwargs,
        )


def log_authorization_decision(
    logger, decision: str, reason: str, correlation_id: str, **kwargs
):
    """Log authorization decision details."""
    if DEBUG_MODE:
        logger.info(
            f"⚖️  Authorization Decision: {decision}",
            extra={"correlation_id": correlation_id},
            **kwargs,
        )
        logger.info(
            f"   - Reason: {reason}", extra={"correlation_id": correlation_id}, **kwargs
        )


def log_policy_generation(logger, policy: dict, correlation_id: str):
    """Log policy generation details."""
    if DEBUG_MODE:
        logger.info(f"📋 Policy Generated:", extra={"correlation_id": correlation_id})
        logger.info(
            f"   - Principal ID: {policy.get('principalId')}",
            extra={"correlation_id": correlation_id},
        )
        logger.info(
            f"   - Effect: {policy.get('policyDocument', {}).get('Statement', [{}])[0].get('Effect')}",
            extra={"correlation_id": correlation_id},
        )
        logger.info(
            f"   - Resource: {policy.get('policyDocument', {}).get('Statement', [{}])[0].get('Resource')}",
            extra={"correlation_id": correlation_id},
        )
        logger.info(
            f"   - Context Keys: {list(policy.get('context', {}).keys())}",
            extra={"correlation_id": correlation_id},
        )
