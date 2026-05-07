"""
Portal Auth API Lambda Handler.

Handles POST /portal/{slug}/auth — validates credentials per access mode
and issues a short-lived session JWT on success.
"""

import hashlib
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

import bcrypt
import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import (
    APIGatewayRestResolver,
    CORSConfig,
    Response,
)
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from jose import exceptions as jose_exceptions
from jose import jwt

logger = Logger(service="portal-auth-api", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="portal-auth-api")
metrics = Metrics(namespace="medialake", service="portal-auth-api")

SYSTEM_SETTINGS_TABLE_NAME = os.environ.get("SYSTEM_SETTINGS_TABLE_NAME", "")
RESOURCE_PREFIX = os.environ.get("RESOURCE_PREFIX", "")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

dynamodb = boto3.resource("dynamodb")
secretsmanager = boto3.client("secretsmanager")

_jwks_cache = None

# JWKS endpoint fetch timeout in seconds. Kept short so cold-start or
# transient network failures don't stall the auth path — a stalled fetch
# leaves `_jwks_cache` as None and the next invocation will retry.
JWKS_FETCH_TIMEOUT = 5

# DynamoDB key constants (replicated from portal_utils — separate package)
PORTAL_PK_PREFIX = "UPLOADPORTAL#"
PORTAL_SLUG_PK_PREFIX = "UPLOADPORTAL_SLUG#"
METADATA_SK = "METADATA"
TOKEN_SK_PREFIX = "TOKEN#"
INDEX_SK = "INDEX"

cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=[
        "Content-Type",
        "X-Amz-Date",
        "Authorization",
        "X-Api-Key",
        "X-Amz-Security-Token",
    ],
    expose_headers=["X-Request-Id"],
    max_age=300,
)

app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=str),
    strip_prefixes=["/portal"],
    cors=cors_config,
)


def _get_portal_by_slug(slug):
    """Two-step DynamoDB lookup: slug → portalId → full metadata record."""
    table = dynamodb.Table(SYSTEM_SETTINGS_TABLE_NAME)
    slug_resp = table.get_item(
        Key={"PK": f"{PORTAL_SLUG_PK_PREFIX}{slug}", "SK": INDEX_SK}
    )
    slug_item = slug_resp.get("Item")
    if not slug_item:
        return None, None

    portal_id = slug_item.get("portalId")
    if not portal_id:
        return None, None

    meta_resp = table.get_item(
        Key={"PK": f"{PORTAL_PK_PREFIX}{portal_id}", "SK": METADATA_SK}
    )
    portal = meta_resp.get("Item")
    if not portal:
        return None, None

    return portal_id, portal


def _is_expired(expires_at_str):
    """Return True if the portal has expired. Fail closed on malformed timestamps."""
    if not expires_at_str:
        return False
    try:
        parsed = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= parsed
    except (ValueError, TypeError):
        return True


def _issue_session_jwt(portal_id, portal, slug):
    """Fetch the portal's HS256 secret and sign a 1-hour session JWT with portal state claims."""
    secret_name = f"{RESOURCE_PREFIX}/portals/{portal_id}/session-secret"
    resp = secretsmanager.get_secret_value(SecretId=secret_name)
    secret = resp["SecretString"]
    now_ts = int(time.time())
    return jwt.encode(
        {
            "sub": portal_id,
            "slug": slug,
            "iat": now_ts,
            "exp": now_ts + 3600,
            "isActive": portal.get("isActive", False),
            "expiresAt": portal.get("expiresAt"),
            "ipAllowlist": portal.get("ipAllowlist") or [],
            "accessVersion": int(portal.get("accessVersion") or 1),
        },
        secret,
        algorithm="HS256",
    )


def _get_jwks():
    """Fetch and cache Cognito JWKS for JWT verification.

    Uses a short timeout so a hung endpoint doesn't hold the Lambda open.
    On failure we leave ``_jwks_cache`` as ``None`` so the next invocation
    retries, and re-raise the exception to the caller.
    """
    global _jwks_cache
    if _jwks_cache is None:
        url = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
        try:
            with urllib.request.urlopen(url, timeout=JWKS_FETCH_TIMEOUT) as resp:
                _jwks_cache = json.loads(resp.read().decode())
        except Exception:
            # Make sure a partial/failed fetch doesn't poison the cache.
            _jwks_cache = None
            raise
    return _jwks_cache


def _validate_cognito_jwt(token, allowed_groups):
    """Validate a Cognito JWT and optionally check group membership."""
    try:
        jwks = _get_jwks()
        claims = jwt.decode(
            token, jwks, algorithms=["RS256"], options={"verify_at_hash": False}
        )
        if allowed_groups:
            user_groups = set(claims.get("cognito:groups", []))
            if not user_groups.intersection(set(allowed_groups)):
                return False
        return True
    except (jose_exceptions.JWTError, Exception):
        return False


def _find_token_record(table, portal_id, raw_token, email):
    """Find a matching non-revoked, non-expired token record."""
    from boto3.dynamodb.conditions import Key

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    resp = table.query(
        KeyConditionExpression=Key("PK").eq(f"{PORTAL_PK_PREFIX}{portal_id}")
        & Key("SK").begins_with(TOKEN_SK_PREFIX)
    )
    for record in resp.get("Items", []):
        if record.get("isRevoked"):
            continue
        if record.get("tokenHash") != token_hash:
            continue
        if (record.get("associatedEmail") or "").lower() != email.lower():
            continue
        if _is_expired(record.get("expiresAt")):
            continue
        return record
    return None


@app.post("/<slug>/auth")
@tracer.capture_method
def post_portal_auth(slug: str):
    """Authenticate a portal visitor and issue a session JWT."""
    portal_id, portal = _get_portal_by_slug(slug)
    if not portal:
        return Response(
            status_code=404,
            content_type="application/json",
            body=json.dumps({"message": "Portal not found"}),
        )

    if not portal.get("isActive", False) or _is_expired(portal.get("expiresAt")):
        return Response(
            status_code=403,
            content_type="application/json",
            body=json.dumps({"message": "Portal is not available"}),
        )

    access_mode = portal.get("accessMode", "public")

    # Public — issue session immediately
    if access_mode == "public":
        token = _issue_session_jwt(portal_id, portal, slug)
        return {"sessionToken": token, "accessMode": "public"}

    # Token-protected
    if access_mode == "token-protected":
        body = app.current_event.json_body or {}
        raw_token = body.get("token")
        email = body.get("email")
        passphrase = body.get("passphrase")

        # Path 1: passphrase-only access (no token provided)
        if not raw_token:
            if not portal.get("passphrase"):
                return Response(
                    status_code=400,
                    content_type="application/json",
                    body=json.dumps({"message": "token and email are required"}),
                )
            if not passphrase:
                return Response(
                    status_code=400,
                    content_type="application/json",
                    body=json.dumps({"message": "passphrase is required"}),
                )
            if not bcrypt.checkpw(passphrase.encode(), portal["passphrase"].encode()):
                return Response(
                    status_code=403,
                    content_type="application/json",
                    body=json.dumps({"message": "Invalid passphrase"}),
                )
            token = _issue_session_jwt(portal_id, portal, slug)
            return {"sessionToken": token, "accessMode": "token-protected"}

        # Path 2: token+email access with optional tokenBypassesPassphrase
        if not email:
            return Response(
                status_code=400,
                content_type="application/json",
                body=json.dumps({"message": "token and email are required"}),
            )

        table = dynamodb.Table(SYSTEM_SETTINGS_TABLE_NAME)
        record = _find_token_record(table, portal_id, raw_token, email)
        if not record:
            return Response(
                status_code=403,
                content_type="application/json",
                body=json.dumps({"message": "Invalid token or email"}),
            )

        # Passphrase check (if portal has one and token doesn't bypass it)
        if portal.get("passphrase") and not portal.get("tokenBypassesPassphrase"):
            if not passphrase:
                return Response(
                    status_code=400,
                    content_type="application/json",
                    body=json.dumps({"message": "passphrase is required"}),
                )
            if not bcrypt.checkpw(passphrase.encode(), portal["passphrase"].encode()):
                return Response(
                    status_code=403,
                    content_type="application/json",
                    body=json.dumps({"message": "Invalid passphrase"}),
                )

        token = _issue_session_jwt(portal_id, portal, slug)
        return {"sessionToken": token, "accessMode": "token-protected"}

    # Cognito groups
    if access_mode == "cognito-groups":
        auth_header = app.current_event.headers.get("Authorization", "")
        bearer_token = (
            auth_header[7:] if auth_header.lower().startswith("bearer ") else None
        )
        if not bearer_token:
            return Response(
                status_code=401,
                content_type="application/json",
                body=json.dumps({"message": "Authorization header required"}),
            )
        allowed_groups = portal.get("allowedGroups") or []
        if not _validate_cognito_jwt(bearer_token, allowed_groups):
            return Response(
                status_code=403,
                content_type="application/json",
                body=json.dumps({"message": "Access denied"}),
            )
        token = _issue_session_jwt(portal_id, portal, slug)
        return {"sessionToken": token, "accessMode": "cognito-groups"}

    # Unknown access mode
    return Response(
        status_code=403,
        content_type="application/json",
        body=json.dumps({"message": "Access denied"}),
    )


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Main Lambda handler for Portal Auth API."""
    logger.info(
        "Portal Auth API invoked",
        extra={
            "http_method": event.get("httpMethod"),
            "path": event.get("path"),
        },
    )
    try:
        return app.resolve(event, context)
    except Exception as e:
        logger.exception("Unhandled exception in Portal Auth API", exc_info=e)
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "An unexpected error occurred"}),
        }
