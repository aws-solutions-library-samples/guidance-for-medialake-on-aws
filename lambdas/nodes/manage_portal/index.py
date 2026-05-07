"""Create or update an upload portal and generate a shareable link."""

import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import boto3
import botocore.exceptions
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from jsonpath_ng.ext import parse as jsonpath_parse
from lambda_middleware import lambda_middleware

ACCESS_CONTROL_FIELDS = {
    "isActive",
    "expiresAt",
    "ipAllowlist",
    "accessMode",
    "allowedGroups",
    "passphrase",
    "tokenBypassesPassphrase",
}

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
    field_mapping = json.loads(os.environ.get("FIELD_MAPPING", "{}")) or data.get(
        "fieldMapping", {}
    )
    default_portal_config = json.loads(
        os.environ.get("DEFAULT_PORTAL_CONFIG", "{}")
    ) or data.get("defaultPortalConfig", {})
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

    # Merge: mapped values win over defaults
    merged = {**default_portal_config, **mapped_values}

    slug = merged.get("slug")
    if not slug:
        raise ValueError("slug is required")

    # Extract recipient email via JSONPath
    recipient_email = ""
    if email_field:
        result = _evaluate_jsonpath(email_field, data)
        if result is None:
            result = _evaluate_jsonpath(email_field, payload)
        recipient_email = result if result is not None else ""

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Check if portal exists
    slug_resp = table.get_item(Key={"PK": f"UPLOADPORTAL_SLUG#{slug}", "SK": "INDEX"})
    slug_item = slug_resp.get("Item")

    def _update_existing_portal(portal_id):
        """Update metadata for an existing portal and return (portal_id, access_mode, meta_item)."""
        meta_resp = table.get_item(
            Key={"PK": f"UPLOADPORTAL#{portal_id}", "SK": "METADATA"}
        )
        meta_item = meta_resp.get("Item", {})
        access_mode = merged.get("accessMode") or meta_item.get("accessMode", "")

        update_expr_parts = ["#updatedAt = :updatedAt"]
        expr_names = {"#updatedAt": "updatedAt"}
        expr_values = {":updatedAt": now}

        for field_key, field_val in merged.items():
            safe_key = field_key.replace("-", "_")
            update_expr_parts.append(f"#{safe_key} = :{safe_key}")
            expr_names[f"#{safe_key}"] = field_key
            expr_values[f":{safe_key}"] = field_val

        # Atomically increment accessVersion when access-control fields are mutated
        has_access_control_change = bool(ACCESS_CONTROL_FIELDS & merged.keys())
        add_expr_parts = []
        if has_access_control_change:
            add_expr_parts.append("#accessVersion :incr")
            expr_names["#accessVersion"] = "accessVersion"
            expr_values[":incr"] = 1

        update_expression = "SET " + ", ".join(update_expr_parts)
        if add_expr_parts:
            update_expression += " ADD " + ", ".join(add_expr_parts)

        table.update_item(
            Key={"PK": f"UPLOADPORTAL#{portal_id}", "SK": "METADATA"},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )
        return access_mode, meta_item

    if slug_item:
        # Portal exists — update metadata
        portal_id = slug_item["portalId"]
        access_mode, meta_item = _update_existing_portal(portal_id)
    else:
        # Portal does not exist — create it
        portal_id = str(uuid.uuid4())

        # Claim slug atomically — first writer wins
        try:
            table.put_item(
                Item={
                    "PK": f"UPLOADPORTAL_SLUG#{slug}",
                    "SK": "INDEX",
                    "portalId": portal_id,
                },
                ConditionExpression="attribute_not_exists(PK)",
            )
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Slug was claimed concurrently — re-read with consistent read and update
                slug_resp = table.get_item(
                    Key={"PK": f"UPLOADPORTAL_SLUG#{slug}", "SK": "INDEX"},
                    ConsistentRead=True,
                )
                slug_item = slug_resp.get("Item")
                if not slug_item:
                    raise RuntimeError(
                        f"Slug '{slug}' conflict detected but slug index not found on consistent re-read"
                    )
                portal_id = slug_item["portalId"]
                access_mode, meta_item = _update_existing_portal(portal_id)
            else:
                raise
        else:
            # Slug claimed successfully — write metadata
            metadata_item = {
                "PK": f"UPLOADPORTAL#{portal_id}",
                "SK": "METADATA",
                "portalId": portal_id,
                "GSI1_PK": "UPLOADPORTALS",
                "GSI1_SK": now,
                "isActive": True,
                "createdAt": now,
                "updatedAt": now,
                "accessVersion": 1,
                **merged,
            }
            try:
                table.put_item(Item=metadata_item)
            except Exception as meta_exc:
                # Best-effort cleanup: remove the slug index so it isn't orphaned.
                # Guard: a concurrent request may have already fallen through the
                # ConditionalCheckFailedException path and written metadata for
                # this portal.  If metadata now exists, the slug index is valid
                # and must NOT be deleted.
                try:
                    guard_resp = table.get_item(
                        Key={"PK": f"UPLOADPORTAL#{portal_id}", "SK": "METADATA"},
                        ConsistentRead=True,
                    )
                    if not guard_resp.get("Item"):
                        table.delete_item(
                            Key={"PK": f"UPLOADPORTAL_SLUG#{slug}", "SK": "INDEX"}
                        )
                except Exception as cleanup_exc:
                    logger.warning(
                        "Failed to clean up slug index after metadata write failure",
                        extra={
                            "slug": slug,
                            "portalId": portal_id,
                            "cleanupError": str(cleanup_exc),
                        },
                    )
                raise meta_exc
            access_mode = merged.get("accessMode", "")
            meta_item = {}

    portal_name = merged.get("name") or meta_item.get("name", "")

    # Create token and build URL
    portal_path = "/p/" if access_mode == "public" else "/upload/"
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
