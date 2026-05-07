"""Generate a shareable upload portal link with a secure token."""

import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from jsonpath_ng.ext import parse as jsonpath_parse
from lambda_middleware import lambda_middleware

logger = Logger()
tracer = Tracer()

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["SYSTEM_SETTINGS_TABLE_NAME"])
CLOUDFRONT_DOMAIN = os.environ.get("CLOUDFRONT_DOMAIN", "")


def _evaluate_jsonpath(expr, data):
    """Evaluate a JSONPath expression against data, returning the first match or None."""
    matches = jsonpath_parse(expr).find(data)
    return matches[0].value if matches else None


def _create_token(
    table, portal_id, slug, mapped_values, email, expiry_days, portal_path="/upload/"
):
    """Create a token record in DynamoDB and return token details + shareable URL."""
    if not CLOUDFRONT_DOMAIN:
        raise ValueError(
            "CLOUDFRONT_DOMAIN environment variable is not set. "
            "Cannot generate portal URLs without a valid CloudFront domain."
        )
    token_id = str(uuid.uuid4())
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    expires_at = (
        (datetime.now(timezone.utc) + timedelta(days=expiry_days))
        .isoformat()
        .replace("+00:00", "Z")
    )

    table.put_item(
        Item={
            "PK": f"UPLOADPORTAL#{portal_id}",
            "SK": f"TOKEN#{token_id}",
            "tokenId": token_id,
            "tokenHash": token_hash,
            "associatedEmail": email or "",
            "expiresAt": expires_at,
            "isRevoked": False,
            "createdAt": now,
            "prePopulatedParams": mapped_values or {},
        }
    )

    shareable_url = f"https://{CLOUDFRONT_DOMAIN}{portal_path}{slug}?token={raw_token}"
    if mapped_values:
        shareable_url += "&" + urlencode(mapped_values)

    return token_id, raw_token, expires_at, shareable_url


@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    logger.info("Incoming event", extra={"event": event})

    payload = event.get("payload", {})
    data = payload.get("data", {})

    # Read parameters — env vars take precedence
    portal_slug = os.environ.get("PORTAL_SLUG") or data.get("portalSlug")
    field_mapping = json.loads(os.environ.get("FIELD_MAPPING", "{}")) or data.get(
        "fieldMapping", {}
    )
    token_expiry_days = int(
        os.environ.get("TOKEN_EXPIRY_DAYS", data.get("tokenExpiryDays", 7))
    )
    email_field = os.environ.get("EMAIL_FIELD") or data.get("emailField")

    # Evaluate JSONPath expressions in field_mapping
    # Each entry is jsonpath_expression -> target_field_name
    # Evaluate against data (Jira business payload) first, fall back to payload (pipeline wrapper)
    mapped_values = {}
    for expr, target_field in field_mapping.items():
        result = _evaluate_jsonpath(expr, data)
        if result is None:
            result = _evaluate_jsonpath(expr, payload)
        if result is not None:
            mapped_values[target_field] = result

    # Extract recipient email via JSONPath
    recipient_email = ""
    if email_field:
        result = _evaluate_jsonpath(email_field, data)
        if result is None:
            result = _evaluate_jsonpath(email_field, payload)
        recipient_email = result if result is not None else ""

    # Look up portal by slug
    slug_resp = table.get_item(
        Key={"PK": f"UPLOADPORTAL_SLUG#{portal_slug}", "SK": "INDEX"}
    )
    slug_item = slug_resp.get("Item")
    if not slug_item:
        raise ValueError(f"Portal with slug '{portal_slug}' not found")
    portal_id = slug_item["portalId"]

    # Get portal metadata
    meta_resp = table.get_item(
        Key={"PK": f"UPLOADPORTAL#{portal_id}", "SK": "METADATA"}
    )
    meta_item = meta_resp.get("Item", {})
    portal_name = meta_item.get("name", "")
    slug = meta_item.get("slug", portal_slug)
    access_mode = meta_item.get("accessMode", "")
    portal_path = "/p/" if access_mode == "public" else "/upload/"

    # Create token and build URL
    token_id, raw_token, expires_at, shareable_url = _create_token(
        table,
        portal_id,
        slug,
        mapped_values,
        recipient_email,
        token_expiry_days,
        portal_path,
    )

    return {
        "portalUrl": shareable_url,
        "recipientEmail": recipient_email,
        "portalName": portal_name,
        "datasetName": mapped_values.get("datasetName", ""),
        "expiresAt": expires_at,
        "tokenId": token_id,
    }
