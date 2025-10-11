"""
Custom API Gateway Lambda Authorizer for Media Lake.

This Lambda function acts as the primary enforcement point for the authorization system.
It validates JWT tokens and calls Amazon Verified Permissions (AVP) for evaluation
before allowing requests to proceed to backend Lambdas.
"""

import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from jose import jwt
from lambda_middleware import is_lambda_warmer_event

# Initialize observability tools with proper namespace
logger = Logger()
metrics = Metrics(namespace="MediaLake/Authorization")
tracer = Tracer()

# Get environment variables
POLICY_STORE_ID = os.environ.get("AVP_POLICY_STORE_ID")
NAMESPACE = os.environ.get("NAMESPACE")
TOKEN_TYPE = os.environ.get("TOKEN_TYPE", "identityToken")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID")
DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
API_KEYS_TABLE_NAME = os.environ.get("API_KEYS_TABLE_NAME")

# Define resource and action types using namespace
RESOURCE_TYPE = f"{NAMESPACE}::Application" if NAMESPACE else "MediaLake::Application"
RESOURCE_ID = NAMESPACE if NAMESPACE else "MediaLake"
ACTION_TYPE = f"{NAMESPACE}::Action" if NAMESPACE else "MediaLake::Action"

# Initialize AWS clients outside handler for reuse
import boto3

# Get the AWS region from environment variable or default to us-east-1
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Initialize Verified Permissions client with explicit region
if os.environ.get("ENDPOINT"):
    verified_permissions = boto3.client(
        "verifiedpermissions",
        region_name=AWS_REGION,
        endpoint_url=f"https://{os.environ.get('ENDPOINT')}.{AWS_REGION}.amazonaws.com",
    )
else:
    verified_permissions = boto3.client("verifiedpermissions", region_name=AWS_REGION)

# Initialize DynamoDB and Secrets Manager clients
dynamodb = boto3.client("dynamodb", region_name=AWS_REGION)
secretsmanager = boto3.client("secretsmanager", region_name=AWS_REGION)

# Safety checks for production environments
if ENVIRONMENT == "prod" and DEBUG_MODE:
    logger.warning("⚠️ DEBUG_MODE is enabled in production - this is a security risk!")

if DEBUG_MODE:
    logger.warning(
        "DEBUG_MODE is enabled - all requests with valid JWT will be allowed"
    )

# JWKS cache with TTL - optimized for Lambda reuse
jwks_cache = {"keys": None, "expiry": 0}

# JWT token verification cache - optimized for Lambda reuse
token_verification_cache = {}

# API key validation cache - optimized for Lambda reuse
api_key_validation_cache = {}


@tracer.capture_method
def extract_api_key_from_header(headers: Dict[str, str]) -> Optional[str]:
    """
    Extract the API key from the X-API-Key header.

    Args:
        headers: Request headers

    Returns:
        API key value or None if not found
    """
    # Check for X-API-Key header (case-insensitive)
    api_key = headers.get("X-API-Key") or headers.get("x-api-key")
    if api_key:
        logger.info("Found API key in X-API-Key header")
        return api_key
    return None


@tracer.capture_method
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
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ")[1]

    return auth_header


@tracer.capture_method
def get_cognito_jwks() -> Dict[str, Any]:
    """
    Fetch the JSON Web Key Set (JWKS) from Cognito user pool.
    Uses caching to avoid frequent requests to Cognito.

    Returns:
        JWKS dictionary containing the public keys
    """
    current_time = time.time()

    # Return cached JWKS if still valid
    if jwks_cache["keys"] and jwks_cache["expiry"] > current_time:
        metrics.add_metric(name="fetch.jwks.cache_hit", unit=MetricUnit.Count, value=1)
        logger.debug("Using cached JWKS")
        return jwks_cache["keys"]

    metrics.add_metric(name="fetch.jwks.cache_miss", unit=MetricUnit.Count, value=1)
    logger.info("Fetching fresh JWKS from Cognito")

    start_time = time.time()

    try:
        # Construct the JWKS URL from the Cognito user pool ID
        if not COGNITO_USER_POOL_ID:
            raise Exception("COGNITO_USER_POOL_ID environment variable not set")

        region = COGNITO_USER_POOL_ID.split("_")[0]
        jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"

        logger.info(f"Fetching JWKS from: {jwks_url}")
        req = urllib.request.Request(jwks_url)

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                response_data = response.read()
                jwks = json.loads(response_data.decode("utf-8"))

                # Cache the JWKS for 1 hour
                jwks_cache["keys"] = jwks
                jwks_cache["expiry"] = current_time + 3600  # 1 hour TTL

                # Record successful fetch metrics
                fetch_time = (time.time() - start_time) * 1000
                metrics.add_metric(
                    name="fetch.jwks.latency",
                    unit=MetricUnit.Milliseconds,
                    value=fetch_time,
                )
                metrics.add_metric(
                    name="fetch.jwks.success", unit=MetricUnit.Count, value=1
                )

                logger.info(
                    f"Successfully fetched JWKS with {len(jwks.get('keys', []))} keys in {fetch_time:.2f}ms"
                )
                return jwks

        except urllib.error.HTTPError as http_err:
            metrics.add_metric(name="fetch.jwks.error", unit=MetricUnit.Count, value=1)
            raise Exception(f"Failed to fetch JWKS: HTTP {http_err.code}")
        except urllib.error.URLError as url_err:
            metrics.add_metric(name="fetch.jwks.error", unit=MetricUnit.Count, value=1)
            raise Exception(f"Failed to fetch JWKS: {url_err.reason}")

    except Exception as e:
        logger.error(f"Error fetching JWKS: {str(e)}")
        metrics.add_metric(name="fetch.jwks.error", unit=MetricUnit.Count, value=1)

        # If we have cached keys, use them even if expired
        if jwks_cache["keys"]:
            logger.warning("Using expired JWKS cache due to fetch error")
            metrics.add_metric(
                name="fetch.jwks.expired_cache_used", unit=MetricUnit.Count, value=1
            )
            return jwks_cache["keys"]

        raise Exception(f"Failed to fetch JWKS: {str(e)}")


@tracer.capture_method
def decode_and_verify_token(token: str, correlation_id: str) -> Dict[str, Any]:
    """
    Decode and verify the JWT token, including signature verification.

    Args:
        token: JWT token
        correlation_id: Request correlation ID for tracing

    Returns:
        Decoded token claims

    Raises:
        Exception: If token is invalid
    """
    start_time = time.time()

    # Check if we have this token in cache
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    cache_entry = token_verification_cache.get(token_hash)

    # If we have a valid cache entry that hasn't expired
    if cache_entry and cache_entry["expiry"] > time.time():
        metrics.add_metric(
            name="validate.token.cache_hit", unit=MetricUnit.Count, value=1
        )
        logger.debug(
            "Using cached token verification result",
            extra={"correlation_id": correlation_id},
        )
        return cache_entry["claims"]

    metrics.add_metric(name="validate.token.cache_miss", unit=MetricUnit.Count, value=1)
    logger.info("Verifying token signature", extra={"correlation_id": correlation_id})

    try:
        # Get unverified header and claims first for debugging
        header = jwt.get_unverified_header(token)
        unverified_claims = jwt.get_unverified_claims(token)

        # Log token details for debugging (production-safe)
        if ENVIRONMENT != "prod":
            logger.info(
                f"Token header: {json.dumps(header)}",
                extra={"correlation_id": correlation_id},
            )
            logger.info(
                f"Token audience (aud): {unverified_claims.get('aud')}",
                extra={"correlation_id": correlation_id},
            )
            logger.info(
                f"Token client_id: {unverified_claims.get('client_id')}",
                extra={"correlation_id": correlation_id},
            )
            logger.info(
                f"Token issuer (iss): {unverified_claims.get('iss')}",
                extra={"correlation_id": correlation_id},
            )
            logger.info(
                f"Expected client ID: {COGNITO_CLIENT_ID}",
                extra={"correlation_id": correlation_id},
            )

        if not header or "kid" not in header:
            metrics.add_metric(
                name="validate.token.invalid_header", unit=MetricUnit.Count, value=1
            )
            raise Exception("Invalid token header or missing key ID (kid)")

        kid = header["kid"]

        # Get the JWKS from Cognito
        jwks = get_cognito_jwks()

        # Find the key with matching kid
        key = None
        for jwk_key in jwks.get("keys", []):
            if jwk_key.get("kid") == kid:
                key = jwk_key
                break

        if not key:
            metrics.add_metric(
                name="validate.token.key_not_found", unit=MetricUnit.Count, value=1
            )
            raise Exception(f"No matching key found for kid: {kid}")

        logger.info(
            f"Using JWK with kid: {key.get('kid')}",
            extra={"correlation_id": correlation_id},
        )

        # Configure JWT decode options
        jwt_options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_iat": True,
            "verify_aud": False,  # We'll handle audience validation manually
            "verify_at_hash": False,  # Skip at_hash validation (we only have ID token, not access token)
        }

        # If we have a specific client ID to validate against, enable audience verification
        jwt_audience = None
        if COGNITO_CLIENT_ID:
            jwt_options["verify_aud"] = True
            jwt_audience = COGNITO_CLIENT_ID
            logger.debug(
                f"Will verify audience against: {jwt_audience}",
                extra={"correlation_id": correlation_id},
            )
        else:
            logger.info(
                "COGNITO_CLIENT_ID not set, skipping audience verification",
                extra={"correlation_id": correlation_id},
            )

        # Verify the token signature and decode claims
        claims = jwt.decode(
            token,
            key,  # Pass the JWK directly
            algorithms=["RS256"],
            audience=jwt_audience,  # Specify expected audience if configured
            options=jwt_options,
        )

        logger.info(
            "Token signature verified successfully",
            extra={"correlation_id": correlation_id},
        )
        metrics.add_metric(
            name="validate.token.signature_verified", unit=MetricUnit.Count, value=1
        )

        # Validate required claims
        if not claims.get("sub"):
            metrics.add_metric(
                name="validate.token.missing_sub", unit=MetricUnit.Count, value=1
            )
            raise Exception("Token missing required 'sub' claim")

        # Validate token issuer if configured
        if COGNITO_USER_POOL_ID:
            expected_issuer = f"https://cognito-idp.{COGNITO_USER_POOL_ID.split('_')[0]}.amazonaws.com/{COGNITO_USER_POOL_ID}"
            if claims.get("iss") != expected_issuer:
                metrics.add_metric(
                    name="validate.token.invalid_issuer", unit=MetricUnit.Count, value=1
                )
                logger.error(
                    f"Issuer mismatch: expected '{expected_issuer}', got '{claims.get('iss')}'",
                    extra={"correlation_id": correlation_id},
                )
                raise Exception(
                    f"Invalid token issuer: expected '{expected_issuer}', got '{claims.get('iss')}'"
                )

        # Cache the verified token with expiry time
        exp_time = claims.get("exp", int(time.time() + 300))
        token_verification_cache[token_hash] = {"claims": claims, "expiry": exp_time}

        # Clean up expired cache entries periodically (1% chance per request)
        if hash(token_hash) % 100 == 0:
            current_time = time.time()
            expired_keys = [
                k
                for k, v in token_verification_cache.items()
                if v["expiry"] < current_time
            ]
            for k in expired_keys:
                token_verification_cache.pop(k, None)

        # Record validation time
        validation_time = (time.time() - start_time) * 1000
        metrics.add_metric(
            name="validate.token.latency",
            unit=MetricUnit.Milliseconds,
            value=validation_time,
        )
        metrics.add_metric(
            name="validate.token.success", unit=MetricUnit.Count, value=1
        )

        return claims

    except jwt.ExpiredSignatureError:
        metrics.add_metric(
            name="validate.token.expired", unit=MetricUnit.Count, value=1
        )
        logger.warning("Token has expired", extra={"correlation_id": correlation_id})
        raise Exception("Token has expired")

    except jwt.JWTClaimsError as e:
        metrics.add_metric(
            name="validate.token.invalid_claims", unit=MetricUnit.Count, value=1
        )
        logger.error(
            f"Invalid token claims: {str(e)}", extra={"correlation_id": correlation_id}
        )
        raise Exception(f"Invalid token claims: {str(e)}")

    except jwt.JWTError as e:
        metrics.add_metric(
            name="validate.token.jwt_error", unit=MetricUnit.Count, value=1
        )
        logger.error(
            f"JWT validation error: {str(e)}", extra={"correlation_id": correlation_id}
        )
        raise Exception(f"Token validation failed: {str(e)}")

    except Exception as e:
        metrics.add_metric(name="validate.token.error", unit=MetricUnit.Count, value=1)
        logger.error(
            f"Error decoding token: {str(e)}", extra={"correlation_id": correlation_id}
        )
        raise Exception(f"Invalid token: {str(e)}")


@tracer.capture_method
def extract_principal_id(
    parsed_token: Dict[str, Any], auth_response: Dict[str, Any]
) -> str:
    """
    Extract principal ID from token claims or AVP response.

    Args:
        parsed_token: Decoded JWT token claims
        auth_response: AVP authorization response

    Returns:
        Principal ID for the user
    """
    # First, try to get principal from AVP response
    if auth_response.get("principal"):
        principal_entity = auth_response.get("principal")
        entity_type = principal_entity.get("entityType", "User")
        entity_id = principal_entity.get("entityId", "")
        if entity_id:
            logger.info(
                f"Using principal from AVP response: {entity_type}::{entity_id}"
            )
            metrics.add_metric(
                name="extract.principal.from_avp", unit=MetricUnit.Count, value=1
            )
            return f"{entity_type}::{entity_id}"

    # Fall back to extracting from token claims
    user_id = parsed_token.get("sub")
    if not user_id:
        logger.error("No 'sub' claim found in token")
        metrics.add_metric(
            name="extract.principal.missing_sub", unit=MetricUnit.Count, value=1
        )
        raise Exception("Invalid token: missing subject")

    # For Cognito tokens, use the sub claim directly
    username = parsed_token.get("cognito:username", user_id)

    logger.info(f"Extracted user ID: {user_id}, username: {username}")
    metrics.add_metric(
        name="extract.principal.from_token", unit=MetricUnit.Count, value=1
    )

    # Return in format expected by your system
    return f"User::{user_id}"


@tracer.capture_method
def get_context_map(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Transform path parameters and query string parameters into the format expected by AVP.

    Args:
        event: API Gateway event

    Returns:
        Context map for AVP or None if no parameters exist
    """
    path_parameters = event.get("pathParameters", {}) or {}
    query_string_parameters = event.get("queryStringParameters", {}) or {}

    # If no parameters, return None
    if not path_parameters and not query_string_parameters:
        return None

    # Transform path parameters into smithy format
    path_params_obj = {}
    if path_parameters:
        path_params_obj = {
            "pathParameters": {
                "record": {
                    param_key: {"string": param_value}
                    for param_key, param_value in path_parameters.items()
                }
            }
        }
        metrics.add_metric(
            name="context.path_parameters",
            unit=MetricUnit.Count,
            value=len(path_parameters),
        )

    # Transform query string parameters into smithy format
    query_params_obj = {}
    if query_string_parameters:
        query_params_obj = {
            "queryStringParameters": {
                "record": {
                    param_key: {"string": param_value}
                    for param_key, param_value in query_string_parameters.items()
                }
            }
        }
        metrics.add_metric(
            name="context.query_parameters",
            unit=MetricUnit.Count,
            value=len(query_string_parameters),
        )

    # Combine both parameter types
    return {"contextMap": {**query_params_obj, **path_params_obj}}


@tracer.capture_method
def check_authorization_with_avp(
    token: str, action_id: str, event: Dict[str, Any], correlation_id: str
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check authorization using Amazon Verified Permissions with token.

    Args:
        token: Bearer token
        action_id: Action ID to check
        event: API Gateway event
        correlation_id: Request correlation ID for tracing

    Returns:
        Tuple of (is_authorized, decision_details)
    """
    start_time = time.time()

    if DEBUG_MODE:
        logger.warning(
            f"DEBUG_MODE enabled: Bypassing AVP authorization check for action {action_id}",
            extra={"correlation_id": correlation_id},
        )
        metrics.add_metric(
            name="authorize.request.debug_bypass", unit=MetricUnit.Count, value=1
        )
        return True, {"reason": "DEBUG_MODE enabled, authorization check bypassed"}

    if not POLICY_STORE_ID:
        logger.warning(
            "POLICY_STORE_ID not set, skipping authorization check",
            extra={"correlation_id": correlation_id},
        )
        metrics.add_metric(
            name="authorize.request.missing_policy_store",
            unit=MetricUnit.Count,
            value=1,
        )
        return True, {"reason": "POLICY_STORE_ID not set"}

    try:
        # Get context map from event
        context = get_context_map(event)

        # Prepare input for isAuthorizedWithToken
        input_params = {
            "policyStoreId": POLICY_STORE_ID,
            "action": {"actionType": ACTION_TYPE, "actionId": action_id},
            "resource": {"entityType": RESOURCE_TYPE, "entityId": RESOURCE_ID},
        }

        # Add token parameter based on TOKEN_TYPE
        if TOKEN_TYPE in ["identityToken", "accessToken"]:
            input_params[TOKEN_TYPE] = token
        else:
            # Default to identityToken for Cognito JWT tokens
            input_params["identityToken"] = token

        # Add context if available
        if context:
            input_params["context"] = context

        # Redact token for logging in production
        log_params = input_params.copy()
        if ENVIRONMENT == "prod":
            if TOKEN_TYPE in log_params:
                log_params[TOKEN_TYPE] = "***REDACTED***"
            if "identityToken" in log_params:
                log_params["identityToken"] = "***REDACTED***"

        logger.info(
            f"AVP IsAuthorizedWithToken request: {json.dumps(log_params)}",
            extra={"correlation_id": correlation_id},
        )

        # Call AVP IsAuthorizedWithToken API
        avp_start_time = time.time()
        response = verified_permissions.is_authorized_with_token(**input_params)
        avp_duration = (time.time() - avp_start_time) * 1000

        metrics.add_metric(
            name="authorize.avp.latency",
            unit=MetricUnit.Milliseconds,
            value=avp_duration,
        )

        decision = response.get("decision", "DENY")
        is_authorized = decision.upper() == "ALLOW"

        logger.info(
            f"AVP authorization decision: {decision}",
            extra={"correlation_id": correlation_id},
        )

        # Record metrics based on decision
        if is_authorized:
            metrics.add_metric(
                name="authorize.request.allow", unit=MetricUnit.Count, value=1
            )
        else:
            metrics.add_metric(
                name="authorize.request.deny", unit=MetricUnit.Count, value=1
            )

            errors = response.get("errors", [])
            if errors:
                logger.error(
                    f"AVP authorization errors: {json.dumps(errors)}",
                    extra={"correlation_id": correlation_id},
                )
                metrics.add_metric(
                    name="authorize.request.errors",
                    unit=MetricUnit.Count,
                    value=len(errors),
                )

            # Log the decision details
            decision_details = response.get("decisionDetails", {})
            logger.info(
                f"Decision details: {json.dumps(decision_details)}",
                extra={"correlation_id": correlation_id},
            )

        # Record total authorization time
        total_duration = (time.time() - start_time) * 1000
        metrics.add_metric(
            name="authorize.request.latency",
            unit=MetricUnit.Milliseconds,
            value=total_duration,
        )

        return is_authorized, response

    except Exception as e:
        logger.error(
            f"Error checking authorization with AVP: {str(e)}",
            extra={"correlation_id": correlation_id},
        )
        metrics.add_metric(
            name="authorize.request.error", unit=MetricUnit.Count, value=1
        )
        # Default to deny on error
        return False, {"error": str(e)}


@tracer.capture_method
def generate_policy(
    principal_id: str, effect: str, resource: str, context: Dict[str, Any] = None
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
                {"Action": "execute-api:Invoke", "Effect": effect, "Resource": resource}
            ],
        },
    }

    # Add context if provided
    if context:
        policy["context"] = context

    # Record policy generation metrics
    metrics.add_metric(
        name=f"generate.policy.{effect.lower()}", unit=MetricUnit.Count, value=1
    )
    logger.info(f"Generated {effect} policy for principal {principal_id}")

    return policy


@tracer.capture_method
def validate_api_key(api_key_value: str, correlation_id: str) -> Dict[str, Any]:
    """
    Validate an API key by looking it up in DynamoDB and verifying against Secrets Manager.

    Args:
        api_key_value: The API key value to validate
        correlation_id: Request correlation ID for tracing

    Returns:
        API key item from DynamoDB if valid

    Raises:
        Exception: If API key is invalid or disabled
    """
    start_time = time.time()

    # Check cache first
    cache_key = hashlib.sha256(api_key_value.encode()).hexdigest()
    cache_entry = api_key_validation_cache.get(cache_key)

    if cache_entry and cache_entry["expiry"] > time.time():
        metrics.add_metric(
            name="validate.api_key.cache_hit", unit=MetricUnit.Count, value=1
        )
        logger.debug(
            "Using cached API key validation result",
            extra={"correlation_id": correlation_id},
        )
        return cache_entry["api_key_item"]

    metrics.add_metric(
        name="validate.api_key.cache_miss", unit=MetricUnit.Count, value=1
    )
    logger.info("Validating API key", extra={"correlation_id": correlation_id})

    try:
        # Validate that API_KEYS_TABLE_NAME is set
        if not API_KEYS_TABLE_NAME:
            raise Exception("API_KEYS_TABLE_NAME environment variable not set")

        # Extract the API key ID from the value (assuming format: id_secretValue)
        # Split by first underscore to get ID
        parts = api_key_value.split("_", 1)
        if len(parts) != 2:
            raise Exception("Invalid API key format")

        api_key_id = parts[0]
        provided_secret = parts[1]

        # Look up API key in DynamoDB with error handling
        try:
            response = dynamodb.get_item(
                TableName=API_KEYS_TABLE_NAME, Key={"id": {"S": api_key_id}}
            )
        except Exception as db_err:
            metrics.add_metric(
                name="validate.api_key.dynamodb_error", unit=MetricUnit.Count, value=1
            )
            logger.error(
                f"Error querying DynamoDB for API key {api_key_id}: {str(db_err)}",
                extra={"correlation_id": correlation_id},
            )
            raise Exception(f"Database error while validating API key: {str(db_err)}")

        if "Item" not in response:
            metrics.add_metric(
                name="validate.api_key.not_found", unit=MetricUnit.Count, value=1
            )
            raise Exception("API key not found")

        # Convert DynamoDB item to regular dict with robust error handling
        try:
            item = response["Item"]

            # Extract required fields with error handling
            api_key_item = {
                "id": item.get("id", {}).get("S", ""),
                "name": item.get("name", {}).get("S", ""),
                "description": item.get("description", {}).get("S", ""),
                "secretArn": item.get("secretArn", {}).get("S", ""),
                "isEnabled": item.get("isEnabled", {}).get("BOOL", False),
                "createdAt": item.get("createdAt", {}).get("S", ""),
                "updatedAt": item.get("updatedAt", {}).get("S", ""),
            }

            # Validate that required fields are present and not empty
            required_fields = ["id", "name", "secretArn"]
            for field in required_fields:
                if not api_key_item[field]:
                    raise Exception(
                        f"Required field '{field}' is missing or empty in API key item"
                    )

            # Check if permissions field exists and parse it safely
            if "permissions" in item and "S" in item["permissions"]:
                try:
                    permissions_str = item["permissions"]["S"]
                    if permissions_str:
                        api_key_item["permissions"] = json.loads(permissions_str)
                    else:
                        api_key_item["permissions"] = {}
                except (json.JSONDecodeError, TypeError) as json_err:
                    logger.warning(
                        f"Failed to parse permissions JSON for API key {api_key_item['id']}: {str(json_err)}",
                        extra={"correlation_id": correlation_id},
                    )
                    api_key_item["permissions"] = {}
            else:
                api_key_item["permissions"] = {}

        except (KeyError, TypeError, AttributeError) as conversion_err:
            metrics.add_metric(
                name="validate.api_key.conversion_error", unit=MetricUnit.Count, value=1
            )
            logger.error(
                f"Error converting DynamoDB item to API key object: {str(conversion_err)}",
                extra={"correlation_id": correlation_id},
            )
            raise Exception(
                f"Malformed API key data in database: {str(conversion_err)}"
            )

        # Check if API key is enabled
        if not api_key_item["isEnabled"]:
            metrics.add_metric(
                name="validate.api_key.disabled", unit=MetricUnit.Count, value=1
            )
            raise Exception("API key is disabled")

        # Retrieve the actual secret from Secrets Manager with error handling
        try:
            secret_response = secretsmanager.get_secret_value(
                SecretId=api_key_item["secretArn"]
            )

            if "SecretString" not in secret_response:
                raise Exception("Secret value not found in Secrets Manager response")

            stored_secret = secret_response["SecretString"]

            if not stored_secret:
                raise Exception("Empty secret value retrieved from Secrets Manager")

        except Exception as secret_err:
            metrics.add_metric(
                name="validate.api_key.secrets_manager_error",
                unit=MetricUnit.Count,
                value=1,
            )
            logger.error(
                f"Error retrieving secret for API key {api_key_item['id']}: {str(secret_err)}",
                extra={"correlation_id": correlation_id},
            )
            raise Exception(f"Error retrieving API key secret: {str(secret_err)}")

        # Compare provided secret with stored secret
        try:
            if not secrets.compare_digest(provided_secret, stored_secret):
                metrics.add_metric(
                    name="validate.api_key.invalid_secret",
                    unit=MetricUnit.Count,
                    value=1,
                )
                raise Exception("Invalid API key")
        except Exception as compare_err:
            metrics.add_metric(
                name="validate.api_key.secret_comparison_error",
                unit=MetricUnit.Count,
                value=1,
            )
            logger.error(
                f"Error comparing secrets for API key {api_key_item['id']}: {str(compare_err)}",
                extra={"correlation_id": correlation_id},
            )
            raise Exception("Error validating API key secret")

        # Cache successful validation (5 minutes TTL)
        api_key_validation_cache[cache_key] = {
            "api_key_item": api_key_item,
            "expiry": time.time() + 300,
        }

        # Clean up expired cache entries periodically (1% chance per request)
        if hash(cache_key) % 100 == 0:
            current_time = time.time()
            expired_keys = [
                k
                for k, v in api_key_validation_cache.items()
                if v["expiry"] < current_time
            ]
            for k in expired_keys:
                api_key_validation_cache.pop(k, None)

        # Record validation time
        validation_time = (time.time() - start_time) * 1000
        metrics.add_metric(
            name="validate.api_key.latency",
            unit=MetricUnit.Milliseconds,
            value=validation_time,
        )
        metrics.add_metric(
            name="validate.api_key.success", unit=MetricUnit.Count, value=1
        )

        logger.info(
            f"API key validated successfully: {api_key_item['name']}",
            extra={"correlation_id": correlation_id},
        )
        return api_key_item

    except Exception as e:
        metrics.add_metric(
            name="validate.api_key.error", unit=MetricUnit.Count, value=1
        )
        logger.error(
            f"Error validating API key: {str(e)}",
            extra={"correlation_id": correlation_id},
        )
        raise Exception(f"Invalid API key: {str(e)}")


@tracer.capture_method
def create_permission_mapping() -> Dict[str, Dict[str, str]]:
    """
    Create a mapping between HTTP methods/resource paths and required permissions.
    Updated to match the new nested permission structure.

    Returns:
        Dictionary mapping resource patterns to required permissions
    """
    return {
        # Assets endpoints
        "get /api/assets": "assets:view",
        "post /api/assets/upload": "assets:upload",
        "delete /api/assets/{id}": "assets:delete",
        "put /api/assets/{id}": "assets:edit",
        "get /api/assets/{id}": "assets:view",
        "post /api/assets/{id}/rename": "assets:edit",
        "get /api/assets/{id}/transcript": "assets:view",
        "get /api/assets/{id}/related_versions": "assets:view",
        "post /api/assets/generate_presigned_url": "assets:upload",
        # Download endpoints
        "get /api/download/bulk": "assets:download",
        "post /api/download/bulk": "assets:download",
        "get /api/download/bulk/{jobId}": "assets:download",
        "put /api/download/bulk/{jobId}/downloaded": "assets:download",
        "delete /api/download/bulk/{jobId}": "assets:download",
        "get /api/download/bulk/user": "assets:download",
        # Collections endpoints
        "get /api/collections": "collections:view",
        "post /api/collections": "collections:create",
        "put /api/collections/{id}": "collections:edit",
        "delete /api/collections/{id}": "collections:delete",
        # Connectors endpoints - now using settings.connectors
        "get /api/connectors": "settings.connectors:view",
        "post /api/connectors": "settings.connectors:create",
        "put /api/connectors/{id}": "settings.connectors:edit",
        "delete /api/connectors/{id}": "settings.connectors:delete",
        "post /api/connectors/{id}/sync": "settings.connectors:edit",
        "get /api/connectors/s3": "settings.connectors:view",
        "post /api/connectors/s3": "settings.connectors:create",
        "get /api/connectors/s3/buckets": "settings.connectors:view",
        "get /api/connectors/s3/explorer/{id}": "settings.connectors:view",
        # Environments endpoints
        "get /api/environments": "environments:view",
        "post /api/environments": "environments:create",
        "put /api/environments/{id}": "environments:edit",
        "delete /api/environments/{id}": "environments:delete",
        # Groups endpoints - now using settings.users (groups are part of user management)
        "get /api/groups": "settings.users:view",
        "post /api/groups": "settings.users:create",
        "put /api/groups/{id}": "settings.users:edit",
        "delete /api/groups/{id}": "settings.users:delete",
        "post /api/groups/add_group_members": "settings.users:edit",
        "post /api/groups/remove_group_member": "settings.users:edit",
        # Integrations endpoints - now using settings.integrations
        "get /api/integrations": "settings.integrations:view",
        "post /api/integrations": "settings.integrations:create",
        "put /api/integrations/{id}": "settings.integrations:edit",
        "delete /api/integrations/{id}": "settings.integrations:delete",
        # Nodes endpoints
        "get /api/nodes": "nodes:view",
        "get /api/nodes/{id}": "nodes:view",
        # Permissions endpoints - now using settings.permissions
        "get /api/permissions": "settings.permissions:view",
        "post /api/permissions": "settings.permissions:create",
        "put /api/permissions/{id}": "settings.permissions:edit",
        "delete /api/permissions/{id}": "settings.permissions:delete",
        "get /api/authorization/permission_sets": "settings.permissions:view",
        "post /api/authorization/permission_sets": "settings.permissions:create",
        "put /api/authorization/permission_sets/{id}": "settings.permissions:edit",
        "delete /api/authorization/permission_sets/{id}": "settings.permissions:delete",
        # Assignment endpoints
        "post /api/authorization/assignments/assign_ps_to_user": "settings.permissions:edit",
        "post /api/authorization/assignments/assign_ps_to_group": "settings.permissions:edit",
        "get /api/authorization/assignments/list_user_assignments": "settings.permissions:view",
        "get /api/authorization/assignments/list_group_assignments": "settings.permissions:view",
        "delete /api/authorization/assignments/remove_user_assignment": "settings.permissions:edit",
        "delete /api/authorization/assignments/remove_group_assignment": "settings.permissions:edit",
        # Pipelines endpoints
        "get /api/pipelines": "pipelines:view",
        "post /api/pipelines": "pipelines:create",
        "put /api/pipelines/{id}": "pipelines:edit",
        "delete /api/pipelines/{id}": "pipelines:delete",
        "get /api/pipelines/{id}": "pipelines:view",
        "get /api/pipelines/executions": "pipelinesExecutions:view",
        "get /api/pipelines/executions/{id}": "pipelinesExecutions:view",
        "post /api/pipelines/executions/{id}/retry": "pipelinesExecutions:retry",
        # Reviews endpoints
        "get /api/reviews/{id}": "reviews:view",
        "put /api/reviews/{id}": "reviews:edit",
        "delete /api/reviews/{id}": "reviews:delete",
        "get /api/reviews/{id}/annotations": "reviews:view",
        "put /api/reviews/{id}/annotations": "reviews:edit",
        "delete /api/reviews/{id}/annotations": "reviews:delete",
        "get /api/reviews/{id}/status": "reviews:view",
        "post /api/reviews/{id}/status": "reviews:edit",
        # Roles endpoints - now using settings.permissions
        "get /api/roles": "settings.permissions:view",
        "post /api/roles": "settings.permissions:create",
        "put /api/roles/{id}": "settings.permissions:edit",
        "delete /api/roles/{id}": "settings.permissions:delete",
        "get /api/settings/roles": "settings.permissions:view",
        "post /api/settings/roles": "settings.permissions:create",
        "put /api/settings/roles/{id}": "settings.permissions:edit",
        "delete /api/settings/roles/{id}": "settings.permissions:delete",
        # Search endpoints
        "get /api/search": "search:view",
        "get /api/search/fields": "search:view",
        # Settings endpoints - now using nested structure
        "get /api/settings/api_keys": "settings.api-keys:view",  # pragma: allowlist secret
        "post /api/settings/api_keys": "settings.api-keys:create",  # pragma: allowlist secret
        "put /api/settings/api_keys/{id}": "settings.api-keys:edit",
        "delete /api/settings/api_keys/{id}": "settings.api-keys:delete",
        "get /api/settings/system": "settings.system:view",
        "get /api/settings/system/search": "settings.system:view",
        "post /api/settings/system/search": "settings.system:edit",
        "put /api/settings/system/search": "settings.system:edit",
        "get /api/settings/userprofile": "settings.users:view",
        "get /api/settings/users": "settings.users:view",
        "put /api/settings/users/{id}": "settings.users:edit",
        "delete /api/settings/users/{id}": "settings.users:delete",
        "get /api/settings/users/{id}": "settings.users:view",
        # Storage endpoints
        "get /api/storage/s3/buckets": "storage:view",
        "get /api/storage/s3/object": "storage:view",
        # AWS endpoints - now using settings.regions
        "get /api/aws/get_regions": "settings.regions:view",
    }


@tracer.capture_method
def normalize_resource_path(
    resource_path: str, path_parameters: Dict[str, str] = None
) -> str:
    """
    Normalize a resource path by replacing path parameters with placeholders.

    Args:
        resource_path: The original resource path (e.g., "/api/assets/123")
        path_parameters: Dictionary of path parameters (e.g., {"id": "123"})

    Returns:
        Normalized path with placeholders (e.g., "/api/assets/{id}")
    """
    if not path_parameters:
        return resource_path

    normalized_path = resource_path

    # Replace path parameter values with placeholders
    for param_name, param_value in path_parameters.items():
        # Replace the actual value with the parameter placeholder
        normalized_path = normalized_path.replace(
            f"/{param_value}", f"/{{{param_name}}}"
        )

    return normalized_path


@tracer.capture_method
def get_required_permission(
    http_method: str, resource_path: str, path_parameters: Dict[str, str] = None
) -> Optional[str]:
    """
    Get the required permission for a given HTTP method and resource path.

    Args:
        http_method: HTTP method (e.g., "get", "post")
        resource_path: Resource path (e.g., "/api/assets/123")
        path_parameters: Dictionary of path parameters

    Returns:
        Required permission string or None if no specific permission is required
    """
    permission_mapping = create_permission_mapping()

    # Normalize the resource path
    normalized_path = normalize_resource_path(resource_path, path_parameters)

    # Create the action key
    action_key = f"{http_method.lower()} {normalized_path}"

    # Try exact match first
    required_permission = permission_mapping.get(action_key)

    if required_permission:
        logger.debug(
            f"Found exact permission match: {action_key} -> {required_permission}"
        )
        return required_permission

    # Try pattern matching for common cases
    # Handle cases where the path might have different parameter names
    for pattern, permission in permission_mapping.items():
        if pattern.startswith(f"{http_method.lower()} "):
            pattern_path = pattern[len(f"{http_method.lower()} ") :]
            if _paths_match(normalized_path, pattern_path):
                logger.debug(
                    f"Found pattern permission match: {pattern} -> {permission}"
                )
                return permission

    logger.debug(f"No specific permission found for: {action_key}")
    return None


@tracer.capture_method
def _paths_match(path1: str, path2: str) -> bool:
    """
    Check if two paths match, considering parameter placeholders.

    Args:
        path1: First path to compare
        path2: Second path to compare

    Returns:
        True if paths match, False otherwise
    """
    # Split paths into segments
    segments1 = [s for s in path1.split("/") if s]
    segments2 = [s for s in path2.split("/") if s]

    # Must have same number of segments
    if len(segments1) != len(segments2):
        return False

    # Compare each segment
    for seg1, seg2 in zip(segments1, segments2):
        # If either segment is a parameter placeholder, it matches
        if seg1.startswith("{") and seg1.endswith("}"):
            continue
        if seg2.startswith("{") and seg2.endswith("}"):
            continue
        # Otherwise, segments must match exactly
        if seg1 != seg2:
            return False

    return True


@tracer.capture_method
def validate_api_key_permissions(
    api_key_item: Dict[str, Any], required_permission: str, correlation_id: str
) -> bool:
    """
    Validate that an API key has the required permission for the requested action.

    Args:
        api_key_item: API key item from DynamoDB
        required_permission: The permission required for this action
        correlation_id: Request correlation ID for tracing

    Returns:
        True if API key has the required permission, False otherwise
    """
    start_time = time.time()

    try:
        # Get permissions from API key
        permissions = api_key_item.get("permissions", {})

        # Add debug logging
        logger.info(
            f"API key permissions type: {type(permissions)}, value: {permissions}"
        )

        # Ensure permissions is a dictionary
        if not isinstance(permissions, dict):
            logger.warning(
                f"API key permissions is not a dictionary, type: {type(permissions)}"
            )
            permissions = {}

        if not permissions:
            logger.warning(
                f"API key {api_key_item['id']} has no permissions defined",
                extra={"correlation_id": correlation_id},
            )
            metrics.add_metric(
                name="validate.api_key_permissions.no_permissions",
                unit=MetricUnit.Count,
                value=1,
            )
            return False

        # Check if the required permission exists and is enabled
        permission_granted = permissions.get(required_permission, False)

        if permission_granted:
            logger.info(
                f"API key {api_key_item['id']} has required permission: {required_permission}",
                extra={"correlation_id": correlation_id},
            )
            metrics.add_metric(
                name="validate.api_key_permissions.granted",
                unit=MetricUnit.Count,
                value=1,
            )
        else:
            logger.warning(
                f"API key {api_key_item['id']} lacks required permission: {required_permission}. "
                f"Available permissions: {list(permissions.keys())}",
                extra={"correlation_id": correlation_id},
            )
            metrics.add_metric(
                name="validate.api_key_permissions.denied",
                unit=MetricUnit.Count,
                value=1,
            )

        # Record validation time
        validation_time = (time.time() - start_time) * 1000
        metrics.add_metric(
            name="validate.api_key_permissions.latency",
            unit=MetricUnit.Milliseconds,
            value=validation_time,
        )

        return permission_granted

    except Exception as e:
        logger.error(
            f"Error validating API key permissions: {str(e)}",
            extra={"correlation_id": correlation_id},
        )
        metrics.add_metric(
            name="validate.api_key_permissions.error", unit=MetricUnit.Count, value=1
        )
        return False


@tracer.capture_method
def generate_api_key_context(api_key_item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate synthetic claims object for API key authentication.

    Args:
        api_key_item: API key item from DynamoDB

    Returns:
        Synthetic claims object that mimics JWT claims
    """
    # Get permissions from API key item
    permissions = api_key_item.get("permissions", {})

    # Add debug logging to understand the permissions structure
    logger.info(f"Permissions type: {type(permissions)}, value: {permissions}")

    # Ensure permissions is a dictionary
    if not isinstance(permissions, dict):
        logger.warning(f"Permissions is not a dictionary, type: {type(permissions)}")
        permissions = {}

    # Transform nested permission structure to flat format expected by CASL
    custom_permissions = []

    # Handle nested permission structure like:
    # {
    #   "settings": {
    #     "api-keys": {"create": True, "view": True, "edit": True, "delete": True}
    #   }
    # }
    def flatten_permissions(obj, prefix=""):
        try:
            if not isinstance(obj, dict):
                logger.warning(
                    f"flatten_permissions called with non-dict object: {type(obj)}"
                )
                return

            for key, value in obj.items():
                if isinstance(value, dict):
                    # Check if this is a leaf node with boolean values (actions)
                    if all(isinstance(v, bool) for v in value.values()):
                        # This is an action level - add permissions for each True action
                        for action, enabled in value.items():
                            if enabled:
                                permission_key = f"{prefix}.{key}" if prefix else key
                                custom_permissions.append(f"{permission_key}:{action}")
                    else:
                        # This is a nested resource - recurse
                        new_prefix = f"{prefix}.{key}" if prefix else key
                        flatten_permissions(value, new_prefix)
                elif isinstance(value, bool) and value:
                    # Direct boolean permission
                    permission_key = f"{prefix}.{key}" if prefix else key
                    custom_permissions.append(
                        f"{permission_key}:view"
                    )  # Default to view
        except Exception as e:
            logger.error(f"Error in flatten_permissions: {str(e)}")
            logger.error(f"Object: {obj}, prefix: {prefix}")

    if permissions:
        flatten_permissions(permissions)

    logger.info(
        f"Generated custom permissions for API key {api_key_item['id']}: {custom_permissions}"
    )

    # Create synthetic claims that backend Lambdas expect
    try:
        claims = {
            "sub": f"ApiKey::{api_key_item.get('id', 'unknown')}",
            "username": api_key_item.get("name", "Unknown"),
            "cognito:username": api_key_item.get("name", "Unknown"),
            "auth_type": "api_key",
            "api_key_id": api_key_item.get("id", "unknown"),
            "permissions": permissions,  # Keep original permissions for reference
            "customPermissions": custom_permissions,  # Add flattened permissions for CASL
        }
    except Exception as claims_err:
        logger.error(f"Error creating claims: {str(claims_err)}")
        # Fall back to basic claims
        claims = {
            "sub": "ApiKey::unknown",
            "username": "Unknown",
            "cognito:username": "Unknown",
            "auth_type": "api_key",
            "api_key_id": "unknown",
            "permissions": {},
            "customPermissions": [],
        }

    logger.info(f"Generated claims type: {type(claims)}")
    logger.info(f"Generated claims keys: {list(claims.keys())}")
    logger.info(f"Generated claims sub: {claims.get('sub', 'Not found')}")

    return claims


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for the Custom API Gateway Authorizer.

    This implementation:
    1. Extracts bearer token from the Authorization header
    2. Validates and verifies the JWT token including signature
    3. Constructs the action ID from HTTP method and resource path
    4. Calls AVP for authorization decision using isAuthorizedWithToken
    5. Returns an IAM policy document allowing or denying access based on the decision

    Args:
        event: API Gateway authorizer event
        context: Lambda context

    Returns:
        IAM policy document
    """
    # Lambda warmer short-circuit
    if is_lambda_warmer_event(event):
        return {"warmed": True}
    start_time = time.time()
    correlation_id = str(context.aws_request_id)

    logger.info(
        "========== CUSTOM AUTHORIZER INVOKED ==========",
        extra={"correlation_id": correlation_id},
    )

    # In production, don't log the full event as it may contain sensitive information
    if ENVIRONMENT == "prod":
        logger.info(
            "Event received (details redacted in production)",
            extra={"correlation_id": correlation_id},
        )
    else:
        logger.info(
            f"Event: {json.dumps(event)}", extra={"correlation_id": correlation_id}
        )

    logger.info(
        f"Environment: DEBUG_MODE={DEBUG_MODE}, ENVIRONMENT={ENVIRONMENT}",
        extra={"correlation_id": correlation_id},
    )
    logger.info(
        "===============================================",
        extra={"correlation_id": correlation_id},
    )

    # Extract method ARN for policy generation
    method_arn = event.get("methodArn", "*")

    # Record request metrics
    metrics.add_metric(name="request.total", unit=MetricUnit.Count, value=1)

    try:
        # First, check for API key authentication
        headers = event.get("headers", {})

        # Log all headers for debugging (production-safe)
        if ENVIRONMENT != "prod":
            logger.info(
                f"All request headers: {json.dumps(headers)}",
                extra={"correlation_id": correlation_id},
            )
        else:
            # In production, only log header names (not values)
            header_names = list(headers.keys()) if headers else []
            logger.info(
                f"Request header names: {header_names}",
                extra={"correlation_id": correlation_id},
            )

        api_key = extract_api_key_from_header(headers)

        # Then check for JWT token
        auth_header = headers.get("Authorization") or headers.get("authorization")
        auth_token = event.get("authorizationToken")

        # In production, don't log sensitive information
        if ENVIRONMENT != "prod":
            logger.info(
                f"Auth header present: {auth_header is not None}, API key present: {api_key is not None}",
                extra={"correlation_id": correlation_id},
            )

        # Determine authentication method - JWT takes precedence if both are present
        bearer_token = None
        if auth_header:
            bearer_token = extract_token_from_header(auth_header)
            if bearer_token:
                metrics.add_metric(
                    name="extract.token.from_header", unit=MetricUnit.Count, value=1
                )
        elif auth_token:
            bearer_token = extract_token_from_header(auth_token)
            if bearer_token:
                metrics.add_metric(
                    name="extract.token.from_token", unit=MetricUnit.Count, value=1
                )

        # If we have a JWT token, use JWT authentication flow
        if bearer_token:
            logger.info(
                "Using JWT authentication",
                extra={"correlation_id": correlation_id},
            )
            # Existing JWT authentication flow continues below
        elif api_key:
            logger.info(
                "Using API key authentication",
                extra={"correlation_id": correlation_id},
            )
            metrics.add_metric(name="auth.type.api_key", unit=MetricUnit.Count, value=1)

            # Validate API key
            try:
                api_key_item = validate_api_key(api_key, correlation_id)

                # Generate synthetic claims for API key
                try:
                    parsed_token = generate_api_key_context(api_key_item)
                    # Verify that parsed_token is a dictionary
                    if not isinstance(parsed_token, dict):
                        logger.warning(
                            f"generate_api_key_context returned non-dict: {type(parsed_token)}"
                        )
                        raise Exception("generate_api_key_context returned non-dict")
                except Exception as context_err:
                    logger.error(
                        f"Error generating API key context: {str(context_err)}",
                        extra={"correlation_id": correlation_id},
                    )
                    # Fall back to basic claims if context generation fails
                    parsed_token = {
                        "sub": f"ApiKey::{api_key_item.get('id', 'unknown')}",
                        "username": api_key_item.get("name", "Unknown"),
                        "cognito:username": api_key_item.get("name", "Unknown"),
                        "auth_type": "api_key",
                        "api_key_id": api_key_item.get("id", "unknown"),
                        "permissions": {},
                        "customPermissions": [],
                    }

                # Extract HTTP method and resource path
                http_method = (
                    event.get("requestContext", {}).get("httpMethod", "GET").lower()
                )
                resource_path = event.get("requestContext", {}).get("resourcePath", "/")

                # Construct action ID
                action_id = f"{http_method} {resource_path}"

                logger.info(
                    f"Action ID: {action_id}", extra={"correlation_id": correlation_id}
                )

                # For API keys, we'll use a simplified authorization approach
                # Check if API key has permissions or use default permissions
                is_authorized = (
                    True  # Default to allow for API keys with valid authentication
                )
                auth_response = {
                    "decision": "ALLOW",
                    "reason": "API key authenticated",
                    "principal": {
                        "entityType": "ApiKey",
                        "entityId": api_key_item.get("id", "unknown"),
                    },
                }

                # Enhanced API key permission validation
                if DEBUG_MODE:
                    # In DEBUG_MODE, bypass permission validation if API key is present
                    logger.warning(
                        f"DEBUG_MODE enabled: Bypassing API key permission validation for action {action_id}",
                        extra={"correlation_id": correlation_id},
                    )
                    metrics.add_metric(
                        name="authorize.api_key.debug_bypass",
                        unit=MetricUnit.Count,
                        value=1,
                    )
                    is_authorized = True
                    auth_response = {
                        "decision": "ALLOW",
                        "reason": "DEBUG_MODE enabled, API key permission validation bypassed",
                        "principal": {
                            "entityType": "ApiKey",
                            "entityId": api_key_item.get("id", "unknown"),
                        },
                    }
                else:
                    # Get path parameters for proper resource path normalization
                    path_parameters = event.get("pathParameters", {}) or {}

                    # Get the required permission for this action
                    required_permission = get_required_permission(
                        http_method, resource_path, path_parameters
                    )

                    if required_permission:
                        # Validate that the API key has the required permission
                        is_authorized = validate_api_key_permissions(
                            api_key_item, required_permission, correlation_id
                        )

                        if is_authorized:
                            auth_response["reason"] = (
                                f"API key has required permission: {required_permission}"
                            )
                        else:
                            auth_response = {
                                "decision": "DENY",
                                "reason": f"API key lacks required permission: {required_permission}",
                                "principal": {
                                    "entityType": "ApiKey",
                                    "entityId": api_key_item.get("id", "unknown"),
                                },
                            }

                        logger.info(
                            f"Permission check for API key {api_key_item.get('id', 'unknown')}: "
                            f"required={required_permission}, granted={is_authorized}",
                            extra={"correlation_id": correlation_id},
                        )
                    else:
                        # No specific permission required - check if API key has any permissions
                        permissions = api_key_item.get("permissions", {})

                        # Add debug logging for permissions
                        logger.info(
                            f"API key permissions for unspecified action: {permissions}"
                        )
                        logger.info(f"Permissions type: {type(permissions)}")

                        if not permissions:
                            logger.warning(
                                f"API key {api_key_item.get('id', 'unknown')} has no permissions for unspecified action: {action_id}",
                                extra={"correlation_id": correlation_id},
                            )
                            is_authorized = False
                            auth_response = {
                                "decision": "DENY",
                                "reason": "API key has no permissions defined",
                                "principal": {
                                    "entityType": "ApiKey",
                                    "entityId": api_key_item.get("id", "unknown"),
                                },
                            }
                        else:
                            logger.info(
                                f"No specific permission required for {action_id}, API key has general permissions",
                                extra={"correlation_id": correlation_id},
                            )
                            auth_response["reason"] = (
                                "API key has general permissions for unspecified action"
                            )

                # Extract principal ID
                try:
                    if isinstance(parsed_token, dict):
                        principal_id = parsed_token.get(
                            "sub", f"ApiKey::{api_key_item.get('id', 'unknown')}"
                        )
                    else:
                        logger.warning(
                            f"parsed_token is not a dictionary, type: {type(parsed_token)}"
                        )
                        principal_id = f"ApiKey::{api_key_item.get('id', 'unknown')}"
                except Exception as principal_err:
                    logger.error(
                        f"Error extracting principal ID: {str(principal_err)}",
                        extra={"correlation_id": correlation_id},
                    )
                    principal_id = f"ApiKey::{api_key_item.get('id', 'unknown')}"

                logger.info(
                    f"Using principal ID: {principal_id}",
                    extra={"correlation_id": correlation_id},
                )

                # Generate policy based on authorization decision
                effect = "Allow" if is_authorized else "Deny"

                # Include all claims in the context for backend Lambdas
                try:
                    if isinstance(parsed_token, dict):
                        # Convert claims to proper JSON-serializable values
                        context_claims = {}
                        for k, v in parsed_token.items():
                            if isinstance(v, (dict, list)):
                                # Convert complex objects to JSON strings
                                context_claims[k] = json.dumps(v, default=str)
                            elif isinstance(v, (str, int, float, bool)) or v is None:
                                # Keep primitive types as-is
                                context_claims[k] = v
                            else:
                                # Convert everything else to string
                                context_claims[k] = str(v)
                    else:
                        logger.warning(
                            f"parsed_token is not a dictionary, type: {type(parsed_token)}"
                        )
                        context_claims = {
                            "actionId": action_id,
                            "userId": principal_id,
                            "username": "Unknown",
                            "sub": "Unknown",
                            "requestId": correlation_id,
                        }
                except Exception as claims_err:
                    logger.error(
                        f"Error converting claims to strings: {str(claims_err)}",
                        extra={"correlation_id": correlation_id},
                    )
                    # Fall back to basic context if claims conversion fails
                    context_claims = {
                        "actionId": action_id,
                        "userId": principal_id,
                        "username": "Unknown",
                        "sub": "Unknown",
                        "requestId": correlation_id,
                    }

                # Add debug logging for parsed_token
                logger.info(f"parsed_token type: {type(parsed_token)}")
                logger.info(
                    f"parsed_token keys: {list(parsed_token.keys()) if isinstance(parsed_token, dict) else 'Not a dict'}"
                )
                logger.info(
                    f"parsed_token username: {parsed_token.get('username', 'Not found') if isinstance(parsed_token, dict) else 'Not a dict'}"
                )
                logger.info(
                    f"parsed_token sub: {parsed_token.get('sub', 'Not found') if isinstance(parsed_token, dict) else 'Not a dict'}"
                )

                # Add debug logging for context_claims
                logger.info(f"context_claims type: {type(context_claims)}")
                logger.info(f"context_claims content: {context_claims}")

                # Create context with error handling - simplified approach
                try:
                    context = {
                        "actionId": str(action_id),
                        "userId": str(principal_id),
                        "username": (
                            str(parsed_token.get("username", ""))
                            if isinstance(parsed_token, dict)
                            else "Unknown"
                        ),
                        "sub": (
                            str(parsed_token.get("sub", ""))
                            if isinstance(parsed_token, dict)
                            else "Unknown"
                        ),
                        "requestId": str(correlation_id),
                        "claims": json.dumps(
                            context_claims, default=str
                        ),  # Stringify claims for context with fallback
                    }
                except Exception as context_err:
                    logger.error(
                        f"Error creating context: {str(context_err)}",
                        extra={"correlation_id": correlation_id},
                    )
                    # Fall back to basic context if creation fails
                    context = {
                        "actionId": str(action_id),
                        "userId": str(principal_id),
                        "username": "Unknown",
                        "sub": "Unknown",
                        "requestId": str(correlation_id),
                        "claims": "{}",
                    }

                # Validate that all context values are strings (API Gateway requirement)
                validated_context = {}
                for key, value in context.items():
                    try:
                        validated_context[key] = str(value)
                    except Exception as str_err:
                        logger.warning(
                            f"Error converting context value {key} to string: {str_err}"
                        )
                        validated_context[key] = "Error converting value"

                policy = {
                    "principalId": str(principal_id),
                    "policyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Action": "execute-api:Invoke",
                                "Effect": str(effect),
                                "Resource": str(method_arn),
                            }
                        ],
                    },
                    "context": validated_context,
                }

                # Record execution time and result
                execution_time = (time.time() - start_time) * 1000
                metrics.add_metric(
                    name="request.latency",
                    unit=MetricUnit.Milliseconds,
                    value=execution_time,
                )
                metrics.add_metric(
                    name=f"request.result_{effect.lower()}",
                    unit=MetricUnit.Count,
                    value=1,
                )

                # Log the policy response before returning
                logger.info(
                    f"Returning API key policy response: {json.dumps(policy, default=str)}",
                    extra={"correlation_id": correlation_id},
                )

                # Additional debug logging for policy structure
                logger.info(f"Policy principalId type: {type(policy['principalId'])}")
                logger.info(
                    f"Policy context types: {[(k, type(v)) for k, v in policy['context'].items()]}"
                )
                logger.info(
                    f"Policy context values: {[(k, repr(v)) for k, v in policy['context'].items()]}"
                )

                return policy

            except Exception as e:
                logger.error(
                    f"Error processing API key: {str(e)}",
                    extra={"correlation_id": correlation_id},
                )
                metrics.add_metric(
                    name="request.api_key_error", unit=MetricUnit.Count, value=1
                )
                raise Exception(f"Unauthorized: {str(e)}")
        else:
            logger.error(
                "No authentication credentials found",
                extra={"correlation_id": correlation_id},
            )
            metrics.add_metric(
                name="request.missing_credentials", unit=MetricUnit.Count, value=1
            )
            raise Exception("Unauthorized: No authentication credentials found")

        # Continue with JWT authentication flow if we have a bearer token
        if not bearer_token:
            # This shouldn't happen as we check above, but just in case
            raise Exception("Unauthorized: No bearer token found")

        # Parse and verify the token
        try:
            parsed_token = decode_and_verify_token(bearer_token, correlation_id)

            # Extract HTTP method and resource path
            http_method = (
                event.get("requestContext", {}).get("httpMethod", "GET").lower()
            )
            resource_path = event.get("requestContext", {}).get("resourcePath", "/")

            # Construct action ID
            action_id = f"{http_method} {resource_path}"

            logger.info(
                f"Action ID: {action_id}", extra={"correlation_id": correlation_id}
            )

            # Check authorization with AVP
            is_authorized, auth_response = check_authorization_with_avp(
                bearer_token, action_id, event, correlation_id
            )

            # Extract principal ID
            principal_id = extract_principal_id(parsed_token, auth_response)

            logger.info(
                f"Using principal ID: {principal_id}",
                extra={"correlation_id": correlation_id},
            )

            # Generate policy based on authorization decision
            effect = "Allow" if is_authorized else "Deny"

            # Create context with error handling
            try:
                context = {
                    "actionId": str(action_id),
                    "userId": str(principal_id),
                    "username": str(parsed_token.get("cognito:username", "")),
                    "sub": str(parsed_token.get("sub", "")),
                    "requestId": str(correlation_id),
                    "claims": json.dumps(
                        parsed_token, default=str
                    ),  # Stringify claims for context with fallback
                }
            except Exception as context_err:
                logger.error(
                    f"Error creating context: {str(context_err)}",
                    extra={"correlation_id": correlation_id},
                )
                # Fall back to basic context if creation fails
                context = {
                    "actionId": str(action_id),
                    "userId": str(principal_id),
                    "username": "Unknown",
                    "sub": "Unknown",
                    "requestId": str(correlation_id),
                    "claims": "{}",
                }

            policy = {
                "principalId": str(principal_id),
                "policyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "execute-api:Invoke",
                            "Effect": str(effect),
                            "Resource": str(method_arn),
                        }
                    ],
                },
                "context": context,
            }

            # Record execution time and result
            execution_time = (time.time() - start_time) * 1000
            metrics.add_metric(
                name="request.latency",
                unit=MetricUnit.Milliseconds,
                value=execution_time,
            )
            metrics.add_metric(
                name=f"request.result_{effect.lower()}", unit=MetricUnit.Count, value=1
            )

            # Log the policy response before returning
            logger.info(
                f"Returning JWT policy response: {json.dumps(policy, default=str)}",
                extra={"correlation_id": correlation_id},
            )

            return policy

        except Exception as e:
            logger.error(
                f"Error processing token: {str(e)}",
                extra={"correlation_id": correlation_id},
            )
            metrics.add_metric(
                name="request.token_error", unit=MetricUnit.Count, value=1
            )

            policy = {
                "principalId": "denied_user",
                "policyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "execute-api:Invoke",
                            "Effect": "Deny",
                            "Resource": str(method_arn),
                        }
                    ],
                },
                "context": {"error": str(e), "requestId": str(correlation_id)},
            }

            # Record execution time
            execution_time = (time.time() - start_time) * 1000
            metrics.add_metric(
                name="request.latency",
                unit=MetricUnit.Milliseconds,
                value=execution_time,
            )
            metrics.add_metric(
                name="request.result_deny", unit=MetricUnit.Count, value=1
            )

            # Log the error policy response before returning
            logger.info(
                f"Returning JWT error policy response: {json.dumps(policy, default=str)}",
                extra={"correlation_id": correlation_id},
            )

            return policy

    except Exception as e:
        logger.error(
            f"Authorization error: {str(e)}", extra={"correlation_id": correlation_id}
        )
        metrics.add_metric(name="request.error", unit=MetricUnit.Count, value=1)

        policy = {
            "principalId": "error_user",
            "policyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": "execute-api:Invoke",
                        "Effect": "Deny",
                        "Resource": str(method_arn),
                    }
                ],
            },
            "context": {"error": str(e), "requestId": str(correlation_id)},
        }

        # Record execution time
        execution_time = (time.time() - start_time) * 1000
        metrics.add_metric(
            name="request.latency", unit=MetricUnit.Milliseconds, value=execution_time
        )
        metrics.add_metric(name="request.result_deny", unit=MetricUnit.Count, value=1)

        # Log the final error policy response before returning
        logger.info(
            f"Returning final error policy response: {json.dumps(policy, default=str)}",
            extra={"correlation_id": correlation_id},
        )

        return policy


# For backward compatibility
lambda_handler = handler
