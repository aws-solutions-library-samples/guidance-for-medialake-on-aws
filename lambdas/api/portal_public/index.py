"""
Portal Public API Lambda Handler.

Handles all public-facing portal routes:
  GET  /<slug>                          – portal details
  POST /<slug>/upload                   – initiate upload
  POST /<slug>/upload/multipart/sign    – sign a multipart part
  POST /<slug>/upload/multipart/complete – complete multipart upload
  POST /<slug>/upload/multipart/abort   – abort multipart upload
  GET  /<slug>/browse                   – browse destination files
  POST /<slug>/folder                   – create folder
"""

import json
import os
import re
from decimal import Decimal
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import (
    APIGatewayRestResolver,
    CORSConfig,
    Response,
)
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.dynamodb.conditions import Key
from botocore.config import Config
from botocore.exceptions import ClientError

logger = Logger(service="portal-public-api", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="portal-public-api")
metrics = Metrics(namespace="medialake", service="portal-public-api")

SYSTEM_SETTINGS_TABLE_NAME = os.environ.get("SYSTEM_SETTINGS_TABLE_NAME", "")
MEDIALAKE_CONNECTOR_TABLE = os.environ.get("MEDIALAKE_CONNECTOR_TABLE", "")
CLOUDFRONT_DOMAIN = os.environ.get("CLOUDFRONT_DOMAIN", "")
RESOURCE_PREFIX = os.environ.get("RESOURCE_PREFIX", "")

dynamodb = boto3.resource("dynamodb")

# --- S3 client cache (from post_upload/index.py) ---
_SIGV4_CFG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "virtual"},
    connect_timeout=5,
    read_timeout=60,
)
_ENDPOINT_TMPL = "https://s3.{region}.amazonaws.com"
_S3_CLIENT_CACHE: Dict[str, boto3.client] = {}

# --- Upload constants (from post_upload/index.py) ---
DEFAULT_EXPIRATION = 21600
ALLOWED_CONTENT_TYPES = [
    "audio/*",
    "video/*",
    "image/*",
    "application/x-mpegURL",
    "application/dash+xml",
]
FILENAME_REGEX = r"^[a-zA-Z0-9!\-_.*'() @\$+,;=&:]+$"

# --- DynamoDB key constants (from portal_auth/index.py) ---
PORTAL_PK_PREFIX = "UPLOADPORTAL#"
PORTAL_SLUG_PK_PREFIX = "UPLOADPORTAL_SLUG#"
METADATA_SK = "METADATA"
DEST_SK_PREFIX = "DEST#"
INDEX_SK = "INDEX"


def _json_default(value):
    """JSON serializer default hook for the public API responses.

    boto3's DynamoDB *resource* deserializes every Number attribute into a
    ``decimal.Decimal``. The previous ``default=str`` hook stringified those
    into quoted JSON strings (e.g. ``"680"``), which broke the frontend: the
    public ``UploadPortalPage`` passes ``appearance.layout.cardMaxWidth``
    straight into MUI's ``sx`` ``maxWidth``. A numeric ``680`` renders as
    ``max-width: 680px``, but the string ``"680"`` is invalid CSS and the
    browser silently drops it (``max-width: none``) — the reported
    "max width setting doesn't work" bug. The same stringification affected
    every other numeric appearance field (``cardBorderRadius``,
    ``cardPadding``, ``pageVerticalPadding``, ``logoSize``, ``bannerHeight``,
    ``baseFontSize``, ``headingFontWeight``) plus ``maxFileSizeBytes`` /
    ``maxFilesPerSession``.

    Convert ``Decimal`` to a native ``int`` (integral values) or ``float`` so
    the JSON carries real numbers; fall back to ``str`` for any other
    non-JSON-native type to preserve the previous behavior.
    """
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return str(value)


cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=[
        "Content-Type",
        "X-Amz-Date",
        "Authorization",
        "X-Api-Key",
        "X-Amz-Security-Token",
        "X-Portal-Session",
    ],
    expose_headers=["X-Request-Id"],
    max_age=300,
)

app = APIGatewayRestResolver(
    serializer=lambda x: json.dumps(x, default=_json_default),
    strip_prefixes=["/portal"],
    cors=cors_config,
)


# ---------------------------------------------------------------------------
# S3 utilities (copied from post_upload/index.py)
# ---------------------------------------------------------------------------


def normalize_prefix(prefix: str) -> str:
    """Normalize a prefix string to ensure consistent formatting."""
    if not prefix:
        return ""
    normalized = prefix.strip()
    if not normalized:
        return ""
    if not normalized.endswith("/"):
        normalized += "/"
    return normalized


def parse_object_prefixes(object_prefix) -> List[str]:
    """Parse objectPrefix from connector configuration into a list of normalized prefixes."""
    if object_prefix is None:
        return []
    if isinstance(object_prefix, str):
        normalized = normalize_prefix(object_prefix)
        return [normalized] if normalized else []
    if isinstance(object_prefix, list):
        return [
            normalize_prefix(p)
            for p in object_prefix
            if isinstance(p, str) and normalize_prefix(p)
        ]
    return []


def validate_prefix_access(requested_path: str, allowed_prefixes: List[str]) -> bool:
    """Validate that a requested path is within the allowed prefix boundaries."""
    if not allowed_prefixes:
        return True
    if requested_path is None:
        requested_path = ""
    normalized_requested_path = normalize_prefix(requested_path)
    for allowed_prefix in allowed_prefixes:
        if normalized_requested_path.startswith(normalize_prefix(allowed_prefix)):
            return True
    return False


def _get_s3_client_for_bucket(bucket: str) -> boto3.client:
    """Return an S3 client pinned to the bucket's actual region (cached)."""
    generic = _S3_CLIENT_CACHE.setdefault(
        "us-east-1",
        boto3.client("s3", region_name="us-east-1", config=_SIGV4_CFG),
    )
    try:
        region = (
            generic.get_bucket_location(Bucket=bucket).get("LocationConstraint")
            or "us-east-1"
        )
    except generic.exceptions.NoSuchBucket:
        raise ValueError(f"S3 bucket {bucket!r} does not exist")

    if region not in _S3_CLIENT_CACHE:
        _S3_CLIENT_CACHE[region] = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=_ENDPOINT_TMPL.format(region=region),
            config=_SIGV4_CFG,
        )
    return _S3_CLIENT_CACHE[region]


def is_multipart_upload_required(file_size: int) -> bool:
    """Determine if multipart upload is required based on file size (>100 MB)."""
    return file_size > 100 * 1024 * 1024


def generate_presigned_post_url(
    bucket: str,
    key: str,
    content_type: str,
    expiration: int = DEFAULT_EXPIRATION,
    metadata: dict | None = None,
    max_size_bytes: int | None = None,
) -> Dict[str, Any]:
    """Generate a presigned POST URL for the S3 object."""
    s3_client = _get_s3_client_for_bucket(bucket)
    _100MB = 100 * 1024 * 1024
    try:
        max_size_bytes = int(max_size_bytes) if max_size_bytes is not None else None
    except (TypeError, ValueError):
        max_size_bytes = None
    upper = (
        min(_100MB, max_size_bytes) if max_size_bytes and max_size_bytes > 0 else _100MB
    )
    fields = {"Content-Type": content_type}
    conditions = [
        {"bucket": bucket},
        {"key": key},
        ["content-length-range", 1, upper],
        {"Content-Type": content_type},
    ]
    if metadata:
        for k, v in metadata.items():
            header = f"x-amz-meta-{k}"
            fields[header] = v
            conditions.append(["starts-with", f"${header}", ""])
    return s3_client.generate_presigned_post(
        Bucket=bucket,
        Key=key,
        Fields=fields,
        Conditions=conditions,
        ExpiresIn=expiration,
    )


def create_multipart_upload(
    bucket: str, key: str, content_type: str, metadata: Dict[str, str] | None = None
) -> str:
    """Initiate a multipart upload and return the upload ID."""
    s3_client = _get_s3_client_for_bucket(bucket)
    kwargs: Dict[str, Any] = {
        "Bucket": bucket,
        "Key": key,
        "ContentType": content_type,
    }
    if metadata:
        kwargs["Metadata"] = metadata
    response = s3_client.create_multipart_upload(**kwargs)
    return response["UploadId"]


# ---------------------------------------------------------------------------
# Portal metadata → automation namespace resolution
# ---------------------------------------------------------------------------
#
# See .kiro/specs/multi-page-upload-portals/portal-metadata-automation-design.md
#
# The client submits raw form values keyed by each field's slug. The SERVER is
# the source of truth for automation: it (1) drops any client-supplied `ml-*`
# key (directives are never trusted from the client), (2) resolves the
# collection-picker field's value against the portal's SAVED allow-list and
# unions the fixed ids into the `ml-collection-ids` directive, (3) prefixes the
# remaining user fields with `ml-usr-`, and (4) stamps provenance. A user
# field's slug matches ^[a-z0-9_]+$ (no hyphen) so it can never collide with a
# bare `ml-` directive.

ML_DIRECTIVE_PREFIX = "ml-"
ML_USER_PREFIX = "ml-usr-"
COLLECTION_IDS_DIRECTIVE = "ml-collection-ids"
SOURCE_DIRECTIVE = "ml-source"
PORTAL_ID_DIRECTIVE = "ml-portal-id"
PORTAL_SOURCE_VALUE = "upload-portal"


def _slug(label: Any) -> str:
    """Slugify a label exactly like the frontend `slug()` helper: lowercase,
    non-alphanumeric runs → `_`, trim leading/trailing `_`."""
    s = re.sub(r"[^a-z0-9]+", "_", str(label).strip().lower())
    return s.strip("_")


def _resolve_portal_metadata(
    portal: Dict[str, Any], portal_id: str, submitted: Dict[str, Any] | None
) -> Dict[str, str]:
    """Translate client-submitted form metadata into the server-trusted S3
    user-metadata namespace.

    Returns the dict of metadata keys/values to attach as `x-amz-meta-*`.
    """
    submitted = submitted or {}
    fields = portal.get("metadataFields") or []

    # Locate the (at most one) collection-picker field and its submitted key.
    picker = next(
        (f for f in fields if (f or {}).get("role") == "collection-picker"), None
    )
    picker_key = _slug(picker["label"]) if picker and picker.get("label") else None

    result: Dict[str, str] = {}

    # User fields → ml-usr-*, dropping any client-sent directive keys and the
    # collection-picker key (consumed into the directive below).
    for key, value in submitted.items():
        key_str = str(key)
        if key_str.lower().startswith(ML_DIRECTIVE_PREFIX):
            logger.warning(
                "Dropping client-supplied reserved metadata key: %s", key_str
            )
            continue
        if picker_key and key_str == picker_key:
            continue
        if value is None:
            continue
        result[f"{ML_USER_PREFIX}{key_str}"] = str(value)

    # Resolve collection ids server-side against the saved allow-list.
    if picker:
        cfg = picker.get("roleConfig") or {}
        allowed_ids = {
            c.get("id")
            for c in (cfg.get("allowedCollections") or [])
            if isinstance(c, dict) and c.get("id")
        }
        raw = submitted.get(picker_key, "") if picker_key else ""
        # The client comma-joins multi-select arrays (", "); split + trim.
        chosen = [s.strip() for s in str(raw).split(",") if s.strip()]
        valid = [cid for cid in chosen if cid in allowed_ids]
        if len(valid) != len(chosen):
            dropped = [cid for cid in chosen if cid not in allowed_ids]
            logger.warning(
                "Dropped collection ids not in portal allow-list: %s", dropped
            )
        fixed = [c for c in (cfg.get("fixedCollectionIds") or []) if c]
        # Union, preserving order and de-duplicating.
        final_ids = list(dict.fromkeys([*valid, *fixed]))
        if final_ids:
            result[COLLECTION_IDS_DIRECTIVE] = ",".join(final_ids)

    # Provenance directives (always present for portal uploads).
    result[SOURCE_DIRECTIVE] = PORTAL_SOURCE_VALUE
    result[PORTAL_ID_DIRECTIVE] = str(portal_id)
    return result


# ---------------------------------------------------------------------------
# DynamoDB helpers
# ---------------------------------------------------------------------------


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


def _get_destination(portal_id, destination_id):
    """Fetch a single destination record for a portal."""
    table = dynamodb.Table(SYSTEM_SETTINGS_TABLE_NAME)
    resp = table.get_item(
        Key={
            "PK": f"{PORTAL_PK_PREFIX}{portal_id}",
            "SK": f"{DEST_SK_PREFIX}{destination_id}",
        }
    )
    return resp.get("Item")


def _get_connector(connector_id):
    """Fetch connector details from the connector table."""
    table = dynamodb.Table(MEDIALAKE_CONNECTOR_TABLE)
    resp = table.get_item(Key={"id": connector_id})
    return resp.get("Item")


# ---------------------------------------------------------------------------
# Path / upload helpers
# ---------------------------------------------------------------------------


def _build_s3_key(root_path, path, filename):
    """Build an S3 key from root_path, path, and filename."""
    parts = [p.strip("/") for p in [root_path, path, filename] if p and p.strip("/")]
    key = "/".join(parts)
    # Normalize double slashes
    while "//" in key:
        key = key.replace("//", "/")
    return key


def _validate_path_within_root(path, root_path):
    """Return True if normalized path starts with normalized root_path."""
    return normalize_prefix(path).startswith(normalize_prefix(root_path))


def _sanitize_path(raw: str) -> str | None:
    """Reject traversal segments (.., .) and double slashes. Returns stripped string or None."""
    stripped = raw.strip()
    if "//" in stripped:
        return None
    for segment in stripped.split("/"):
        if segment in ("..", "."):
            return None
    return stripped


def _validate_structured_path(path_segments, constructed_path, root_path):
    """Validate that path segments match their regex constraints."""
    normalized_root = normalize_prefix(root_path)
    normalized_path = normalize_prefix(constructed_path)
    relative = normalized_path
    if normalized_root and normalized_path.startswith(normalized_root):
        relative = normalized_path[len(normalized_root) :]
    segments = [s for s in relative.split("/") if s]
    folder_segments = segments[:-1] if segments else segments
    for seg_def in path_segments:
        position = seg_def.get("position", 0)
        regex = seg_def.get("regex", ".*")
        if position >= len(folder_segments):
            return False, f"Path segment at position {position} is missing"
        if not re.fullmatch(regex, folder_segments[position]):
            return (
                False,
                f"Path segment '{folder_segments[position]}' at position {position} does not match pattern '{regex}'",
            )
    return True, None


def _error(status_code, message):
    """Return a JSON error Response."""
    return Response(
        status_code=status_code,
        content_type="application/json",
        body=json.dumps({"message": message}),
    )


def _calculate_part_size(file_size):
    """Calculate optimal part size and total parts for multipart upload."""
    GB = 1024 * 1024 * 1024
    MB = 1024 * 1024

    if file_size >= 100 * GB:
        part_size = 500 * MB
    elif file_size >= 10 * GB:
        part_size = 200 * MB
    elif file_size >= 1 * GB:
        part_size = 100 * MB
    elif file_size >= 100 * MB:
        part_size = 50 * MB
    else:
        part_size = 5 * MB

    total_parts = (file_size + part_size - 1) // part_size

    if total_parts > 10000:
        part_size = (file_size + 9999) // 10000
        part_size = ((part_size + MB - 1) // MB) * MB
        total_parts = (file_size + part_size - 1) // part_size

    return part_size, total_parts


def _validate_content_type(content_type):
    """Return True if content_type matches any allowed pattern."""
    for allowed in ALLOWED_CONTENT_TYPES:
        if allowed.endswith("*"):
            if content_type.startswith(allowed[:-1]):
                return True
        elif content_type == allowed:
            return True
    return False


# ---------------------------------------------------------------------------
# Appearance asset resolution
# ---------------------------------------------------------------------------


def _resolve_appearance_asset_urls(appearance):
    """Resolve the read-time-only `bannerUrl`/`faviconUrl` from their stored S3
    keys so the public portal page can render the admin-configured banner and
    favicon (Requirement 7.7).

    The visual editor persists `bannerS3Key` and `faviconS3Key` inside
    `appearance.branding`; the resolved URLs are intentionally NOT stored (they
    are derived from the CloudFront domain at read time, exactly like the
    portal `logoUrl`). Without this resolution the public renderer never
    receives a `bannerUrl`/`faviconUrl` and silently drops the banner/favicon
    even though the admin configured them.

    Returns a shallow copy of `appearance` with the URLs populated; passes the
    value through unchanged when there is no appearance, no branding map, or no
    CloudFront domain configured.
    """
    if not isinstance(appearance, dict):
        return appearance

    branding = appearance.get("branding")
    if not isinstance(branding, dict) or not CLOUDFRONT_DOMAIN:
        return appearance

    resolved_branding = dict(branding)
    banner_key = branding.get("bannerS3Key")
    if banner_key:
        resolved_branding["bannerUrl"] = f"https://{CLOUDFRONT_DOMAIN}/{banner_key}"
    favicon_key = branding.get("faviconS3Key")
    if favicon_key:
        resolved_branding["faviconUrl"] = f"https://{CLOUDFRONT_DOMAIN}/{favicon_key}"

    resolved = dict(appearance)
    resolved["branding"] = resolved_branding
    return resolved


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/<slug>")
@tracer.capture_method
def get_portal(slug: str):
    """Return portal details and destinations (public-safe fields only)."""
    portal_id, portal = _get_portal_by_slug(slug)
    if not portal:
        return _error(404, "Portal not found")

    table = dynamodb.Table(SYSTEM_SETTINGS_TABLE_NAME)
    dest_resp = table.query(
        KeyConditionExpression=Key("PK").eq(f"{PORTAL_PK_PREFIX}{portal_id}")
        & Key("SK").begins_with(DEST_SK_PREFIX)
    )

    destinations = []
    for item in dest_resp.get("Items", []):
        destinations.append(
            {
                "destinationId": item.get("destinationId"),
                "friendlyName": item.get("friendlyName"),
                "allowBrowsing": item.get("allowBrowsing", False),
                "allowFolderCreation": item.get("allowFolderCreation", False),
                "order": item.get("order", 0),
                "pathSegments": item.get("pathSegments", []),
                "pageNumber": item.get("pageNumber"),
            }
        )

    logo_url = None
    logo_key = portal.get("logoS3Key")
    if logo_key and CLOUDFRONT_DOMAIN:
        logo_url = f"https://{CLOUDFRONT_DOMAIN}/{logo_key}"

    return {
        "portalId": portal_id,
        "name": portal.get("name"),
        "description": portal.get("description"),
        "logoUrl": logo_url,
        "destinations": destinations,
        "metadataFields": portal.get("metadataFields", []),
        "maxFileSizeBytes": portal.get("maxFileSizeBytes"),
        "maxFilesPerSession": portal.get("maxFilesPerSession"),
        "structuredPathMode": portal.get("structuredPathMode", False),
        "captchaEnabled": portal.get("captchaEnabled", False),
        "appearance": _resolve_appearance_asset_urls(portal.get("appearance")),
        "pages": portal.get("pages", []),
    }


@app.post("/<slug>/upload")
@tracer.capture_method
def post_upload(slug: str):
    """Initiate a single-part or multipart upload."""
    body = app.current_event.json_body or {}
    destination_id = body.get("destinationId")
    filename = body.get("filename")
    content_type = body.get("contentType")
    file_size = body.get("fileSize")
    path = body.get("path", "")
    path = _sanitize_path(path)
    if path is None:
        return _error(400, "Invalid path: traversal segments are not allowed")
    metadata = body.get("metadata") or {}
    file_count = body.get("fileCount", 1)

    if not filename:
        return _error(400, "filename is required")
    if not content_type:
        return _error(400, "contentType is required")
    if file_size is None:
        return _error(400, "fileSize is required")
    if not isinstance(file_size, (int, float)) or file_size <= 0:
        return _error(400, "fileSize must be a positive number")
    if not destination_id:
        return _error(400, "destinationId is required")

    portal_id, portal = _get_portal_by_slug(slug)
    if not portal:
        return _error(404, "Portal not found")

    if (
        not isinstance(file_count, int)
        or isinstance(file_count, bool)
        or file_count < 1
    ):
        return _error(400, "fileCount must be a positive integer")

    max_files = portal.get("maxFilesPerSession")
    if max_files and file_count > max_files:
        return _error(
            400,
            f"File count {file_count} exceeds maximum {max_files} files per session",
        )

    destination = _get_destination(portal_id, destination_id)
    if not destination:
        return _error(400, "Destination not found")

    if not _validate_content_type(content_type):
        return _error(400, f"Content type '{content_type}' is not allowed")

    max_size = portal.get("maxFileSizeBytes")
    if max_size and file_size > max_size:
        return _error(400, f"File size {file_size} exceeds maximum {max_size}")

    if not re.match(FILENAME_REGEX, filename):
        return _error(400, "Invalid filename")

    s3_key = _build_s3_key(destination["rootPath"], path, filename)

    if not _validate_path_within_root(s3_key, destination["rootPath"]):
        return _error(400, "Path is outside the allowed root")

    if portal.get("structuredPathMode") and destination.get("pathSegments"):
        valid, err_msg = _validate_structured_path(
            destination["pathSegments"], s3_key, destination["rootPath"]
        )
        if not valid:
            return _error(400, err_msg)

    connector = _get_connector(destination["connectorId"])
    if not connector:
        return _error(500, "Connector not found")

    bucket = connector["storageIdentifier"]

    # Resolve the client-submitted form metadata into the server-trusted
    # namespace (ml-usr-* user fields, ml-collection-ids directive validated
    # against the saved allow-list, provenance). See _resolve_portal_metadata.
    s3_metadata = _resolve_portal_metadata(portal, portal_id, metadata)

    if is_multipart_upload_required(file_size):
        upload_id = create_multipart_upload(
            bucket, s3_key, content_type, metadata=s3_metadata or None
        )
        part_size, total_parts = _calculate_part_size(file_size)
        return {
            "multipart": True,
            "bucket": bucket,
            "key": s3_key,
            "uploadId": upload_id,
            "partSize": part_size,
            "totalParts": total_parts,
        }

    presigned_post = generate_presigned_post_url(
        bucket,
        s3_key,
        content_type,
        metadata=s3_metadata or None,
        max_size_bytes=portal.get("maxFileSizeBytes"),
    )
    return {
        "multipart": False,
        "presignedPost": {
            "url": presigned_post["url"],
            "fields": presigned_post["fields"],
        },
    }


@app.post("/<slug>/upload/multipart/sign")
@tracer.capture_method
def post_multipart_sign(slug: str):
    """Generate a presigned URL for a single multipart part."""
    body = app.current_event.json_body or {}
    destination_id = body.get("destinationId")
    upload_id = body.get("uploadId")
    key = body.get("key")
    part_number = body.get("partNumber")

    if not destination_id:
        return _error(400, "destinationId is required")
    if not upload_id:
        return _error(400, "uploadId is required")
    if not key:
        return _error(400, "key is required")
    if part_number is None:
        return _error(400, "partNumber is required")
    if (
        not isinstance(part_number, int)
        or isinstance(part_number, bool)
        or part_number < 1
    ):
        return _error(400, "partNumber must be a positive integer")

    portal_id, portal = _get_portal_by_slug(slug)
    if not portal:
        return _error(404, "Portal not found")

    destination = _get_destination(portal_id, destination_id)
    if not destination:
        return _error(400, "Destination not found")

    key = _sanitize_path(key)
    if key is None:
        return _error(400, "Invalid key: traversal segments are not allowed")

    if not _validate_path_within_root(key, destination["rootPath"]):
        return _error(400, "Key is outside the allowed root")

    connector = _get_connector(destination["connectorId"])
    if not connector:
        return _error(500, "Connector not found")

    bucket = connector["storageIdentifier"]
    s3_client = _get_s3_client_for_bucket(bucket)
    url = s3_client.generate_presigned_url(
        "upload_part",
        Params={
            "Bucket": bucket,
            "Key": key,
            "UploadId": upload_id,
            "PartNumber": part_number,
        },
        ExpiresIn=DEFAULT_EXPIRATION,
    )
    return {
        "presignedUrl": url,
        "partNumber": part_number,
        "expiresIn": DEFAULT_EXPIRATION,
    }


@app.post("/<slug>/upload/multipart/complete")
@tracer.capture_method
def post_multipart_complete(slug: str):
    """Complete a multipart upload."""
    body = app.current_event.json_body or {}
    destination_id = body.get("destinationId")
    upload_id = body.get("uploadId")
    key = body.get("key")
    parts = body.get("parts", [])

    if not destination_id:
        return _error(400, "destinationId is required")
    if not upload_id:
        return _error(400, "uploadId is required")
    if not key:
        return _error(400, "key is required")
    if not isinstance(parts, list) or not parts:
        return _error(400, "parts is required and must be a non-empty list")

    portal_id, portal = _get_portal_by_slug(slug)
    if not portal:
        return _error(404, "Portal not found")

    destination = _get_destination(portal_id, destination_id)
    if not destination:
        return _error(400, "Destination not found")

    key = _sanitize_path(key)
    if key is None:
        return _error(400, "Invalid key: traversal segments are not allowed")

    if not _validate_path_within_root(key, destination["rootPath"]):
        return _error(400, "Key is outside the allowed root")

    connector = _get_connector(destination["connectorId"])
    if not connector:
        return _error(500, "Connector not found")

    bucket = connector["storageIdentifier"]
    s3_client = _get_s3_client_for_bucket(bucket)
    s3_client.complete_multipart_upload(
        Bucket=bucket,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={"Parts": parts},
    )

    max_size = portal.get("maxFileSizeBytes")
    if max_size and max_size > 0:
        try:
            head = s3_client.head_object(Bucket=bucket, Key=key)
            content_length = head["ContentLength"]
            if content_length > max_size:
                s3_client.delete_object(Bucket=bucket, Key=key)
                return _error(
                    400,
                    f"Uploaded file size {content_length} bytes exceeds the portal maximum of {max_size} bytes. The upload has been removed.",
                )
        except ClientError as e:
            logger.error(
                "HEAD after multipart complete failed",
                error=str(e),
                bucket=bucket,
                key=key,
            )
            try:
                s3_client.delete_object(Bucket=bucket, Key=key)
            except ClientError:
                logger.error(
                    "Best-effort cleanup failed after HEAD error",
                    bucket=bucket,
                    key=key,
                )
            return _error(
                500,
                "Upload size verification failed. The upload has been removed as a precaution.",
            )

    return {"location": f"s3://{bucket}/{key}", "bucket": bucket, "key": key}


@app.post("/<slug>/upload/multipart/abort")
@tracer.capture_method
def post_multipart_abort(slug: str):
    """Abort a multipart upload."""
    body = app.current_event.json_body or {}
    destination_id = body.get("destinationId")
    upload_id = body.get("uploadId")
    key = body.get("key")

    if not destination_id:
        return _error(400, "destinationId is required")
    if not upload_id:
        return _error(400, "uploadId is required")
    if not key:
        return _error(400, "key is required")

    portal_id, portal = _get_portal_by_slug(slug)
    if not portal:
        return _error(404, "Portal not found")

    destination = _get_destination(portal_id, destination_id)
    if not destination:
        return _error(400, "Destination not found")

    key = _sanitize_path(key)
    if key is None:
        return _error(400, "Invalid key: traversal segments are not allowed")

    if not _validate_path_within_root(key, destination["rootPath"]):
        return _error(400, "Key is outside the allowed root")

    connector = _get_connector(destination["connectorId"])
    if not connector:
        return _error(500, "Connector not found")

    bucket = connector["storageIdentifier"]
    s3_client = _get_s3_client_for_bucket(bucket)
    try:
        s3_client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchUpload":
            raise
    return {"message": "Multipart upload aborted"}


@app.get("/<slug>/browse")
@tracer.capture_method
def get_browse(slug: str):
    """Browse files in a destination prefix."""
    params = app.current_event.query_string_parameters or {}
    destination_id = params.get("destinationId")
    prefix = params.get("prefix")
    continuation_token = params.get("continuationToken")

    portal_id, portal = _get_portal_by_slug(slug)
    if not portal:
        return _error(404, "Portal not found")

    destination = _get_destination(portal_id, destination_id)
    if not destination:
        return _error(400, "Destination not found")

    if not destination.get("allowBrowsing"):
        return _error(403, "Browsing is not allowed for this destination")

    if not prefix:
        prefix = destination["rootPath"]
    else:
        prefix = _sanitize_path(prefix)
        if prefix is None:
            return _error(403, "Invalid prefix: traversal segments are not allowed")

    if not _validate_path_within_root(prefix, destination["rootPath"]):
        return _error(403, "Prefix is outside the allowed root")

    connector = _get_connector(destination["connectorId"])
    if not connector:
        return _error(500, "Connector not found")

    bucket = connector["storageIdentifier"]
    s3_client = _get_s3_client_for_bucket(bucket)

    list_params = {
        "Bucket": bucket,
        "Prefix": normalize_prefix(prefix),
        "Delimiter": "/",
        "MaxKeys": 1000,
    }
    if continuation_token:
        list_params["ContinuationToken"] = continuation_token

    response = s3_client.list_objects_v2(**list_params)

    return {
        "commonPrefixes": [p["Prefix"] for p in response.get("CommonPrefixes", [])],
        "objects": [
            {
                "key": o["Key"],
                "size": o["Size"],
                "lastModified": o["LastModified"].isoformat(),
            }
            for o in response.get("Contents", [])
        ],
        "prefix": prefix,
        "isTruncated": response.get("IsTruncated", False),
        "nextContinuationToken": response.get("NextContinuationToken"),
    }


@app.post("/<slug>/folder")
@tracer.capture_method
def post_folder(slug: str):
    """Create a folder (zero-byte object) in a destination."""
    body = app.current_event.json_body or {}
    destination_id = body.get("destinationId")
    path = body.get("path", "")

    portal_id, portal = _get_portal_by_slug(slug)
    if not portal:
        return _error(404, "Portal not found")

    destination = _get_destination(portal_id, destination_id)
    if not destination:
        return _error(400, "Destination not found")

    if not destination.get("allowFolderCreation"):
        return _error(403, "Folder creation is not allowed for this destination")

    path = _sanitize_path(path)
    if path is None:
        return _error(403, "Invalid path: traversal segments are not allowed")

    if not path.endswith("/"):
        path += "/"

    if not _validate_path_within_root(path, destination["rootPath"]):
        return _error(403, "Path is outside the allowed root")

    connector = _get_connector(destination["connectorId"])
    if not connector:
        return _error(500, "Connector not found")

    bucket = connector["storageIdentifier"]
    s3_client = _get_s3_client_for_bucket(bucket)
    s3_client.put_object(Bucket=bucket, Key=path, Body=b"")
    return {"path": path, "message": "Folder created"}


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Main Lambda handler for Portal Public API."""
    return app.resolve(event, context)
