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
from aws_lambda_powertools.utilities.validation import SchemaValidationError, validate
from botocore.config import Config
from botocore.exceptions import ConnectTimeoutError, ReadTimeoutError
from pydantic import BaseModel, Field, ValidationError, validator

# Initialize AWS X-Ray, metrics, and logger
tracer = Tracer(service="upload-service")
metrics = Metrics(namespace="upload-service")
logger = Logger(service="upload-api", level=os.getenv("LOG_LEVEL", "WARNING"))

# Exceptions that mean "the caller sent a bad body" and must answer 4xx. Built defensively:
# the Lambda runtime ships powertools with fastjsonschema, but some unit-test harnesses stub
# the validation module out, in which case SchemaValidationError is not an exception class and
# cannot appear in an `except` clause.
_BAD_REQUEST_ERRORS = tuple(
    exc
    for exc in (json.JSONDecodeError, SchemaValidationError, ValidationError)
    if isinstance(exc, type) and issubclass(exc, BaseException)
)

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
UPLOAD_SOURCE_VALUE = "upload"

# Upload directives table.
#
# The browser performs every S3 call itself against presigned URLs (Uppy 6's
# @uppy/aws-s3), sending the bytes and a Content-Type header and nothing else, so the
# server can no longer stamp `x-amz-meta-*` onto the object. The `ml-*` directives are
# written here instead, keyed by the object's bucket and key, and the ingest Lambda merges
# the row into the object's user metadata before it builds the asset record.
UPLOAD_DIRECTIVES_TABLE_NAME = os.getenv("UPLOAD_DIRECTIVES_TABLE_NAME", "")
# A Golden Retriever restore can resume a multipart upload long after the create call, so
# the row outlives the 24h the overflow side-record used to get.
DIRECTIVE_TTL_SECONDS = 7 * 24 * 60 * 60

# Which S3 request the client is asking to have signed. Mirrors Uppy's signRequest: a PUT
# creates the object in one request, a POST (without an uploadId) creates a multipart upload.
SIGN_METHOD_PUT = "PUT"
SIGN_METHOD_POST = "POST"

ALLOWED_CONTENT_TYPES = [
    "audio/*",
    "video/*",
    "image/*",
    "application/x-mpegURL",  # HLS
    "application/dash+xml",  # MPEG-DASH
    "application/mxf",  # MXF
]
# S3-compatible filename regex.
# Allows: alphanumeric, S3 safe chars (!-_.*'()), and chars that require
# URL-encoding but are fully supported (space @$+,;=&:).
# Blocks: control chars and S3 "characters to avoid" (\{}^`~|%<>"#[])
FILENAME_REGEX = r"^[a-zA-Z0-9!\-_.*'() @\$+,;=&:]+$"

"""
UPLOAD PROTOCOL

The client is Uppy 6's @uppy/aws-s3 in `signRequest` mode. It asks this endpoint to sign
the request that creates the object and then talks to S3 directly:

- `method: "PUT"`  — single-part upload; the response URL is a presigned PutObject with
  `content-type` and `content-length` as signed headers, so the object can only be written
  with the declared type and exact size.
- `method: "POST"` — multipart upload; the response URL is a presigned
  CreateMultipartUpload. Parts, ListParts, Complete and Abort are signed by
  /assets/upload/multipart/sign.

Either way the object key is decided here from the connector's allowed prefixes, the
requested path and the filename, and returned as `key`; the client uses it for the rest of
the upload. Collection directives are written to the upload-directives table rather than
stamped on the object (see UPLOAD_DIRECTIVES_TABLE_NAME above).
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
        "method": {"type": "string", "enum": [SIGN_METHOD_PUT, SIGN_METHOD_POST]},
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
    # Optional so a caller that omits it gets the size-based choice the endpoint always
    # made; Uppy passes the method it is about to use.
    method: Optional[str] = None

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

    @validator("method")
    @classmethod
    def validate_method(cls, v):
        # Also enforced by the request schema; repeated here so the model is a complete
        # contract on its own and the value can be trusted downstream.
        if v is not None and v not in (SIGN_METHOD_PUT, SIGN_METHOD_POST):
            raise ValueError(
                f"method must be one of: {SIGN_METHOD_PUT}, {SIGN_METHOD_POST}"
            )
        return v

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


def _build_directives(collection_ids: List[str], user_id: str) -> Dict[str, str]:
    """The ``ml-*`` directive map for this upload, in the shape ingest expects.

    Same keys and values that used to be stamped as ``x-amz-meta-*``: ingest merges this map
    into the object's user metadata, so every downstream reader (Layer C collection
    association and the upload-session nodes) sees exactly what it saw before. Empty when no
    collections were selected, matching the previous "nothing to stamp" behaviour.

    There is no inline/overflow split any more: the row lives in DynamoDB, where the 2 KB S3
    user-metadata budget does not apply.
    """
    if not collection_ids:
        return {}
    return {
        ML_SOURCE_KEY: UPLOAD_SOURCE_VALUE,
        ML_USER_ID_KEY: user_id,
        ML_COLLECTION_IDS_KEY: ",".join(collection_ids),
    }


def _write_upload_directives(
    bucket: str,
    key: str,
    directives: Dict[str, str],
    collection_ids: List[str],
    user_id: str,
    connector_id: str,
) -> None:
    """Persist the directive row for the object about to be uploaded.

    Keyed ``PK=UPLOADDIR#<bucket>#<key>`` — the same key the ingest Lambda already used for
    the overflow side-record, so its lookup is unchanged. ``collectionIds`` and ``userId``
    are kept alongside the ``directives`` map for the legacy overflow reader.

    Written before the presigned URL is returned: if this fails the upload must fail too,
    because an object that lands without its row silently loses its collection association.
    """
    if not UPLOAD_DIRECTIVES_TABLE_NAME:
        raise RuntimeError("UPLOAD_DIRECTIVES_TABLE_NAME is not configured")
    boto3.resource("dynamodb").Table(UPLOAD_DIRECTIVES_TABLE_NAME).put_item(
        Item={
            "PK": f"UPLOADDIR#{bucket}#{key}",
            "directives": directives,
            "collectionIds": collection_ids,
            "userId": user_id,
            "connectorId": connector_id,
            "expiresAt": int(time.time()) + DIRECTIVE_TTL_SECONDS,
        }
    )


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
    except APIError:
        # Already carries the right status code (e.g. 404 for an unknown connector);
        # re-raise unchanged so a client error is not reported as a server fault.
        raise
    except Exception as e:
        logger.error(f"Error retrieving connector details: {str(e)}")
        raise APIError(f"Error retrieving connector details: {str(e)}", 500)


@tracer.capture_method
def is_multipart_upload_required(file_size: int) -> bool:
    """Size-based default when the client does not say which request it will make.

    Matches the client's default ``shouldUseMultipart`` threshold (100MB).
    """
    return file_size > 100 * 1024 * 1024


def resolve_sign_method(requested: Optional[str], file_size: int) -> str:
    """The S3 request to presign: the client's choice, or the size-based default."""
    if requested in (SIGN_METHOD_PUT, SIGN_METHOD_POST):
        return requested
    return (
        SIGN_METHOD_POST if is_multipart_upload_required(file_size) else SIGN_METHOD_PUT
    )


@tracer.capture_method
def generate_presigned_put_url(
    bucket: str,
    key: str,
    content_type: str,
    file_size: int,
    expiration: int = DEFAULT_EXPIRATION,
) -> str:
    """Presigned PutObject URL for a single-part upload.

    ``ContentType`` and ``ContentLength`` become signed headers (``content-type`` and
    ``content-length``). The browser always sends both — Uppy sets ``Content-Type`` to the
    same value the client declared here, and the browser sets ``Content-Length`` from the
    body — so the object can only be written with the declared type and exactly the declared
    size. This replaces the ``content-length-range`` condition of the old presigned POST.
    """
    try:
        s3_client = _get_s3_client_for_bucket(bucket)
        url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ContentType": content_type,
                "ContentLength": file_size,
            },
            ExpiresIn=expiration,
        )
        logger.info(
            f"Generated presigned PUT URL for s3://{bucket}/{key} "
            f"(region {s3_client.meta.region_name}) valid {expiration}s"
        )
        return url
    except Exception as e:
        logger.error(f"Error generating presigned PUT URL: {str(e)}")
        raise APIError(f"Error generating presigned PUT URL: {str(e)}", 500)


@tracer.capture_method
def generate_create_multipart_url(
    bucket: str, key: str, content_type: str, expiration: int = DEFAULT_EXPIRATION
) -> str:
    """Presigned CreateMultipartUpload URL.

    The browser POSTs to it and reads the UploadId from the XML response; the server never
    sees the upload id. ``ContentType`` is a signed header for the same reason as the PUT.
    """
    try:
        s3_client = _get_s3_client_for_bucket(bucket)
        url = s3_client.generate_presigned_url(
            "create_multipart_upload",
            Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expiration,
        )
        logger.info(
            f"Generated presigned CreateMultipartUpload URL for s3://{bucket}/{key} "
            f"(region {s3_client.meta.region_name}) valid {expiration}s"
        )
        return url
    except Exception as e:
        logger.error(f"Error generating presigned CreateMultipartUpload URL: {str(e)}")
        raise APIError(
            f"Error generating presigned CreateMultipartUpload URL: {str(e)}", 500
        )


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

    # objectPrefix may be a string (legacy) or a list of prefixes; reuse the
    # shared parser so both shapes are handled consistently.
    for object_prefix in parse_object_prefixes(connector.get("objectPrefix")):
        # parse_object_prefixes guarantees a trailing slash but not a stripped
        # leading slash, so a bare "personal" arrives as "personal/" and
        # "/personal" as "/personal/".
        if object_prefix.lstrip("/").startswith("personal/"):
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

        # The directive row carries what used to be stamped on the object. It is written
        # first so a failure surfaces as a failed request rather than as an object that
        # lands without its collection association.
        user_id = _authenticated_user_id(event)
        directives = _build_directives(request.collection_ids, user_id)
        if directives:
            _write_upload_directives(
                bucket,
                key,
                directives,
                request.collection_ids,
                user_id,
                request.connector_id,
            )

        method = resolve_sign_method(request.method, request.file_size)
        multipart = method == SIGN_METHOD_POST

        if multipart:
            logger.info(
                f"Signing CreateMultipartUpload - filename: {request.filename}, "
                f"file_size: {request.file_size / (1024 * 1024):.2f}MB, "
                f"connector_id: {request.connector_id}, bucket: {bucket}, key: {key}"
            )
            url = generate_create_multipart_url(bucket, key, request.content_type)
            metrics.add_metric(name="MultipartUploadCreated", value=1, unit="Count")
            metrics.add_metric(
                name="MultipartUploadFileSize", value=request.file_size, unit="Bytes"
            )
            message = "CreateMultipartUpload URL generated successfully"
        else:
            logger.info(
                f"Signing PutObject - filename: {request.filename}, "
                f"file_size: {request.file_size / (1024 * 1024):.2f}MB, "
                f"connector_id: {request.connector_id}, bucket: {bucket}, key: {key}"
            )
            url = generate_presigned_put_url(
                bucket, key, request.content_type, request.file_size
            )
            metrics.add_metric(name="PresignedPutUrlGenerated", value=1, unit="Count")
            metrics.add_metric(
                name="SinglePartUploadFileSize", value=request.file_size, unit="Bytes"
            )
            message = "Presigned PUT URL generated successfully"

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "status": "success",
                    "message": message,
                    "data": {
                        "bucket": bucket,
                        # Authoritative: the client proposed a placeholder and must use
                        # this key for every later request of the upload.
                        "key": key,
                        "url": url,
                        "method": method,
                        "multipart": multipart,
                        "expires_in": DEFAULT_EXPIRATION,
                    },
                }
            ),
        }

    except _BAD_REQUEST_ERRORS as e:
        # A malformed body or a body that fails the request schema is a client error.
        # The underlying messages carry schema paths, pydantic internals and the submitted
        # values, so they are logged but not returned to the caller.
        logger.warning(f"Invalid upload request: {str(e)}")
        metrics.add_metric(
            name="UploadUrlGenerationClientErrors", value=1, unit="Count"
        )
        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "status": "error",
                    "message": "Invalid request body. Check the required upload fields and try again.",
                }
            ),
        }
    except (ReadTimeoutError, ConnectTimeoutError) as e:
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
                    "message": "An unexpected error occurred while preparing the upload.",
                }
            ),
        }
