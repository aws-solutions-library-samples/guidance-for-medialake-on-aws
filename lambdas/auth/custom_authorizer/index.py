"""
Custom API Gateway Lambda Authorizer for Media Lake.

This Lambda function acts as the primary enforcement point for the authorization system.
It validates JWT tokens and calls Amazon Verified Permissions (AVP) for evaluation
before allowing requests to proceed to backend Lambdas.
"""

import hashlib
import json
import os
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
    correlation_id = context.aws_request_id

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
        # Extract the bearer token from the Authorization header
        auth_header = event.get("headers", {}).get("Authorization") or event.get(
            "headers", {}
        ).get("authorization")
        auth_token = event.get("authorizationToken")

        # In production, don't log the auth header as it contains sensitive information
        if ENVIRONMENT != "prod":
            logger.info(
                f"Auth header present: {auth_header is not None}",
                extra={"correlation_id": correlation_id},
            )

        bearer_token = None
        if auth_header:
            bearer_token = extract_token_from_header(auth_header)
            metrics.add_metric(
                name="extract.token.from_header", unit=MetricUnit.Count, value=1
            )
        elif auth_token:
            bearer_token = extract_token_from_header(auth_token)
            metrics.add_metric(
                name="extract.token.from_token", unit=MetricUnit.Count, value=1
            )

        if not bearer_token:
            logger.error(
                "No bearer token found in authorization sources",
                extra={"correlation_id": correlation_id},
            )
            metrics.add_metric(
                name="request.missing_token", unit=MetricUnit.Count, value=1
            )
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

            policy = {
                "principalId": principal_id,
                "policyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "execute-api:Invoke",
                            "Effect": effect,
                            "Resource": method_arn,
                        }
                    ],
                },
                "context": {
                    "actionId": action_id,
                    "userId": principal_id,
                    "username": parsed_token.get("cognito:username", ""),
                    "sub": parsed_token.get("sub", ""),
                    "requestId": correlation_id,
                },
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
                            "Resource": method_arn,
                        }
                    ],
                },
                "context": {"error": str(e), "requestId": correlation_id},
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
                        "Resource": method_arn,
                    }
                ],
            },
            "context": {"error": str(e), "requestId": correlation_id},
        }

        # Record execution time
        execution_time = (time.time() - start_time) * 1000
        metrics.add_metric(
            name="request.latency", unit=MetricUnit.Milliseconds, value=execution_time
        )
        metrics.add_metric(name="request.result_deny", unit=MetricUnit.Count, value=1)

        return policy


# For backward compatibility
lambda_handler = handler
