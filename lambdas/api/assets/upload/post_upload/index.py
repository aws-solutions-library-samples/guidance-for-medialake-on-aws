import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.validation import validate
from botocore.config import Config
from botocore.exceptions import ConnectTimeoutError, ReadTimeoutError
from pydantic import BaseModel, Field, validator

# Initialize AWS X-Ray, metrics, and logger
tracer = Tracer(service="upload-service")
metrics = Metrics(namespace="upload-service")
logger = Logger(service="upload-api", level=os.getenv("LOG_LEVEL", "WARNING"))

# Initialize DynamoDB and S3
dynamodb = boto3.resource("dynamodb")

# Regional S3 client configuration for better cross-region support
_SIGV4_CFG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "virtual"},
    connect_timeout=5,
    read_timeout=60,  # Longer timeout for multipart operations
)

_ENDPOINT_TMPL = "https://s3.{region}.amazonaws.com"
_S3_CLIENT_CACHE: Dict[str, boto3.client] = {}  # {region → client}

# Define constants
# 6 hours — large files (500GB) with many parts need longer-lived URLs
DEFAULT_EXPIRATION = 21600
MAX_COLLECTIONS_PER_UPLOAD = int(os.getenv("MAX_COLLECTIONS_PER_UPLOAD", "50"))

# Collection directive constants (§6.3, §10.2)
ML_SOURCE_KEY = "ml-source"
ML_COLLECTION_IDS_KEY = "ml-collection-ids"
ML_USER_ID_KEY = "ml-user-id"
ML_OVERFLOW_KEY = "ml-collection-overflow"
UPLOAD_SOURCE_VALUE = "upload"

# S3 user-metadata budget (§6.5)
SAFE_INLINE_BUDGET = 1536  # leave headroom for key names within S3's 2 KB limit

# Upload directives table (overflow side-records, §6.5, §10.5)
UPLOAD_DIRECTIVES_TABLE_NAME = os.getenv("UPLOAD_DIRECTIVES_TABLE_NAME", "")
DIRECTIVE_TTL_SECONDS = 24 * 60 * 60  # ~24h

ALLOWED_CONTENT_TYPES = [
    "audio/*",
    "video/*",
    "image/*",
    "application/x-mpegURL",  # HLS
    "application/dash+xml",  # MPEG-DASH
]
# S3-compatible filename regex.
# Allows: alphanumeric, S3 safe chars (!-_.*'()), and chars that require
# URL-encoding but are fully supported (space @$+,;=&:).
# Blocks: control chars and S3 "characters to avoid" (\{}^`~|%<>"#[])
FILENAME_REGEX = r"^[a-zA-Z0-9!\-_.*'() @\$+,;=&:]+$"

"""
TESTING RECOMMENDATIONS FOR MULTIPART UPLOADS:

Testing Multipart Uploads:
- Use files > 100MB to trigger multipart upload flow
- Verify PUT method is used in presigned URLs via CloudWatch logs

Expected Log Output for Successful Multipart Flow:
1. "Multipart upload required" with file details
2. "Total parts calculated" with part size and count
3. "Initiating multipart upload" with bucket, key, region
4. "Multipart upload initiated successfully" with upload_id
5. "Generating presigned URLs for parts" with total parts
6. "Generating PUT presigned URL for part X" for each part
7. "All presigned URLs generated successfully"
8. "Multipart upload response prepared"

Expected Log Output for Successful Single-Part Flow:
1. "Single-part upload will be used" with file details
2. "Generated presigned POST URL" with bucket, key, expiration

Verification:
- Check CloudWatch Logs for debug statements showing PUT method
- Monitor metrics: MultipartUploadCreated, MultipartUploadFileSize
- Reference: Uppy 5.0 AWS S3 plugin documentation for multipart requirements
"""

# Schema for request validation
request_schema = {
    "type": "object",
    "properties": {
        "connector_id": {"type": "string"},
        "filename": {"type": "string", "pattern": FILENAME_REGEX},
        "content_type": {"type": "string"},
        "file_size": {"type": "integer", "minimum": 1},
        "path": {"type": "string", "default": ""},
        "collection_ids": {"type": "array", "items": {"type": "string"}, "default": []},
    },
    "required": ["connector_id", "filename", "content_type", "file_size"],
}


class RequestBody(BaseModel):
    connector_id: str
    filename: str
    content_type: str
    file_size: int = Field(gt=0)
    path: str = ""
    collection_ids: List[str] = Field(default_factory=list)

    @validator("filename")
    @classmethod
    def validate_filename(cls, v):
        if not re.match(FILENAME_REGEX, v):
            raise ValueError(f"Filename must match pattern: {FILENAME_REGEX}")
        return v

    @validator("content_type")
    @classmethod
    def validate_content_type(cls, v):
        # Check if content type matches any of the allowed patterns
        for allowed_type in ALLOWED_CONTENT_TYPES:
            if allowed_type.endswith("*"):
                prefix = allowed_type[:-1]
                if v.startswith(prefix):
                    return v
            elif v == allowed_type:
                return v
        raise ValueError(
            f"Content type not allowed. Must be one of: {', '.join(ALLOWED_CONTENT_TYPES)}"
        )

    @validator("path")
    @classmethod
    def validate_path(cls, v):
        # Normalize path to prevent path traversal attacks
        normalized_path = os.path.normpath(v)
        if normalized_path.startswith("..") or "//" in normalized_path:
            raise ValueError("Invalid path - potential path traversal attempt")

        # Strip leading slashes to avoid absolute paths
        normalized_path = normalized_path.lstrip("/")
        return normalized_path

    @validator("collection_ids")
    @classmethod
    def validate_collection_ids(cls, v):
        # De-duplicate while preserving order; drop blanks.
        seen, cleaned = set(), []
        for cid in v:
            cid = (cid or "").strip()
            if cid and cid not in seen:
                seen.add(cid)
                cleaned.append(cid)
        if len(cleaned) > MAX_COLLECTIONS_PER_UPLOAD:
            raise ValueError(
                f"At most {MAX_COLLECTIONS_PER_UPLOAD} collections may be selected per upload"
            )
        return cleaned


class APIError(Exception):
    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def _authenticated_user_id(event) -> str:
    """Read the uploader id from API Gateway authorizer claims.

    Never derived from the request body — ensures association attribution
    cannot be spoofed.

    Handles both dict and JSON-string formats for claims, as API Gateway
    may serialize authorizer claims differently depending on configuration.
    """
    authorizer = event.get("requestContext", {}).get("authorizer", {}) or {}
    claims = authorizer.get("claims", {}) or {}

    # Handle case where claims is a JSON-encoded string
    if isinstance(claims, str):
        try:
            claims = json.loads(claims)
        except (json.JSONDecodeError, TypeError):
            claims = {}

    # Also check direct authorizer fields (custom authorizer format)
    if not isinstance(claims, dict):
        claims = {}

    return (
        claims.get("sub")
        or claims.get("cognito:username")
        or authorizer.get("sub")
        or authorizer.get("principalId")
        or ""
    )


def _within_metadata_budget(inline_ids: str, user_id: str) -> bool:
    """Check whether the collection directive fits within S3's 2 KB user-metadata budget.

    Computes the total byte cost of all metadata key-value pairs that would be stamped
    inline, and returns True only if it stays within SAFE_INLINE_BUDGET (§6.5).
    """
    used = (
        len(ML_COLLECTION_IDS_KEY)
        + len(inline_ids.encode("utf-8"))
        + len(ML_SOURCE_KEY)
        + len(UPLOAD_SOURCE_VALUE)
        + len(ML_USER_ID_KEY)
        + len(user_id.encode("utf-8"))
    )
    return used <= SAFE_INLINE_BUDGET


def _write_overflow_directive(
    bucket: str, key: str, collection_ids: List[str], user_id: str
) -> None:
    """Write the full collection id list to the Upload directives table (§6.5, §10.5).

    Called when the inline encoding would exceed SAFE_INLINE_BUDGET. The side-record
    is keyed by PK=UPLOADDIR#<bucket>#<key> and carries an expiresAt TTL (~24h) so
    DynamoDB auto-expires it.
    """
    if not UPLOAD_DIRECTIVES_TABLE_NAME:
        raise RuntimeError("UPLOAD_DIRECTIVES_TABLE_NAME is not configured")
    boto3.resource("dynamodb").Table(UPLOAD_DIRECTIVES_TABLE_NAME).put_item(
        Item={
            "PK": f"UPLOADDIR#{bucket}#{key}",
            "collectionIds": collection_ids,
            "userId": user_id,
            "expiresAt": int(time.time()) + DIRECTIVE_TTL_SECONDS,
        }
    )


def _build_collection_metadata(
    collection_ids: List[str], user_id: str, bucket: str, key: str
) -> Dict[str, str]:
    """Build the x-amz-meta-* user-metadata dict for the collection directive (§6.3).

    Returns an empty dict when no collections are selected. When the inline encoding
    would exceed the S3 budget, writes an overflow side-record and returns only the
    overflow marker plus source/user-id.
    """
    if not collection_ids:
        return {}
    meta: Dict[str, str] = {ML_SOURCE_KEY: UPLOAD_SOURCE_VALUE, ML_USER_ID_KEY: user_id}
    inline = ",".join(collection_ids)
    if _within_metadata_budget(inline, user_id):
        meta[ML_COLLECTION_IDS_KEY] = inline
    else:
        _write_overflow_directive(bucket, key, collection_ids, user_id)
        meta[ML_OVERFLOW_KEY] = "1"
    return meta


@tracer.capture_method
def normalize_prefix(prefix: str) -> str:
    """
    Normalize a prefix string to ensure consistent formatting.

    Parameters:
        prefix: The prefix string to normalize

    Returns:
        Normalized prefix with trailing slash, or empty string if input is None/empty

    Example:
        normalize_prefix("folder/subfolder") → "folder/subfolder/"
        normalize_prefix("folder/") → "folder/"
        normalize_prefix("") → ""
        normalize_prefix(None) → ""
    """
    if not prefix:
        return ""

    # Strip leading and trailing whitespace
    normalized = prefix.strip()

    if not normalized:
        return ""

    # Ensure single trailing slash for non-empty prefixes
    if not normalized.endswith("/"):
        normalized += "/"

    return normalized


@tracer.capture_method
def parse_object_prefixes(object_prefix) -> List[str]:
    """
    Parse objectPrefix from connector configuration into a list of normalized prefixes.

    Parameters:
        object_prefix: Can be str, list, or None

    Returns:
        List of normalized prefix strings, or empty list if no prefixes configured

    Example:
        parse_object_prefixes("uploads/") → ["uploads/"]
        parse_object_prefixes(["uploads/", "media/"]) → ["uploads/", "media/"]
        parse_object_prefixes(None) → []
        parse_object_prefixes("") → []
    """
    if object_prefix is None:
        return []

    # Handle string format (legacy)
    if isinstance(object_prefix, str):
        normalized = normalize_prefix(object_prefix)
        return [normalized] if normalized else []

    # Handle list format (new)
    if isinstance(object_prefix, list):
        normalized_list = []
        for prefix in object_prefix:
            if isinstance(prefix, str):
                normalized = normalize_prefix(prefix)
                if normalized:
                    normalized_list.append(normalized)
        return normalized_list

    # Return empty list for any other type
    return []


@tracer.capture_method
def validate_prefix_access(requested_path: str, allowed_prefixes: List[str]) -> bool:
    """
    Validate that a requested path is within the allowed prefix boundaries.

    Parameters:
        requested_path: The path from the upload request
        allowed_prefixes: List of normalized prefix strings that are allowed

    Returns:
        True if path is allowed (either no restrictions or within allowed prefix)
        False if path is outside all allowed prefixes

    Example:
        validate_prefix_access("uploads/video.mp4", ["uploads/"]) → True
        validate_prefix_access("private/file.mp4", ["uploads/"]) → False
        validate_prefix_access("any/path", []) → True (no restrictions)
    """
    # No restrictions - allow all access
    if not allowed_prefixes:
        return True

    # Handle edge case where requested_path is None
    if requested_path is None:
        requested_path = ""

    # Normalize the requested path for consistent comparison
    normalized_requested_path = normalize_prefix(requested_path)

    # Check if requested path starts with any allowed prefix
    for allowed_prefix in allowed_prefixes:
        normalized_allowed_prefix = normalize_prefix(allowed_prefix)
        if normalized_requested_path.startswith(normalized_allowed_prefix):
            return True

    # Path is outside all allowed prefixes
    return False


def _get_s3_client_for_bucket(bucket: str) -> boto3.client:
    """
    Return an S3 client **pinned to the bucket's actual region**.
    Clients are cached to reuse TCP connections across warm invocations.
    """
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


@tracer.capture_method
def get_connector_details(connector_id: str) -> Dict[str, Any]:
    """Retrieve connector details from DynamoDB."""
    try:
        connector_table = os.environ.get("MEDIALAKE_CONNECTOR_TABLE")
        if not connector_table:
            raise APIError(
                "MEDIALAKE_CONNECTOR_TABLE environment variable is not set", 500
            )

        table = dynamodb.Table(connector_table)
        response = table.get_item(Key={"id": connector_id})

        if "Item" not in response:
            raise APIError(f"Connector not found with ID: {connector_id}", 404)

        return response["Item"]
    except Exception as e:
        logger.error(f"Error retrieving connector details: {str(e)}")
        raise APIError(f"Error retrieving connector details: {str(e)}", 500)


@tracer.capture_method
def is_multipart_upload_required(file_size: int) -> bool:
    """Determine if multipart upload is required based on file size."""
    # 100MB threshold for multipart upload
    return file_size > 100 * 1024 * 1024


@tracer.capture_method
def generate_presigned_post_url(
    bucket: str,
    key: str,
    content_type: str,
    collection_meta: Dict[str, str] = None,
    expiration: int = DEFAULT_EXPIRATION,
) -> Dict[str, Any]:
    """Generate a presigned POST URL for the S3 object using region-aware S3 client.

    collection_meta keys are stamped as x-amz-meta-* in both Fields and Conditions
    so S3 persists them as object user-metadata (§6.3, Req 8.1).
    """
    try:
        # Get region-specific S3 client
        s3_client = _get_s3_client_for_bucket(bucket)

        fields = {"Content-Type": content_type}
        conditions = [
            {"bucket": bucket},
            {"key": key},
            [
                "content-length-range",
                1,
                100 * 1024 * 1024,
            ],  # 1 byte to 100MB (single-part threshold)
            {"Content-Type": content_type},
        ]

        # Stamp collection directive metadata into Fields and Conditions (§6.3)
        if collection_meta:
            for k, v in collection_meta.items():
                fields[f"x-amz-meta-{k}"] = v
                conditions.append({f"x-amz-meta-{k}": v})

        presigned_post = s3_client.generate_presigned_post(
            Bucket=bucket,
            Key=key,
            Fields=fields,
            Conditions=conditions,
            ExpiresIn=expiration,
        )

        logger.info(
            f"Generated presigned POST URL for s3://{bucket}/{key} (region {s3_client.meta.region_name}) valid {expiration}s"
        )

        return presigned_post
    except Exception as e:
        logger.error(f"Error generating presigned POST URL: {str(e)}")
        raise APIError(f"Error generating presigned POST URL: {str(e)}", 500)


@tracer.capture_method
def create_multipart_upload(
    bucket: str, key: str, content_type: str, collection_meta: Dict[str, str] = None
) -> Dict[str, Any]:
    """Initiate a multipart upload and return the upload ID using region-aware S3 client.

    collection_meta is passed as Metadata to create_multipart_upload so S3 carries it
    onto the completed object (§6.4, Req 8.2).
    """
    try:
        # Get region-specific S3 client
        s3_client = _get_s3_client_for_bucket(bucket)

        logger.info(
            f"Initiating multipart upload - bucket: {bucket}, key: {key}, "
            f"content_type: {content_type}, region: {s3_client.meta.region_name}"
        )

        kwargs = {
            "Bucket": bucket,
            "Key": key,
            "ContentType": content_type,
        }
        # Stamp collection directive metadata (§6.4)
        if collection_meta:
            kwargs["Metadata"] = collection_meta

        response = s3_client.create_multipart_upload(**kwargs)

        upload_id = response["UploadId"]
        logger.info(
            f"Multipart upload initiated successfully - upload_id: {upload_id}, "
            f"bucket: {bucket}, key: {key}"
        )

        return {"upload_id": upload_id}
    except Exception as e:
        logger.error(
            f"Error creating multipart upload - bucket: {bucket}, key: {key}, "
            f"content_type: {content_type}, error: {str(e)}",
            exc_info=True,
        )
        raise APIError(f"Error creating multipart upload: {str(e)}", 500)


def get_user_sub_from_event(event: Dict) -> Optional[str]:
    """Extract user sub from API Gateway authorizer context.

    Checks ``requestContext.authorizer.sub`` first (custom authorizer),
    then falls back to ``requestContext.authorizer.claims.sub`` (Cognito).

    Returns:
        The user's Cognito ``sub`` claim, or ``None`` if it cannot be
        determined.  The caller decides how to handle the missing value.
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
        pass
    return None


def get_caller_permissions(event: Dict) -> List[str]:
    """Extract the caller's flat permission list from the authorizer context.

    The custom authorizer passes the decoded token — including the
    ``custom:permissions`` JSON-string claim — as
    ``requestContext.authorizer.claims``.

    Returns an empty list if permissions cannot be determined.
    """
    try:
        authorizer = event.get("requestContext", {}).get("authorizer", {})
        if not isinstance(authorizer, dict):
            return []
        claims = authorizer.get("claims")
        if isinstance(claims, str):
            claims = json.loads(claims)
        if not isinstance(claims, dict):
            return []
        perms = claims.get("custom:permissions", "[]")
        if isinstance(perms, str):
            perms = json.loads(perms)
        return perms if isinstance(perms, list) else []
    except Exception:
        logger.warning("Could not parse caller permissions from authorizer context")
        return []


def caller_can_upload_to_connectors(event: Dict) -> bool:
    """Whether the caller may upload into shared (non-personal) connectors.

    Requires the ``connectors:upload`` permission (the ``settings.`` prefixed
    variant is also accepted for backward compatibility). This is independent
    of personal "My Assets" uploads, which only require ``assets:upload``.
    """
    perms = get_caller_permissions(event)
    return "connectors:upload" in perms or "settings.connectors:upload" in perms


def validate_personal_path(event: Dict, resolved_key: str) -> str:
    """Validate that the resolved S3 key belongs to the authenticated user.

    For my-assets connectors, ensures the upload targets only the
    authenticated user's personal folder.

    Args:
        event: The API Gateway event (for extracting user_sub).
        resolved_key: The fully constructed S3 object key.

    Returns:
        The user_sub if validation passes.

    Raises:
        APIError(401): If user_sub cannot be extracted.
        APIError(403): If the key doesn't start with ``personal/{user_sub}/``.
    """
    user_sub = get_user_sub_from_event(event)
    if user_sub is None:
        raise APIError("Unauthorized: unable to identify user", 401)

    expected_prefix = f"personal/{user_sub}/"
    if not resolved_key.startswith(expected_prefix):
        logger.warning(
            f"Personal path enforcement rejected - resolved_key: {resolved_key}, "
            f"expected_prefix: {expected_prefix}"
        )
        metrics.add_metric(
            name="PersonalPathEnforcementRejection", value=1, unit="Count"
        )
        raise APIError(
            "Access denied: upload path is outside your personal folder",
            403,
        )

    return user_sub


def _is_personal_target(connector: Dict[str, Any]) -> bool:
    """Whether an upload to ``connector`` must be confined to the caller's own
    personal ("My Assets") folder.

    True for the per-user my-assets connector AND for any connector that targets
    the personal-assets bucket or the reserved ``personal/`` key prefix (e.g. the
    internal ``my-assets-system`` connector). Enforcing personal-path ownership
    regardless of the connector's declared ``type`` prevents a caller with
    ``connectors:upload`` from using a personal-bucket connector to write into
    another user's folder.
    """
    if connector.get("type") == "my-assets":
        return True

    object_prefix = (connector.get("objectPrefix") or "").lstrip("/")
    if object_prefix == "personal" or object_prefix.startswith("personal/"):
        return True

    personal_bucket = os.environ.get("PERSONAL_ASSETS_BUCKET", "").strip()
    if personal_bucket and connector.get("storageIdentifier") == personal_bucket:
        return True

    return False


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(
    event: APIGatewayProxyEvent, context: LambdaContext
) -> Dict[str, Any]:
    try:
        # Parse and validate request body
        body = json.loads(event.get("body", "{}"))
        validate(event=body, schema=request_schema)
        request = RequestBody(**body)

        # Add structured logging context for all subsequent logs
        multipart_required = is_multipart_upload_required(request.file_size)

        # Get connector details
        connector = get_connector_details(request.connector_id)

        # Parse objectPrefix to get allowed prefixes
        allowed_prefixes = parse_object_prefixes(connector.get("objectPrefix"))
        logger.debug(
            f"Parsed allowed prefixes for connector {request.connector_id}: {allowed_prefixes}"
        )

        # Update logging context with all relevant information
        logger.append_keys(
            connector_id=request.connector_id,
            filename=request.filename,
            file_size=request.file_size,
            content_type=request.content_type,
            multipart_required=multipart_required,
            allowed_prefixes_count=len(allowed_prefixes),
            path_validation_required=bool(allowed_prefixes),
        )

        # Extract S3 bucket information
        bucket = connector.get("storageIdentifier")
        if not bucket:
            raise APIError("Invalid connector configuration: missing bucket", 400)

        # Ensure the path is safe
        safe_path = request.path.strip("/")

        # Determine effective path and matched prefix
        effective_path = safe_path
        matched_prefix = None

        if allowed_prefixes:
            # Check if safe_path already starts with any allowed prefix
            for prefix in allowed_prefixes:
                normalized_prefix = normalize_prefix(prefix)
                normalized_safe_path = normalize_prefix(safe_path) if safe_path else ""
                if normalized_safe_path.startswith(normalized_prefix):
                    # Path already includes an allowed prefix
                    matched_prefix = prefix.rstrip("/")
                    effective_path = safe_path
                    break

            # If no match found and safe_path is not empty, prepend first allowed prefix
            if matched_prefix is None and safe_path:
                matched_prefix = allowed_prefixes[0].rstrip("/")
                effective_path = f"{matched_prefix}/{safe_path}"

            # If safe_path is empty, use first allowed prefix as the effective path
            if not safe_path:
                matched_prefix = allowed_prefixes[0].rstrip("/")
                effective_path = matched_prefix

        # Validate the effective path against allowed prefixes
        if allowed_prefixes:
            if not validate_prefix_access(effective_path, allowed_prefixes):
                logger.warning(
                    f"Upload path validation failed - connector_id: {request.connector_id}, "
                    f"requested_path: {safe_path}, effective_path: {effective_path}, "
                    f"allowed_prefixes: {allowed_prefixes}"
                )
                metrics.add_metric(
                    name="UploadPathValidationFailures", value=1, unit="Count"
                )
                raise APIError(
                    f"Access denied: upload path is outside allowed prefixes. Allowed prefixes: {allowed_prefixes}",
                    403,
                )
            else:
                logger.info(
                    f"Upload path validation passed - connector_id: {request.connector_id}, "
                    f"safe_path: {safe_path}, effective_path: {effective_path}, "
                    f"matched_prefix: {matched_prefix}"
                )
                metrics.add_metric(
                    name="UploadPathValidationSuccess", value=1, unit="Count"
                )

        # Construct the object key from effective_path (avoiding duplication)
        if allowed_prefixes and matched_prefix:
            # If safe_path already contained the prefix, use it directly
            if safe_path and safe_path.startswith(matched_prefix):
                key = f"{safe_path}/{request.filename}"
            else:
                # Use effective_path which includes the matched prefix
                key = f"{effective_path}/{request.filename}"
        else:
            # No prefix restrictions
            key = f"{safe_path}/{request.filename}" if safe_path else request.filename

        # Normalize the key to prevent any issues.
        # Use os.path.normpath to resolve ".." and "." components, which
        # pathlib.Path does NOT do for relative paths.  This is critical
        # for the personal-path enforcement below: without normpath, a
        # crafted path like "personal/user-A/../user-B/file" would pass
        # the startswith check but resolve to another user's folder on S3.
        key = os.path.normpath(str(Path(key)))

        # Enforce personal-path ownership for any connector that targets the
        # personal-assets bucket / reserved `personal/` prefix — the per-user
        # my-assets connector AND the internal my-assets-system connector. This
        # stops a caller with connectors:upload from using a personal-bucket
        # connector to write into another user's folder.
        if _is_personal_target(connector):
            validate_personal_path(event, key)
        else:
            # Uploading into a shared (non-personal) connector requires the
            # connectors:upload permission in addition to assets:upload.
            # Personal "My Assets" uploads above are exempt.
            if not caller_can_upload_to_connectors(event):
                logger.warning(
                    "Upload to shared connector denied: caller lacks "
                    "connectors:upload",
                    extra={"connector_id": request.connector_id},
                )
                metrics.add_metric(
                    name="ConnectorUploadPermissionDenied", value=1, unit="Count"
                )
                raise APIError(
                    "Access denied: you do not have permission to upload to "
                    "this connector.",
                    403,
                )

        # Compute the collection directive once and apply it to whichever upload
        # path is taken (§6.3, §6.4 — single-part and multipart share the same metadata)
        user_id = _authenticated_user_id(event)
        collection_meta = _build_collection_metadata(
            request.collection_ids, user_id, bucket, key
        )

        # Handle multipart upload if file is larger than 100MB
        if is_multipart_upload_required(request.file_size):
            logger.info(
                f"Multipart upload required - filename: {request.filename}, "
                f"file_size: {request.file_size / (1024 * 1024):.2f}MB, "
                f"connector_id: {request.connector_id}, bucket: {bucket}, key: {key}"
            )

            # For multipart uploads, we need to:
            # 1. Create a multipart upload
            # 2. Generate presigned URLs for each part
            multipart_upload_info = create_multipart_upload(
                bucket, key, request.content_type, collection_meta
            )
            upload_id = multipart_upload_info["upload_id"]

            # Calculate optimal part size based on file size.
            # Strategy: scale chunk size with file size to keep total parts
            # manageable (fewer sign requests) while respecting S3 limits
            # (min 5MB, max 5GB per part, max 10,000 parts per upload).
            GB = 1024 * 1024 * 1024
            MB = 1024 * 1024

            if request.file_size >= 100 * GB:
                part_size = 500 * MB  # 100GB+ → 500MB chunks
            elif request.file_size >= 10 * GB:
                part_size = 200 * MB  # 10-100GB → 200MB chunks
            elif request.file_size >= 1 * GB:
                part_size = 100 * MB  # 1-10GB → 100MB chunks
            elif request.file_size >= 100 * MB:
                part_size = 50 * MB  # 100MB-1GB → 50MB chunks
            else:
                part_size = 5 * MB  # <100MB → 5MB chunks

            total_parts = (request.file_size + part_size - 1) // part_size

            # Safety: if still over 10,000 parts, bump part size to fit
            if total_parts > 10000:
                part_size = (request.file_size + 9999) // 10000
                part_size = ((part_size + MB - 1) // MB) * MB  # Round up to nearest MB
                total_parts = (request.file_size + part_size - 1) // part_size

                logger.info(
                    f"Adjusted part size to stay under 10,000 parts - "
                    f"new_part_size: {part_size / (1024 * 1024):.2f}MB, "
                    f"new_total_parts: {total_parts}, file_size: {request.file_size / (1024 * 1024):.2f}MB"
                )

            logger.info(
                f"Multipart upload initiated - file_size: {request.file_size} bytes, "
                f"part_size: {part_size} bytes ({part_size / (1024 * 1024):.2f}MB), "
                f"total_parts: {total_parts}, upload_id: {upload_id}"
            )

            metrics.add_metric(name="MultipartUploadCreated", value=1, unit="Count")
            metrics.add_metric(
                name="MultipartUploadFileSize", value=request.file_size, unit="Bytes"
            )

            # Response structure for on-demand part signing.
            # The frontend will call /assets/upload/multipart/sign for each part as needed
            # instead of receiving pre-generated URLs.
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "status": "success",
                        "message": "Multipart upload initiated successfully",
                        "data": {
                            "bucket": bucket,
                            "key": key,
                            "upload_id": upload_id,
                            "expires_in": DEFAULT_EXPIRATION,
                            "multipart": True,
                            "part_size": part_size,
                            "total_parts": total_parts,
                        },
                    }
                ),
            }
        else:
            logger.info(
                f"Single-part upload will be used - filename: {request.filename}, "
                f"file_size: {request.file_size / (1024 * 1024):.2f}MB, "
                f"connector_id: {request.connector_id}, bucket: {bucket}, key: {key}"
            )

            # For single-part uploads, generate a presigned POST URL
            presigned_post = generate_presigned_post_url(
                bucket, key, request.content_type, collection_meta
            )

            logger.info(
                f"Presigned POST URL generated successfully - bucket: {bucket}, key: {key}, "
                f"expiration: {DEFAULT_EXPIRATION}s"
            )

            metrics.add_metric(name="PresignedPostUrlGenerated", value=1, unit="Count")
            metrics.add_metric(
                name="SinglePartUploadFileSize", value=request.file_size, unit="Bytes"
            )

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "status": "success",
                        "message": "Presigned POST URL generated successfully",
                        "data": {
                            "bucket": bucket,
                            "key": key,
                            "presigned_post": presigned_post,
                            "expires_in": DEFAULT_EXPIRATION,
                            "multipart": False,
                        },
                    }
                ),
            }

    except (ReadTimeoutError, ConnectTimeoutError) as e:
        # Timeout errors
        logger.error(
            f"AWS service call timed out - error: {str(e)}",
            exc_info=True,
        )
        metrics.add_metric(
            name="UploadUrlGenerationTimeoutErrors", value=1, unit="Count"
        )
        return {
            "statusCode": 504,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": "AWS service call timed out. Please try again.",
                }
            ),
        }
    except APIError as e:
        # Extract request details for enhanced error context
        try:
            body = json.loads(event.get("body", "{}"))
            connector_id = body.get("connector_id", "unknown")
            filename = body.get("filename", "unknown")
            file_size = body.get("file_size", 0)
            multipart_attempted = file_size > 100 * 1024 * 1024 if file_size else False

            logger.warning(
                f"API Error - connector_id: {connector_id}, filename: {filename}, "
                f"file_size: {file_size}, multipart_attempted: {multipart_attempted}, "
                f"error: {str(e)}"
            )
        except Exception:
            logger.warning(f"API Error: {str(e)}")

        metrics.add_metric(
            name="UploadUrlGenerationClientErrors", value=1, unit="Count"
        )
        return {
            "statusCode": e.status_code,
            "body": json.dumps({"status": "error", "message": str(e)}),
        }
    except Exception as e:
        # Extract request details for enhanced error context
        upload_flow = "unknown"
        try:
            body = json.loads(event.get("body", "{}"))
            connector_id = body.get("connector_id", "unknown")
            file_size = body.get("file_size", 0)
            upload_flow = (
                "multipart" if file_size > 100 * 1024 * 1024 else "single-part"
            )

            logger.error(
                f"Unexpected error - full_request_body: {json.dumps(body)}, "
                f"connector_id: {connector_id}, upload_flow: {upload_flow}, "
                f"error: {str(e)}",
                exc_info=True,
            )
        except Exception:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)

        metrics.add_metric(
            name="UploadUrlGenerationServerErrors", value=1, unit="Count"
        )
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": f"An unexpected error occurred: {str(e)}",
                }
            ),
        }
