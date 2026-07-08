"""Create or update an upload portal and generate a shareable link."""

import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlencode

import bcrypt
import boto3
import botocore.exceptions
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from jsonpath_ng.ext import parse as jsonpath_parse
from lambda_middleware import lambda_middleware

# Shared portal validation / field rules (common_libraries layer) — same source
# of truth as the admin portal API and the deploy-time pipeline check.
from portal_validation import (
    ACCESS_CONTROL_FIELDS,
    select_portal_config_fields,
    validate_portal_config,
)

logger = Logger()
tracer = Tracer()

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["SYSTEM_SETTINGS_TABLE_NAME"])
secretsmanager = boto3.client("secretsmanager")
CLOUDFRONT_DOMAIN = os.environ.get("CLOUDFRONT_DOMAIN", "")
# Must match the prefix used by the admin portal API (portals_post.py) and the
# portal auth endpoint (portal_auth/index.py) so the session secret name lines up.
RESOURCE_PREFIX = os.environ.get("RESOURCE_PREFIX", "")


def _session_secret_name(portal_id):
    """Return the Secrets Manager name for a portal's session-signing secret."""
    return f"{RESOURCE_PREFIX}/portals/{portal_id}/session-secret"


def _create_session_secret(portal_id):
    """Create the per-portal HS256 session secret.

    The portal auth endpoint (``portal_auth``) signs short-lived session JWTs
    with this secret. A portal created without it returns 500 on every
    ``/portal/{slug}/auth`` call and is effectively inaccessible. Mirrors the
    secret provisioning in the admin create handler (``portals_post.py``).
    """
    secret_name = _session_secret_name(portal_id)
    try:
        secretsmanager.create_secret(
            Name=secret_name,
            SecretString=secrets.token_urlsafe(32),
        )
    except secretsmanager.exceptions.ResourceExistsException:
        # Idempotent: a secret already exists for this portal id — keep it so
        # existing sessions stay valid.
        logger.info(
            "Session secret already exists, reusing it",
            extra={"portalId": portal_id},
        )
    return secret_name


def _evaluate_jsonpath(expr, data):
    """Evaluate a JSONPath expression against data, returning the first match or None."""
    matches = jsonpath_parse(expr).find(data)
    return matches[0].value if matches else None


# Portal-config keys a Template contributes when seeding a portal. The
# template's own name/description/slug/passphrase are intentionally excluded:
# name + slug come from Default Portal Config or runtime Field Mapping, and a
# template never carries a passphrase. `destinations` and `appearance` are
# handled separately (destinations become DEST# items; appearance layers with a
# selected theme). Mirrors TEMPLATE_SCALAR_STRUCTURE_KEYS in the editor store.
_TEMPLATE_SEED_KEYS = (
    "pages",
    "metadataFields",
    "accessMode",
    "allowedGroups",
    "ipAllowlist",
    "tokenBypassesPassphrase",
    "structuredPathMode",
    "captchaEnabled",
    "formSubmissionEnabled",
    "maxFileSizeBytes",
    "maxFilesPerSession",
)


def _from_dynamodb(value):
    """Recursively convert DynamoDB ``Decimal`` values to ``int``/``float``.

    Items read back through the boto3 resource client carry numbers as
    ``Decimal``. The shared structure validator requires real ``int`` page
    numbers (``isinstance(n, int)``), and ``json.dumps`` can't serialize
    ``Decimal``, so a template read from the table must be normalized before it
    is merged, validated, or persisted.
    """
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, list):
        return [_from_dynamodb(item) for item in value]
    if isinstance(value, dict):
        return {key: _from_dynamodb(item) for key, item in value.items()}
    return value


def _deep_merge(base, override):
    """Deep-merge two dicts without mutating either input.

    Nested dicts merge recursively; every other value in ``override`` (scalars,
    lists) replaces the value in ``base``. Used to layer a selected theme's
    appearance over a template's appearance.
    """
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _get_portal_template(template_id):
    """Fetch a portal Template by id (PK=PORTALTEMPLATE#{id}, SK=METADATA).

    Returns the item as a plain dict (Decimals normalized). Raises ValueError
    if the template does not exist so a misconfigured node fails loudly instead
    of silently creating an empty portal.
    """
    resp = table.get_item(Key={"PK": f"PORTALTEMPLATE#{template_id}", "SK": "METADATA"})
    item = resp.get("Item")
    if not item:
        raise ValueError(f"Portal template '{template_id}' not found")
    return _from_dynamodb(item)


def _get_portal_theme(theme_id):
    """Fetch a portal Theme by id (PK=PORTALTHEME#{id}, SK=METADATA).

    Returns the item as a plain dict (Decimals normalized). Raises ValueError
    if the theme does not exist.
    """
    resp = table.get_item(Key={"PK": f"PORTALTHEME#{theme_id}", "SK": "METADATA"})
    item = resp.get("Item")
    if not item:
        raise ValueError(f"Portal theme '{theme_id}' not found")
    return _from_dynamodb(item)


def _resolve_config_from_sources(template_id, theme_id):
    """Build a base portal config from an optional Template and/or Theme.

    Server-side mirror of the editor's create-from-template / apply-theme
    seeding (``usePortalEditorStore.initializeFromSources``) — there is no
    shared server-side expander, so the node resolves the record(s) itself. A
    Template seeds structure (pages/metadataFields/destinations), appearance and
    limits; a selected Theme's appearance is layered on top of (and overrides)
    the template's appearance. The returned dict is the *base* — callers merge
    Default Portal Config and runtime Field Mapping over it (both win).
    """
    base = {}

    if template_id:
        template = _get_portal_template(template_id)
        for key in _TEMPLATE_SEED_KEYS:
            value = template.get(key)
            if value is not None:
                base[key] = value
        destinations = template.get("destinations")
        if destinations is not None:
            base["destinations"] = destinations
        template_appearance = template.get("appearance")
        if isinstance(template_appearance, dict):
            base["appearance"] = template_appearance

    if theme_id:
        theme = _get_portal_theme(theme_id)
        theme_appearance = theme.get("appearance")
        if isinstance(theme_appearance, dict):
            # A selected theme overrides the template's look (deep-merged so a
            # partial theme still layers cleanly onto any template appearance).
            base["appearance"] = _deep_merge(
                base.get("appearance") or {}, theme_appearance
            )

    return base


def _write_destinations(portal_id, destinations):
    """Persist a portal's destinations as ``DEST#`` items and return their SKs.

    Mirrors the admin create handler's ``PortalDestinationModel`` write so a
    portal seeded from a template is actually upload-ready. Only non-None keys
    are written (the boto3 resource client would otherwise store NULL
    attributes; the PynamoDB-based admin path simply omits null attributes).
    """
    written_sks = []
    try:
        for dest in destinations:
            if not isinstance(dest, dict):
                continue
            dest_id = dest.get("destinationId") or str(uuid.uuid4())
            item = {
                "PK": f"UPLOADPORTAL#{portal_id}",
                "SK": f"DEST#{dest_id}",
                "destinationId": dest_id,
                "friendlyName": dest.get("friendlyName", ""),
                "connectorId": dest.get("connectorId", ""),
                "rootPath": dest.get("rootPath", "/"),
                "allowBrowsing": dest.get("allowBrowsing", False),
                "allowFolderCreation": dest.get("allowFolderCreation", False),
                "order": dest.get("order", 0),
                "pathSegments": dest.get("pathSegments"),
                "pageNumber": dest.get("pageNumber"),
            }
            item = {k: v for k, v in item.items() if v is not None}
            table.put_item(Item=item)
            written_sks.append(item["SK"])
    except Exception:
        # Roll back the destinations written so far so a mid-loop failure does
        # not leave a partial set behind; the caller cleans up the rest.
        for sk in written_sks:
            try:
                table.delete_item(Key={"PK": f"UPLOADPORTAL#{portal_id}", "SK": sk})
            except Exception:
                logger.warning(
                    "Cleanup: failed to delete destination", extra={"sk": sk}
                )
        raise
    return written_sks


def _cleanup_partial_portal(portal_id, slug, secret_name, dest_sks=None):
    """Best-effort teardown of a partially-created portal (create-path failure).

    Deletes any written destination items, the metadata item, the slug index,
    and the session secret so a failed create does not orphan resources.
    """
    for sk in dest_sks or []:
        try:
            table.delete_item(Key={"PK": f"UPLOADPORTAL#{portal_id}", "SK": sk})
        except Exception:
            logger.warning("Cleanup: failed to delete destination", extra={"sk": sk})
    try:
        table.delete_item(Key={"PK": f"UPLOADPORTAL#{portal_id}", "SK": "METADATA"})
    except Exception:
        logger.warning("Cleanup: failed to delete portal metadata")
    try:
        table.delete_item(Key={"PK": f"UPLOADPORTAL_SLUG#{slug}", "SK": "INDEX"})
    except Exception:
        logger.warning("Cleanup: failed to delete slug index")
    if secret_name:
        try:
            secretsmanager.delete_secret(
                SecretId=secret_name, ForceDeleteWithoutRecovery=True
            )
        except Exception:
            logger.warning("Cleanup: failed to delete session secret")


def _prepare_metadata_fields(merged):
    """Allow-list a merged portal config to known fields and hash any passphrase.

    Mirrors the admin create handler (``portals_post.py``): we never persist
    arbitrary/misspelled keys, and a passphrase is stored bcrypt-hashed (a
    plaintext passphrase would break ``portal_auth``'s ``bcrypt.checkpw``). An
    empty passphrase is normalized to ``None`` ("no passphrase").
    """
    fields = select_portal_config_fields(merged)
    if "passphrase" in fields:
        raw = fields["passphrase"]
        fields["passphrase"] = (
            bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode() if raw else None
        )
    return fields


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

    # Optional Template / Theme references (dropdowns in the node UI). A blank
    # env var / data value normalizes to None so an unset dropdown is ignored.
    template_id = (
        os.environ.get("TEMPLATE_ID") or data.get("templateId") or ""
    ).strip() or None
    theme_id = (os.environ.get("THEME_ID") or data.get("themeId") or "").strip() or None

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

    # Resolve an optional Template/Theme reference into a base config, then
    # merge with precedence: template/theme base < Default Portal Config <
    # runtime field mapping (later layers win). Mirrors the editor's
    # create-from-template / apply-theme seeding order.
    source_base = _resolve_config_from_sources(template_id, theme_id)
    merged = {**source_base, **default_portal_config, **mapped_values}

    # Destinations (e.g. seeded from a template) are written as DEST# items on
    # create; they are not part of the metadata allow-list. Default Portal
    # Config / field mapping may override the template's destinations.
    resolved_destinations = merged.get("destinations") or []

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

    # Validate with the shared rules (same as the admin API / deploy-time check).
    # On update, name may be unchanged/absent so validate leniently; on create
    # require name + slug.
    validation_errors = validate_portal_config(merged, partial=bool(slug_item))
    if validation_errors:
        raise ValueError(
            "Invalid portal configuration: " + "; ".join(validation_errors)
        )

    # Allow-list known fields and bcrypt-hash any passphrase before persisting.
    prepared = _prepare_metadata_fields(merged)

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

        for field_key, field_val in prepared.items():
            safe_key = field_key.replace("-", "_")
            update_expr_parts.append(f"#{safe_key} = :{safe_key}")
            expr_names[f"#{safe_key}"] = field_key
            expr_values[f":{safe_key}"] = field_val

        # Atomically increment accessVersion when access-control fields are mutated
        has_access_control_change = bool(ACCESS_CONTROL_FIELDS & prepared.keys())
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
            # Slug claimed successfully — provision the session secret, then
            # write metadata. The session secret MUST exist before the portal
            # is usable: the portal auth endpoint signs session JWTs with it, so
            # a portal without it fails every access with a 500.
            secret_name = _create_session_secret(portal_id)
            metadata_item = {
                "PK": f"UPLOADPORTAL#{portal_id}",
                "SK": "METADATA",
                "portalId": portal_id,
                "slug": slug,
                "GSI1_PK": "UPLOADPORTALS",
                "GSI1_SK": now,
                "isActive": True,
                "createdAt": now,
                "updatedAt": now,
                "accessVersion": 1,
                **prepared,
            }
            try:
                table.put_item(Item=metadata_item)
            except Exception as meta_exc:
                # Best-effort cleanup: remove the slug index and session secret
                # so they aren't orphaned.
                # Guard: a concurrent request may have already fallen through the
                # ConditionalCheckFailedException path and written metadata for
                # this portal.  If metadata now exists, the slug index and secret
                # are valid and must NOT be deleted.
                try:
                    guard_resp = table.get_item(
                        Key={"PK": f"UPLOADPORTAL#{portal_id}", "SK": "METADATA"},
                        ConsistentRead=True,
                    )
                    if not guard_resp.get("Item"):
                        table.delete_item(
                            Key={"PK": f"UPLOADPORTAL_SLUG#{slug}", "SK": "INDEX"}
                        )
                        try:
                            secretsmanager.delete_secret(
                                SecretId=secret_name,
                                ForceDeleteWithoutRecovery=True,
                            )
                        except Exception as secret_cleanup_exc:
                            logger.warning(
                                "Failed to clean up session secret after metadata write failure",
                                extra={
                                    "portalId": portal_id,
                                    "cleanupError": str(secret_cleanup_exc),
                                },
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
            # Seed destinations (Scope B) from the resolved config so a portal
            # created from a template is upload-ready. Create-path only: an
            # update leaves an existing portal's destinations untouched. On
            # failure, tear down the just-created portal to avoid orphans.
            if resolved_destinations:
                try:
                    _write_destinations(portal_id, resolved_destinations)
                except Exception as dest_exc:
                    _cleanup_partial_portal(portal_id, slug, secret_name)
                    raise dest_exc
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
