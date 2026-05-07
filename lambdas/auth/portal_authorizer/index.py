"""
Portal API Gateway Lambda Authorizer.

Validates incoming portal requests by looking up the portal record in DynamoDB,
checking IP allowlists, portal status/expiry, session JWTs, and access-mode-specific
credentials (public, token-protected, cognito-groups). Fail-closed on any error.
"""

import hashlib
import ipaddress
import json
import logging
import os
import urllib.request
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

import boto3
from jose import exceptions as jose_exceptions
from jose import jwt

SYSTEM_SETTINGS_TABLE_NAME = os.environ.get("SYSTEM_SETTINGS_TABLE_NAME", "")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
RESOURCE_PREFIX = os.environ.get("RESOURCE_PREFIX", "")

dynamodb = boto3.resource("dynamodb")
secretsmanager = boto3.client("secretsmanager")

_jwks_cache = None

# JWKS endpoint fetch timeout in seconds. Short so a hung endpoint can't
# stall the authorizer (which gates every portal request).
JWKS_FETCH_TIMEOUT = 5

# DynamoDB key constants (replicated from portal_utils — separate package)
PORTAL_PK_PREFIX = "UPLOADPORTAL#"
PORTAL_SLUG_PK_PREFIX = "UPLOADPORTAL_SLUG#"
METADATA_SK = "METADATA"
TOKEN_SK_PREFIX = "TOKEN#"
INDEX_SK = "INDEX"


def _build_policy(principal_id, effect, method_arn, context=None):
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
    }
    if context:
        policy["context"] = context
    return policy


def _allow(method_arn, portal_id):
    return _build_policy("portal-visitor", "Allow", method_arn, {"portalId": portal_id})


def _deny(method_arn):
    return _build_policy("portal-visitor", "Deny", method_arn)


def _get_header(headers, name):
    """Truly case-insensitive header lookup."""
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def _check_ip(viewer_address, ip_allowlist):
    """Check if the viewer IP is within any of the allowed CIDR ranges."""
    try:
        # CloudFront-Viewer-Address: <ip>:<port> or [<ipv6>]:<port>
        raw = viewer_address.rsplit(":", 1)[0].strip("[]")
        ip = ipaddress.ip_address(raw)
        return any(
            ip in ipaddress.ip_network(cidr, strict=False) for cidr in ip_allowlist
        )
    except (ValueError, TypeError):
        return False


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


def _get_portal_by_slug(table, slug):
    """Two-step DynamoDB lookup: slug → portalId → full metadata record."""
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


def _validate_session_jwt(token, portal_id):
    """Validate a session JWT signed with the portal's HS256 secret."""
    try:
        secret_name = f"{RESOURCE_PREFIX}/portals/{portal_id}/session-secret"
        resp = secretsmanager.get_secret_value(SecretId=secret_name)
        secret = resp["SecretString"]
        jwt.decode(token, secret, algorithms=["HS256"])
        return True
    except (jose_exceptions.JWTError, Exception):
        return False


def _validate_token_protected(table, portal_id, headers):
    """Validate token-protected access via X-Portal-Token and X-Portal-Email headers."""
    raw_token = _get_header(headers, "X-Portal-Token")
    email = _get_header(headers, "X-Portal-Email")
    if not raw_token or not email:
        return False

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    from boto3.dynamodb.conditions import Key

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
        return True

    return False


def _get_jwks():
    """Fetch and cache Cognito JWKS for JWT verification.

    Uses a short timeout so a hung endpoint doesn't block the authorizer.
    On failure we clear the cache and re-raise so the next invocation retries.
    """
    global _jwks_cache
    if _jwks_cache is None:
        url = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
        try:
            with urllib.request.urlopen(url, timeout=JWKS_FETCH_TIMEOUT) as resp:
                _jwks_cache = json.loads(resp.read().decode())
        except Exception:
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


def _is_auth_route(event):
    """Detect if the request targets /portal/{slug}/auth."""
    path = event.get("path") or event.get("resource") or ""
    return path.rstrip("/").endswith("/auth")


def _get_unverified_claims(token):
    """Parse JWT claims without signature verification. Returns None on any error."""
    try:
        return jwt.get_unverified_claims(token)
    except Exception:
        return None


def lambda_handler(event, context):
    method_arn = event.get("methodArn", "*")
    try:
        headers = event.get("headers") or {}
        logger.info("Authorizer headers: %s", json.dumps(list(headers.keys())))
        logger.info(
            "Authorizer pathParameters: %s", json.dumps(event.get("pathParameters"))
        )

        # Step 1 — IP check (use X-Forwarded-For as primary, CloudFront-Viewer-Address as fallback)
        # X-Forwarded-For is always forwarded by CloudFront's AllViewerExceptHostHeader policy.
        # CloudFront-Viewer-Address requires a custom origin request policy.
        viewer_address = _get_header(headers, "CloudFront-Viewer-Address")
        if not viewer_address:
            xff = _get_header(headers, "X-Forwarded-For")
            if xff:
                # X-Forwarded-For: <client>, <proxy1>, ... — take the first (client) IP
                client_ip = xff.split(",")[0].strip()
                viewer_address = f"{client_ip}:0"
        if not viewer_address:
            logger.info("DENY step1: no CloudFront-Viewer-Address or X-Forwarded-For")
            return _deny(method_arn)

        # Step 2 — Extract session token and slug
        session_token = _get_header(headers, "X-Portal-Session")
        slug = (event.get("pathParameters") or {}).get("slug")

        # Step 3 — Session JWT fast-path (no DDB)
        if session_token and slug:
            try:
                claims = _get_unverified_claims(session_token)
                if claims and claims.get("sub") and claims.get("slug") == slug:
                    portal_id = claims["sub"]
                    secret_name = (
                        f"{RESOURCE_PREFIX}/portals/{portal_id}/session-secret"
                    )
                    resp = secretsmanager.get_secret_value(SecretId=secret_name)
                    secret = resp["SecretString"]
                    verified = jwt.decode(session_token, secret, algorithms=["HS256"])

                    # Revocation window: time for this projected DDB read (~1–5 ms) plus Lambda
                    # cold-start overhead (~100–500 ms for first invocation). Warm Lambda revocation
                    # is sub-second. This single-field projected read costs ~0.5 RCU.
                    table = dynamodb.Table(SYSTEM_SETTINGS_TABLE_NAME)
                    version_resp = table.get_item(
                        Key={"PK": f"{PORTAL_PK_PREFIX}{portal_id}", "SK": METADATA_SK},
                        ProjectionExpression="#av",
                        ExpressionAttributeNames={"#av": "accessVersion"},
                    )
                    current_version = int(
                        version_resp.get("Item", {}).get("accessVersion") or 1
                    )
                    jwt_version = int(verified.get("accessVersion") or 1)
                    if current_version != jwt_version:
                        raise ValueError(
                            "accessVersion mismatch — falling through to full DDB path"
                        )

                    # Enforce ipAllowlist claim
                    ip_allowlist = verified.get("ipAllowlist") or []
                    if ip_allowlist:
                        if not _check_ip(viewer_address, ip_allowlist):
                            return _deny(method_arn)

                    # Enforce isActive claim
                    if not verified.get("isActive", False):
                        return _deny(method_arn)

                    # Enforce expiresAt claim
                    if _is_expired(verified.get("expiresAt")):
                        return _deny(method_arn)

                    return _allow(method_arn, portal_id)
            except Exception:
                pass  # Fall through to DDB path

        # Step 4 — Require slug for DDB path
        if not slug:
            return _deny(method_arn)

        # Step 5 — Portal lookup via DDB
        table = dynamodb.Table(SYSTEM_SETTINGS_TABLE_NAME)
        portal_id, portal = _get_portal_by_slug(table, slug)
        if not portal:
            return _deny(method_arn)

        # IP allowlist check from DDB record
        ip_allowlist = portal.get("ipAllowlist") or []
        if ip_allowlist:
            if not _check_ip(viewer_address, ip_allowlist):
                return _deny(method_arn)

        # Step 6 — Active/expiry check from DDB record
        if not portal.get("isActive", False):
            return _deny(method_arn)
        if _is_expired(portal.get("expiresAt")):
            return _deny(method_arn)

        # Step 7 — Short-circuit for /portal/{slug}/auth route
        if _is_auth_route(event):
            return _allow(method_arn, portal_id)

        # Step 8 — Access mode check
        access_mode = portal.get("accessMode", "public")
        if access_mode == "public":
            return _allow(method_arn, portal_id)
        elif access_mode == "token-protected":
            if _validate_token_protected(table, portal_id, headers):
                return _allow(method_arn, portal_id)
            return _deny(method_arn)
        elif access_mode == "cognito-groups":
            auth_header = _get_header(headers, "Authorization") or ""
            token = (
                auth_header[7:] if auth_header.lower().startswith("bearer ") else None
            )
            if not token:
                return _deny(method_arn)
            allowed_groups = portal.get("allowedGroups") or []
            if _validate_cognito_jwt(token, allowed_groups):
                return _allow(method_arn, portal_id)
            return _deny(method_arn)
        else:
            return _deny(method_arn)

    except Exception:
        return _deny(method_arn)
