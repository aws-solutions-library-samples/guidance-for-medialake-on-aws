import json
import os
import time
from functools import lru_cache

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from boto3.dynamodb.conditions import Key
from cors_utils import create_response

logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="MedialakeS3Explorer")

# Create a global S3 client outside the handler to benefit from connection reuse
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")


# Cache connector lookups to avoid repeated DB calls
@lru_cache(maxsize=100)
def get_connector(connector_id, table_name):
    """Get connector with caching to avoid repeated DB calls"""
    try:
        logger.debug(f"Getting connector {connector_id} from table {table_name}")
        table = dynamodb.Table(table_name)

        with tracer.provider.in_subsegment("get_connector_from_dynamodb") as subsegment:
            subsegment.put_annotation("connector_id", connector_id)

            start_time = time.time()
            connector_response = table.query(
                KeyConditionExpression=Key("id").eq(connector_id)
            )
            query_time = (time.time() - start_time) * 1000

            metrics.add_metric(
                name="DynamoDBQueryLatency", unit="Milliseconds", value=query_time
            )
            logger.debug(f"DynamoDB query took {query_time}ms")

            return (
                connector_response["Items"][0] if connector_response["Items"] else None
            )
    except Exception as e:
        logger.error(f"Failed to get connector: {str(e)}")
        return None


def normalize_prefix(prefix):
    """
    Normalize a prefix by trimming whitespace and ensuring a single trailing slash.

    Args:
        prefix (str): Raw prefix string

    Returns:
        str: Normalized prefix with trailing slash (empty string if input is empty)
    """
    if not prefix:
        return ""

    # Trim whitespace
    prefix = prefix.strip()

    if not prefix:
        return ""

    # Ensure single trailing slash for non-empty prefixes
    if not prefix.endswith("/"):
        prefix = prefix + "/"

    return prefix


def parse_object_prefixes(object_prefix):
    """
    Parse objectPrefix from connector configuration into a list of prefix strings.

    Args:
        object_prefix: Raw objectPrefix value from connector (str, list, or None)

    Returns:
        list: List of normalized prefix strings (empty list if no prefixes configured)
    """
    if not object_prefix:
        return []

    if isinstance(object_prefix, str):
        # Single string prefix - normalize it
        normalized = normalize_prefix(object_prefix)
        return [normalized] if normalized else []
    elif isinstance(object_prefix, list):
        # List of prefixes - normalize each and filter out empty results
        return [
            normalized
            for prefix in object_prefix
            if prefix and (normalized := normalize_prefix(prefix))
        ]

    return []


def validate_prefix_access(requested_prefix, allowed_prefixes):
    """
    Validate if the requested prefix is allowed based on configured allowed prefixes.

    Args:
        requested_prefix (str): The prefix being requested
        allowed_prefixes (list): List of allowed prefix strings (assumed to be normalized)

    Returns:
        bool: True if access is allowed (requested prefix is within an allowed prefix), False otherwise
    """
    # If no prefixes configured, allow all access
    if not allowed_prefixes:
        return True

    # Handle edge cases
    if requested_prefix is None:
        requested_prefix = ""

    # Normalize the requested prefix for boundary-aware comparison
    normalized_requested = normalize_prefix(requested_prefix)

    # Check if requested prefix is within any allowed prefix
    for allowed_prefix in allowed_prefixes:
        if not allowed_prefix:
            continue

        # Normalize the allowed prefix for boundary-aware comparison
        normalized_allowed = normalize_prefix(allowed_prefix)

        # Allow only if requested prefix starts with (is within) an allowed prefix
        # This prevents accessing parent folders or sibling folders
        if normalized_requested.startswith(normalized_allowed):
            return True

    return False


def get_caller_sub(event):
    """Extract the caller's Cognito sub from the authorizer context.

    Checks ``requestContext.authorizer.sub`` first (custom authorizer), then falls back to
    ``requestContext.authorizer.claims.sub`` (Cognito). Returns None when it cannot be
    determined; callers decide how to handle that.
    """
    try:
        authorizer = event.get("requestContext", {}).get("authorizer", {})
        if not isinstance(authorizer, dict):
            return None

        sub = authorizer.get("sub")
        if sub:
            return sub

        claims = authorizer.get("claims")
        if isinstance(claims, str):
            try:
                claims = json.loads(claims)
            except (json.JSONDecodeError, ValueError):
                return None
        if isinstance(claims, dict):
            return claims.get("sub")
    except Exception:
        logger.warning("Could not determine caller sub from authorizer context")
    return None


def is_personal_connector(connector):
    """Whether this connector addresses a single user's personal ("My Assets") storage.

    Mirrors ``_is_personal_target`` in the upload handler: true for the per-user my-assets
    connector, and for any connector confined to the reserved ``personal/`` key prefix.
    """
    if connector.get("type") == "my-assets":
        return True

    object_prefix = connector.get("objectPrefix") or ""
    if isinstance(object_prefix, list):
        return any(
            str(prefix).lstrip("/").startswith("personal/") for prefix in object_prefix
        )
    return str(object_prefix).lstrip("/").startswith("personal/")


def validate_personal_connector_access(event, connector, connector_id):
    """Deny listing another user's personal storage.

    The prefix allow-list alone is not sufficient protection here. My Assets connectors are
    per-user records (``id = my-assets-{sub}``, ``objectPrefix = personal/{sub}/``), so a
    caller who supplies someone else's connector id would pass the allow-list check against
    *that* connector's prefix and list the other user's private files. Ownership therefore
    has to be checked explicitly, the same way the upload handler enforces
    ``personal/{user_sub}/`` on writes.

    Returns None when access is allowed, or a 403 response to return to the caller.
    """
    if not is_personal_connector(connector):
        return None

    caller_sub = get_caller_sub(event)
    if not caller_sub:
        logger.warning(
            f"Denying personal connector access for {connector_id}: caller sub unavailable"
        )
        metrics.add_metric(name="PersonalConnectorAccessDenied", unit="Count", value=1)
        return create_response(
            403,
            {"status": "error", "message": "Access denied"},
        )

    owner_sub = connector.get("userId")
    expected_prefix = f"personal/{caller_sub}/"
    object_prefix = connector.get("objectPrefix") or ""
    prefixes = object_prefix if isinstance(object_prefix, list) else [object_prefix]
    prefix_matches_caller = any(
        normalize_prefix(str(prefix)) == expected_prefix for prefix in prefixes
    )

    if (owner_sub and owner_sub == caller_sub) or prefix_matches_caller:
        return None

    logger.warning(
        f"Denying personal connector access for {connector_id}: "
        "caller does not own this personal storage"
    )
    metrics.add_metric(name="PersonalConnectorAccessDenied", unit="Count", value=1)
    return create_response(
        403,
        {"status": "error", "message": "Access denied"},
    )


@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event, context):
    """Main handler for S3 explorer API endpoint"""
    try:
        # Extract parameters. API Gateway sends queryStringParameters as null
        # (present, valued null) when the request has no query string, so a
        # `.get("queryStringParameters", {})` default never applies — coerce it.
        connector_id = event["pathParameters"]["connector_id"]
        query_params = event.get("queryStringParameters") or {}
        prefix = query_params.get("prefix", "")
        continuation_token = query_params.get("continuationToken")

        logger.info(
            f"S3 Explorer request for connector: {connector_id}, prefix: {prefix}"
        )

        # Get table name from environment variable
        table_name = os.environ.get("MEDIALAKE_CONNECTOR_TABLE")

        if not table_name:
            logger.error("MEDIALAKE_CONNECTOR_TABLE environment variable not set")
            return create_response(
                500,
                {
                    "status": "error",
                    "message": "Configuration error: Missing MEDIALAKE_CONNECTOR_TABLE environment variable",
                },
            )

        # Get connector with caching
        connector = get_connector(connector_id, table_name)

        if not connector:
            logger.warning(f"Connector {connector_id} not found")
            return create_response(
                404,
                {
                    "status": "error",
                    "message": f"Connector {connector_id} not found",
                },
            )

        bucket = connector.get("storageIdentifier")

        # A personal ("My Assets") connector may only be browsed by its owner. This is
        # checked before any prefix handling, because the allow-list is derived from the
        # connector record itself and so cannot distinguish one user's personal storage
        # from another's.
        personal_access_denied = validate_personal_connector_access(
            event, connector, connector_id
        )
        if personal_access_denied:
            return personal_access_denied

        # Parse objectPrefix into list format
        allowed_prefixes = parse_object_prefixes(connector.get("objectPrefix"))
        logger.debug(
            f"Parsed allowed prefixes for connector {connector_id}: {allowed_prefixes}"
        )

        # Sort allowed prefixes for deterministic default selection
        # Sort lexicographically to ensure consistent behavior
        if allowed_prefixes:
            allowed_prefixes = sorted(allowed_prefixes)
            logger.debug(f"Sorted allowed prefixes: {allowed_prefixes}")

        # Derive default prefix for backward compatibility
        default_prefix = allowed_prefixes[0] if allowed_prefixes else ""

        # Set default prefix if no prefix requested
        if not prefix and default_prefix:
            prefix = default_prefix

        # Normalize the incoming prefix before validation and S3 operations
        prefix = normalize_prefix(prefix)

        # Validate requested prefix against allowed prefixes
        if allowed_prefixes:
            if not validate_prefix_access(prefix, allowed_prefixes):
                logger.warning(
                    f"Access denied for connector {connector_id}: "
                    f"requested prefix '{prefix}' is outside allowed prefixes {allowed_prefixes}"
                )
                metrics.add_metric(
                    name="PrefixValidationFailures", unit="Count", value=1
                )
                return create_response(
                    403,
                    {
                        "status": "error",
                        "message": "Access denied: requested path is outside allowed prefixes",
                        "allowedPrefixes": allowed_prefixes,
                    },
                )
            logger.info(f"Prefix validation passed for {prefix}")
            metrics.add_metric(name="PrefixValidationSuccess", unit="Count", value=1)

        if not bucket:
            logger.warning(f"Bucket not configured for connector {connector_id}")
            return create_response(
                400,
                {
                    "status": "error",
                    "message": "Bucket not configured for connector",
                },
            )

        # List S3 objects
        params = {
            "Bucket": bucket,
            "Delimiter": "/",
            "MaxKeys": 1000,
            "Prefix": prefix or "",
        }
        if continuation_token:
            params["ContinuationToken"] = continuation_token

        # Record S3 operation with tracing
        with tracer.provider.in_subsegment("list_s3_objects") as subsegment:
            subsegment.put_annotation("bucket", bucket)
            subsegment.put_annotation("prefix", prefix)

            start_time = time.time()
            response = s3_client.list_objects_v2(**params)
            end_time = time.time()

            # Record the S3 operation latency
            latency = (end_time - start_time) * 1000
            metrics.add_metric(
                name="S3ListObjectsLatency", unit="Milliseconds", value=latency
            )
            logger.info(f"S3 list_objects_v2 latency: {latency}ms")

            # Count prefixes returned for metrics
            prefix_count = len(response.get("CommonPrefixes", []))
            metrics.add_metric(
                name="S3PrefixesReturned", unit="Count", value=prefix_count
            )

            subsegment.put_metadata("prefix_count", prefix_count)

        # Return only folders (commonPrefixes), not individual files
        result = {
            "commonPrefixes": [p["Prefix"] for p in response.get("CommonPrefixes", [])],
            "prefix": prefix,
            "allowedPrefixes": allowed_prefixes,
            "delimiter": "/",
            "isTruncated": response.get("IsTruncated", False),
            "nextContinuationToken": response.get("NextContinuationToken"),
        }

        response = create_response(
            200,
            {
                "status": "success",
                "message": "Objects retrieved successfully",
                "data": result,
            },
        )
        # Add caching header for frontend
        response["headers"]["Cache-Control"] = "max-age=60"
        return response

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        error_message = str(e)
        status_code = 400 if "NoSuchBucket" in error_message else 500

        return create_response(
            status_code, {"status": "error", "message": error_message}
        )
