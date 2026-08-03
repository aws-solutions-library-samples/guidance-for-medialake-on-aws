import json
import math
import os
import re
import time
from decimal import Decimal, InvalidOperation
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from boto3.dynamodb.types import TypeDeserializer
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.helpers import streaming_bulk

logger = Logger(service="ddb-to-os-index")
tracer = Tracer()
metrics = Metrics(namespace="MediaLake/AssetIndexing", service="ddb-to-os-index")

# OpenSearch configuration
REGION = os.environ["OS_DOMAIN_REGION"]
HOST = os.environ["OPENSEARCH_ENDPOINT"].split("://")[-1]
INDEX = os.environ["OPENSEARCH_INDEX"]
SQS_URL = os.environ["SQS_URL"]

# Bulk processing configuration
BULK_BATCH_SIZE = int(os.environ.get("BULK_BATCH_SIZE", "500"))
MAX_BULK_SIZE_MB = int(os.environ.get("MAX_BULK_SIZE_MB", "5"))

# Circuit breaker configuration
ERROR_THRESHOLD = float(os.environ.get("ERROR_THRESHOLD", "0.3"))
CIRCUIT_TIMEOUT = int(os.environ.get("CIRCUIT_TIMEOUT", "60"))

# Verbose logging configuration (set env var VERBOSE_LOGGING=true to enable
# detailed per-document logging without a code change)
VERBOSE_LOGGING = os.environ.get("VERBOSE_LOGGING", "false").lower() == "true"

deserializer = TypeDeserializer()


class CircuitBreaker:
    """
    Circuit breaker to prevent overwhelming OpenSearch when it's under pressure.
    Opens circuit when error rate exceeds threshold, preventing further requests.
    """

    def __init__(
        self, error_threshold: float = ERROR_THRESHOLD, timeout: int = CIRCUIT_TIMEOUT
    ):
        self.error_threshold = error_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def record_success(self):
        """Record a successful operation."""
        self.success_count += 1
        if self.state == "HALF_OPEN" and self.success_count >= 3:
            self.state = "CLOSED"
            self.failure_count = 0
            logger.info("Circuit breaker closed - system recovered")

    def record_failure(self):
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        total_requests = self.success_count + self.failure_count
        if total_requests >= 10:
            error_rate = self.failure_count / total_requests
            if error_rate >= self.error_threshold and self.state == "CLOSED":
                self.state = "OPEN"
                logger.warning(
                    f"Circuit breaker opened - error rate {error_rate:.2%}",
                    extra={"failures": self.failure_count, "total": total_requests},
                )

    def can_proceed(self) -> bool:
        """Check if requests can proceed."""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            if time.time() - self.last_failure_time >= self.timeout:
                self.state = "HALF_OPEN"
                self.failure_count = 0
                self.success_count = 0
                logger.info("Circuit breaker half-open - testing recovery")
                return True
            return False

        return True  # HALF_OPEN state


circuit_breaker = CircuitBreaker()


def retry_with_backoff(max_retries=5, base_delay=2, max_delay=60):
    """
    Decorator that implements retry logic with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (default: 5)
        base_delay: Initial delay in seconds between retries (default: 2s)
        max_delay: Maximum delay in seconds between retries (default: 60s)
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    if not circuit_breaker.can_proceed():
                        logger.warning("Circuit breaker open - skipping operation")
                        raise Exception("Circuit breaker is open")

                    result = func(*args, **kwargs)
                    circuit_breaker.record_success()
                    return result

                except Exception as e:
                    last_exception = e
                    circuit_breaker.record_failure()

                    if attempt == max_retries:
                        logger.error(
                            f"All {max_retries + 1} retry attempts failed for function {func.__name__}",
                            extra={
                                "function": func.__name__,
                                "total_attempts": max_retries + 1,
                                "final_error": str(e),
                                "error_type": type(e).__name__,
                            },
                        )
                        raise e

                    delay = min(base_delay * (2**attempt), max_delay)

                    logger.warning(
                        f"Attempt {attempt + 1} failed, retrying in {delay}s",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "delay": delay,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                    )

                    time.sleep(delay)

            raise last_exception

        return wrapper

    return decorator


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Decimal objects from DynamoDB.

    Guards against decimal.DivisionImpossible and other InvalidOperation
    errors that occur when Decimal values have extreme precision or
    special forms (NaN, Infinity, very large exponents) that cannot
    survive a modulo or int/float conversion.
    """

    def default(self, obj):
        if isinstance(obj, Decimal):
            try:
                if obj % 1 == 0:
                    return int(obj)
                return float(obj)
            except (InvalidOperation, OverflowError, ValueError):
                # Fallback: convert to string to preserve the value without
                # risking DivisionImpossible or overflow.
                return str(obj)
        return super().default(obj)


from opensearchpy import RequestsAWSV4SignerAuth as _StreamSignerAuth

# Initialize AWS credentials and clients
# Use RequestsAWSV4SignerAuth with refreshable credentials so that
# long-lived Lambda containers never sign requests with expired tokens.
from refreshable_auth import get_refreshable_credentials

sqs = boto3.client("sqs")
opensearch_client = OpenSearch(
    hosts=[{"host": HOST, "port": 443}],
    http_auth=_StreamSignerAuth(get_refreshable_credentials(), REGION, "es"),
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    timeout=30,
    max_retries=3,
    retry_on_timeout=True,
)


def dynamodb_item_to_dict(item):
    """
    Convert a DynamoDB record (e.g., NewImage from a Streams event)
    into a normal Python dict.
    """
    return {k: deserializer.deserialize(v) for k, v in item.items()}


# ---------------------------------------------------------------------------
# Metadata sanitization for OpenSearch compatibility
# ---------------------------------------------------------------------------
# These EXIF / IPTC fields are known to carry string values (labels, phone
# numbers, serial numbers) that OpenSearch's dynamic mapping may have already
# locked to ``long`` or ``date``.
#
# Strategy: the OpenSearch index already has these fields mapped as ``long``.
# Changing the mapping requires a full reindex, so instead we convert
# human-readable labels back to their EXIF numeric codes.  Values that
# cannot be mapped are *removed* from the document so OpenSearch doesn't
# reject the entire bulk item.
# ---------------------------------------------------------------------------

# Field-specific label → numeric code mappings.
# Keys are the EXIF/IPTC field names as they appear in the Metadata tree.
# Values are dicts mapping lowercased string labels to their integer codes.
_FIELD_LABEL_TO_CODE: Dict[str, Dict[str, int]] = {
    "White Balance": {
        # EXIF tag 41987
        "auto": 0,
        "auto white balance": 0,
        "manual": 1,
        "manual white balance": 1,
    },
    "Light Source": {
        # EXIF tag 37384
        "unknown": 0,
        "daylight": 1,
        "fluorescent": 2,
        "tungsten": 3,
        "tungsten (incandescent light)": 3,
        "flash": 4,
        "fine weather": 9,
        "cloudy weather": 10,
        "cloudy": 10,
        "shade": 11,
        "daylight fluorescent": 12,
        "day white fluorescent": 13,
        "cool white fluorescent": 14,
        "white fluorescent": 15,
        "warm white fluorescent": 16,
        "standard light a": 17,
        "standard light b": 18,
        "standard light c": 19,
        "d55": 20,
        "d65": 21,
        "d75": 22,
        "d50": 23,
        "iso studio tungsten": 24,
        "other": 255,
        "other light source": 255,
    },
    "Metering Mode": {
        # EXIF tag 37383
        "unknown": 0,
        "average": 1,
        "centerweightedaverage": 2,
        "center weighted average": 2,
        "center-weighted average": 2,
        "spot": 3,
        "multi-spot": 4,
        "multispot": 4,
        "multi spot": 4,
        "pattern": 5,
        "partial": 6,
        "other": 255,
    },
    "Exposure Mode": {
        # EXIF tag 41986
        "auto": 0,
        "auto exposure": 0,
        "manual": 1,
        "manual exposure": 1,
        "auto bracket": 2,
    },
    "Gain Control": {
        # EXIF tag 41991
        "none": 0,
        "low gain up": 1,
        "high gain up": 2,
        "low gain down": 3,
        "high gain down": 4,
    },
    "Scene Capture Type": {
        # EXIF tag 41990
        "standard": 0,
        "landscape": 1,
        "portrait": 2,
        "night": 3,
        "night scene": 3,
    },
}

# Fields whose values should be REMOVED from the document if they can't be
# parsed as a number that fits in a Java long.  The value is still preserved
# in DynamoDB — it just won't appear in the OpenSearch index (which would
# reject it anyway with a mapper_parsing_exception).
_FIELDS_REMOVE_IF_NOT_NUMERIC: set = {
    # Contact / identifier fields
    "Ci Tel Work",
    "Serial Number",
    "Body Serial Number",
    # Date fields with non-ISO formats
    "Date Time Original",
    "Date Time Digitized",
    "Date Time",
    "Create Date",
    # Leaf / capture metadata (arbitrary strings)
    "Gray Balance",
    # DAM system fields
    "Unknown",
    # Photoshop metadata
    "Transmission Reference",
    # XMP instance IDs
    "Instance ID",
    # Scene Type (raw byte strings like "01 00 00 00")
    "Scene Type",
    # SKU / product fields with type conflicts
    "Skunum",
    # Webdam custom fields (mixed types like "1.7 oz")
    "Custom Field13",
}


def _sanitize_decimal(value: Any) -> Any:
    """Convert a Decimal to int/float safely, falling back to str.

    This prevents ``decimal.DivisionImpossible`` and ``OverflowError``
    that occur with very large or high-precision DynamoDB numbers.
    Non-finite floats (inf/-inf/nan) are dropped to None: JSON for
    OpenSearch cannot carry them, and downstream int() conversions crash
    with "cannot convert float infinity to integer".
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if not isinstance(value, Decimal):
        return value
    try:
        if value.is_finite():
            if value % 1 == 0:
                return int(value)
            result = float(value)
            return result if math.isfinite(result) else str(value)
        return str(value)  # Decimal('Infinity') / Decimal('NaN')
    except (InvalidOperation, OverflowError, ValueError):
        return str(value)


def _sanitize_value_recursive(obj: Any) -> Any:
    """Walk an arbitrary nested structure and make every value OS-safe.

    * Decimal → int | float | str  (safe conversion)
    * Everything else passes through unchanged.
    """
    if isinstance(obj, dict):
        return {k: _sanitize_value_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_value_recursive(v) for v in obj]
    if isinstance(obj, set):
        return [_sanitize_value_recursive(v) for v in obj]
    return _sanitize_decimal(obj)


def _sanitize_metadata_field(field_name: str, field_value: Any) -> Any:
    """Convert a metadata field value so it's safe for the existing OS mapping.

    * For fields in ``_FIELD_LABEL_TO_CODE``: convert known string labels to
      their EXIF numeric code.  If the label is unrecognised *and* the value
      is not already numeric, return ``None`` (caller should drop the field).
    * For fields in ``_FIELDS_REMOVE_IF_NOT_NUMERIC``: return the value only
      if it's numeric; otherwise return ``None``.
    * For all other fields: pass through unchanged.

    Numeric values that exceed Java's ``long`` range (±2^63-1) are treated
    as non-numeric since OpenSearch will reject them.
    """
    _JAVA_LONG_MIN = -(2**63)
    _JAVA_LONG_MAX = 2**63 - 1

    label_map = _FIELD_LABEL_TO_CODE.get(field_name)
    is_remove_if_not_numeric = field_name in _FIELDS_REMOVE_IF_NOT_NUMERIC

    if label_map is None and not is_remove_if_not_numeric:
        return field_value  # not a problematic field

    def _try_numeric(val_str: str):
        """Try to parse a string as int (within long range) or float."""
        try:
            n = int(val_str)
            if _JAVA_LONG_MIN <= n <= _JAVA_LONG_MAX:
                return n
            return None  # overflows Java long
        except ValueError:
            pass
        try:
            return float(val_str)
        except ValueError:
            pass
        return None

    def _is_safe_numeric(val) -> bool:
        """Check if a value is numeric and within Java long range."""
        if isinstance(val, float):
            return True
        if isinstance(val, int):
            return _JAVA_LONG_MIN <= val <= _JAVA_LONG_MAX
        return False

    # The common shape is {"value": <something>, ...}
    if isinstance(field_value, dict) and "value" in field_value:
        raw = field_value["value"]
        if isinstance(raw, (int, float)) and _is_safe_numeric(raw):
            return field_value  # already numeric and in range — safe
        if isinstance(raw, str):
            # Try label → code mapping first
            if label_map is not None:
                code = label_map.get(raw.lower().strip())
                if code is not None:
                    field_value["value"] = code
                    return field_value
            # Try plain numeric parse
            parsed = _try_numeric(raw)
            if parsed is not None:
                field_value["value"] = parsed
                return field_value
            # Can't make it numeric — signal removal
            return None
        # Numeric but out of range
        if isinstance(raw, int) and not _is_safe_numeric(raw):
            return None
        # Non-string, non-numeric (e.g. None, bool) — keep as-is
        return field_value

    # Flat value (not wrapped in {"value": ...})
    if isinstance(field_value, (int, float)) and _is_safe_numeric(field_value):
        return field_value
    if isinstance(field_value, str):
        if label_map is not None:
            code = label_map.get(field_value.lower().strip())
            if code is not None:
                return code
        parsed = _try_numeric(field_value)
        if parsed is not None:
            return parsed
        return None  # signal removal
    return field_value


def _sanitize_metadata_block(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Walk the ``Metadata`` subtree and fix known problematic fields.

    Handles arbitrary nesting depth (e.g.
    ``Metadata.EmbeddedMetadata.Exif.White Balance.value``).

    Fields whose values cannot be safely converted are *removed* from the
    output so they don't cause mapper_parsing_exception in OpenSearch.
    """
    if not isinstance(metadata, dict):
        return metadata
    sanitized: Dict[str, Any] = {}
    for key, value in metadata.items():
        if key in _FIELD_LABEL_TO_CODE or key in _FIELDS_REMOVE_IF_NOT_NUMERIC:
            result = _sanitize_metadata_field(key, value)
            if result is not None:
                sanitized[key] = result
            # else: intentionally dropped — value can't be made OS-safe
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_metadata_block(value)
        else:
            sanitized[key] = value
    return sanitized


def sanitize_document(document: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare a DynamoDB document for safe OpenSearch indexing.

    1. Recursively converts all ``Decimal`` values to native Python types
       (int / float / str) to prevent ``DivisionImpossible``.
    2. Coerces known EXIF/IPTC metadata fields to strings so they don't
       clash with OpenSearch's dynamic ``long`` / ``date`` mappings.

    The function returns a *new* dict — the original is not mutated.
    """
    doc = _sanitize_value_recursive(document)
    if "Metadata" in doc and isinstance(doc["Metadata"], dict):
        doc["Metadata"] = _sanitize_metadata_block(doc["Metadata"])
    return doc


def normalize_metadata_values(obj):
    """
    Recursively normalize metadata values to ensure consistent types for OpenSearch.
    Converts string values to numbers where appropriate to match existing index mappings.
    """
    # EXIF tag value mappings - convert human-readable strings back to numeric codes
    EXIF_VALUE_MAPPINGS = {
        # Resolution Unit (tag 296)
        "inches": 2,
        "inch": 2,
        "centimeters": 3,
        "centimeter": 3,
        "cm": 3,
        "none": 1,
        # Orientation (tag 274)
        "horizontal (normal)": 1,
        "mirror horizontal": 2,
        "rotate 180": 3,
        "mirror vertical": 4,
        "mirror horizontal and rotate 270 cw": 5,
        "rotate 90 cw": 6,
        "mirror horizontal and rotate 90 cw": 7,
        "rotate 270 cw": 8,
        # YCbCr Positioning (tag 531)
        "centered": 1,
        "co-sited": 2,
        # Exposure Program (tag 34850)
        "not defined": 0,
        "manual": 1,
        "normal program": 2,
        "aperture priority": 3,
        "shutter priority": 4,
        "creative program": 5,
        "action program": 6,
        "portrait mode": 7,
        "landscape mode": 8,
        # Metering Mode (tag 37383)
        "unknown": 0,
        "average": 1,
        "center weighted average": 2,
        "spot": 3,
        "multi-spot": 4,
        "pattern": 5,
        "partial": 6,
        # Flash (common values)
        "flash did not fire": 0,
        "flash fired": 1,
        # Color Space (tag 40961)
        "srgb": 1,
        "uncalibrated": 65535,
        # Sensing Method (tag 41495)
        "one-chip color area sensor": 2,
        # File Source (tag 41728)
        "digital camera": 3,
        # Scene Type (tag 41729)
        "directly photographed": 1,
        # Custom Rendered (tag 41985)
        "normal process": 0,
        "custom process": 1,
        # Exposure Mode (tag 41986)
        "auto exposure": 0,
        "manual exposure": 1,
        "auto bracket": 2,
        # White Balance (tag 41987)
        "auto white balance": 0,
        "manual white balance": 1,
        # Scene Capture Type (tag 41990)
        "standard": 0,
        "landscape": 1,
        "portrait": 2,
        "night scene": 3,
        # Contrast, Saturation, Sharpness (tags 41992-41994)
        "normal": 0,
        "soft": 1,
        "hard": 2,
        "low": 1,
        "high": 2,
    }

    if isinstance(obj, dict):
        return {k: normalize_metadata_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [normalize_metadata_values(item) for item in obj]
    elif isinstance(obj, (int, float, Decimal)):
        return obj  # Keep numeric types as-is
    elif isinstance(obj, str):
        # Try to convert known string values to their numeric equivalents
        lower_val = obj.lower().strip()
        if lower_val in EXIF_VALUE_MAPPINGS:
            return EXIF_VALUE_MAPPINGS[lower_val]
        # Try to parse as number if it looks numeric. Guard against values
        # that parse to inf/nan (e.g. "1.8E+310") - keep those as strings.
        try:
            if "." in obj:
                parsed = float(obj)
                return parsed if math.isfinite(parsed) else obj
            return int(obj)
        except ValueError:
            return obj  # Keep as string if not convertible
    elif obj is None:
        return None
    else:
        return str(obj)


def normalize_document_for_indexing(document: dict) -> dict:
    """
    Normalize a document before indexing to OpenSearch.
    Specifically handles EmbeddedMetadata which can have inconsistent types.

    Pipeline:
    1. sanitize_document — safe Decimal conversion + force-keyword fields
    2. normalize_metadata_values — EXIF string→numeric enum mapping
    3. remove_conflicting_fields — strip/convert known serial/version fields
    """
    # Step 1: make all Decimals safe and coerce known keyword fields to str
    doc = sanitize_document(document)

    if "Metadata" in doc and "EmbeddedMetadata" in doc.get("Metadata", {}):
        # Step 2 & 3: normalize enum labels and remove conflicting fields
        # (json round-trip is no longer needed for Decimal safety since
        #  sanitize_document already handled that, but we keep the deep-copy
        #  semantics so callers don't see mutations)
        doc_copy = json.loads(json.dumps(doc, cls=DecimalEncoder))
        doc_copy["Metadata"]["EmbeddedMetadata"] = normalize_metadata_values(
            doc_copy["Metadata"]["EmbeddedMetadata"]
        )
        doc_copy["Metadata"]["EmbeddedMetadata"] = remove_conflicting_fields(
            doc_copy["Metadata"]["EmbeddedMetadata"]
        )
        return doc_copy

    return doc


def remove_conflicting_fields(obj, path=""):
    """
    Remove fields that have known type conflicts in OpenSearch.
    These are fields mapped as numeric but can contain alphanumeric strings.
    """
    # Fields that are mapped as long but can contain non-numeric strings
    SERIAL_NUMBER_PATHS = {
        "Exif.Serial Number.value",
        "Exif.Body Serial Number.value",
        "Exif.Lens Serial Number.value",
        "Ifd0.Serial Number.value",
        "Aux.Serial Number.value",
        "Aux.Lens Serial Number.value",
    }
    # Version fields that need special handling (e.g., "2.2.1" -> 221)
    VERSION_PATHS = {
        "Exif.Exif Version.value",
        "Exif.FlashPix Version.value",
    }

    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            current_path = f"{path}.{k}" if path else k
            # Handle serial number fields - convert to numeric value
            if current_path in SERIAL_NUMBER_PATHS:
                if isinstance(v, str):
                    # Try parsing as hex first (common for lens serials like "00000d4e5a")
                    try:
                        result[k] = int(v, 16)
                    except ValueError:
                        # Fall back to stripping non-digits
                        numeric_only = "".join(c for c in v if c.isdigit())
                        if numeric_only:
                            result[k] = int(numeric_only)
                        # Skip if no digits at all
                elif isinstance(v, (int, float)):
                    try:
                        result[k] = int(v)
                    except (OverflowError, ValueError):
                        pass  # inf/nan - drop rather than crash the record
            # Handle version fields - strip dots and convert to int
            elif current_path in VERSION_PATHS:
                if isinstance(v, str):
                    # "2.2.1" -> "221" -> 221
                    numeric_only = "".join(c for c in v if c.isdigit())
                    if numeric_only:
                        result[k] = int(numeric_only)
                elif isinstance(v, (int, float)):
                    try:
                        result[k] = int(v)
                    except (OverflowError, ValueError):
                        pass  # inf/nan - drop rather than crash the record
            else:
                result[k] = remove_conflicting_fields(v, current_path)
        return result
    elif isinstance(obj, list):
        return [remove_conflicting_fields(item, path) for item in obj]
    else:
        return obj


def prepare_bulk_actions(records: List[dict]) -> Tuple[List[dict], dict, List[dict]]:
    """
    Prepare bulk actions from DynamoDB stream records.

    Returns:
        Tuple of (bulk_actions, action_to_record_map, failed_records)
        action_to_record_map: dict mapping document_id to original record
    """
    bulk_actions = []
    action_to_record_map = {}
    failed_records = []
    # Always-on manifest of every document in this batch, logged at the end so
    # a specific InventoryID or object name can be traced through the stream.
    batch_manifest = {"index": [], "update": [], "delete": [], "skipped_lock": 0}

    def _object_name(doc: dict) -> str:
        """Best-effort extraction of the object name for log traceability."""
        try:
            return (
                doc.get("DigitalSourceAsset", {})
                .get("MainRepresentation", {})
                .get("StorageInfo", {})
                .get("PrimaryLocation", {})
                .get("ObjectKey", {})
                .get("Name", "?")
            )
        except Exception:
            return "?"

    for idx, record in enumerate(records):
        try:
            event_name = record.get("eventName")

            if VERBOSE_LOGGING:
                logger.info(
                    f"Processing record {idx + 1}/{len(records)}",
                    extra={"event_name": event_name, "record_index": idx},
                )

            if event_name == "REMOVE":
                document_id = record["dynamodb"]["OldImage"]["InventoryID"]["S"]

                # Skip internal LOCK records - they should never be indexed
                if document_id.startswith("LOCK#"):
                    batch_manifest["skipped_lock"] += 1
                    if VERBOSE_LOGGING:
                        logger.info(
                            f"Skipping LOCK record: {document_id}",
                            extra={"document_id": document_id, "operation": "skip"},
                        )
                    continue
                bulk_actions.append(
                    {
                        "_op_type": "delete",
                        "_index": INDEX,
                        "_id": document_id,
                    }
                )
                action_to_record_map[document_id] = record
                batch_manifest["delete"].append(document_id)

                if VERBOSE_LOGGING:
                    logger.info(
                        f"Prepared DELETE action for document {document_id}",
                        extra={"document_id": document_id, "operation": "delete"},
                    )

            elif event_name == "INSERT":
                new_image = record["dynamodb"].get("NewImage")
                if not new_image:
                    logger.warning("INSERT event without NewImage; skipping")
                    continue

                document = dynamodb_item_to_dict(new_image)
                document_id = document["InventoryID"]

                # Skip internal LOCK records - they should never be indexed
                if document_id.startswith("LOCK#"):
                    if VERBOSE_LOGGING:
                        logger.info(
                            f"Skipping LOCK record: {document_id}",
                            extra={"document_id": document_id, "operation": "skip"},
                        )
                    continue

                # Normalize document to avoid type conflicts in OpenSearch
                normalized_doc = normalize_document_for_indexing(document)
                bulk_actions.append(
                    {
                        "_op_type": "index",
                        "_index": INDEX,
                        "_id": document_id,
                        "_source": normalized_doc,
                    }
                )
                action_to_record_map[document_id] = record
                batch_manifest["index"].append(
                    f"{document_id} ({_object_name(document)})"
                )

                if VERBOSE_LOGGING:
                    logger.info(
                        f"Prepared INDEX action for document {document_id}",
                        extra={"document_id": document_id, "operation": "index"},
                    )

            elif event_name == "MODIFY":
                new_image = record["dynamodb"].get("NewImage")
                if not new_image:
                    logger.warning("MODIFY event without NewImage; skipping")
                    continue

                document = dynamodb_item_to_dict(new_image)
                document_id = document["InventoryID"]

                # Skip internal LOCK records - they should never be indexed
                if document_id.startswith("LOCK#"):
                    if VERBOSE_LOGGING:
                        logger.info(
                            f"Skipping LOCK record: {document_id}",
                            extra={"document_id": document_id, "operation": "skip"},
                        )
                    continue

                # Normalize document to avoid type conflicts in OpenSearch
                normalized_doc = normalize_document_for_indexing(document)
                bulk_actions.append(
                    {
                        "_op_type": "update",
                        "_index": INDEX,
                        "_id": document_id,
                        "doc": normalized_doc,
                        "doc_as_upsert": True,
                    }
                )
                action_to_record_map[document_id] = record
                batch_manifest["update"].append(
                    f"{document_id} ({_object_name(document)})"
                )

                if VERBOSE_LOGGING:
                    logger.info(
                        f"Prepared UPDATE action for document {document_id}",
                        extra={"document_id": document_id, "operation": "update"},
                    )

        except Exception as e:
            # Best-effort InventoryID extraction so the failed asset is
            # identifiable in the logs even when preparation crashed.
            failed_inventory_id = "unknown"
            try:
                img = record.get("dynamodb", {}).get("NewImage") or record.get(
                    "dynamodb", {}
                ).get("OldImage", {})
                failed_inventory_id = img.get("InventoryID", {}).get("S", "unknown")
            except Exception:
                pass
            logger.error(
                f"Failed to prepare bulk action for record",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "event_name": event_name,
                    "record_index": idx,
                    "inventory_id": failed_inventory_id,
                },
            )
            failed_records.append(record)

    # Always-on batch manifest: one searchable line per batch listing every
    # document ID and object name. CloudWatch-filter by InventoryID or name
    # to confirm whether a specific asset ever reached this lambda.
    logger.info(
        "Batch manifest",
        extra={
            "total_records": len(records),
            "actions_prepared": len(bulk_actions),
            "failed_preparations": len(failed_records),
            "index_docs": batch_manifest["index"],
            "update_docs": batch_manifest["update"],
            "delete_docs": batch_manifest["delete"],
            "skipped_lock_records": batch_manifest["skipped_lock"],
        },
    )

    return bulk_actions, action_to_record_map, failed_records


# ---------------------------------------------------------------------------
# Self-healing for dynamic-mapping conflicts
# ---------------------------------------------------------------------------
# Three weeks of prd ERROR logs showed >10k documents rejected outright with
# mapper_parsing_exception / illegal_argument_exception: dynamic mapping
# locked arbitrary EmbeddedMetadata fields as long/date, then later assets
# sent strings ("inches", "W1W 6XH", "Custom", locale-formatted dates...).
# The static blocklists above can never keep up (40+ distinct field paths and
# growing), so when OpenSearch names the offending field in its error we drop
# that one field from the document and retry. The full value always remains
# in DynamoDB; only the un-indexable field is omitted from the search doc.
# ---------------------------------------------------------------------------

_MAPPER_FIELD_PATTERNS = (
    # mapper_parsing_exception: failed to parse field [X] of type [long] ...
    re.compile(r"failed to parse field \[(.+?)\] of type \["),
    # illegal_argument_exception: mapper [X] cannot be changed from type ...
    re.compile(r"mapper \[(.+?)\] cannot be changed from type"),
    # object mapping conflicts: object mapping for [X] tried to parse ...
    re.compile(r"object mapping for \[(.+?)\] tried to parse"),
    # dynamic mapping failures for new fields
    re.compile(r"Could not dynamically add mapping for field \[(.+?)\]"),
)


def _extract_conflicting_field_path(error_reason: str) -> Optional[str]:
    """Pull the offending field path out of an OpenSearch mapper error."""
    for pattern in _MAPPER_FIELD_PATTERNS:
        m = pattern.search(error_reason or "")
        if m:
            return m.group(1)
    return None


def _remove_field_path(node: Any, segments: List[str]) -> bool:
    """
    Remove a field from a nested document given its flattened OpenSearch path.

    OpenSearch reports paths like "Metadata.EmbeddedMetadata.Exif.Custom
    Rendered.value" with dots as separators, but document keys may themselves
    contain dots. Try the longest multi-segment key match first at every
    level, and descend into lists (OS paths never include array indices).

    Returns True if a field was removed.
    """
    if not segments:
        return False
    if isinstance(node, list):
        removed = False
        for item in node:
            if _remove_field_path(item, segments):
                removed = True
        return removed
    if not isinstance(node, dict):
        return False
    for take in range(len(segments), 0, -1):
        key = ".".join(segments[:take])
        if key in node:
            if take == len(segments):
                del node[key]
                return True
            if _remove_field_path(node[key], segments[take:]):
                return True
    return False


def _action_document_body(action: dict) -> Optional[dict]:
    """Return the mutable document body of a bulk action (index or update)."""
    if action.get("_op_type") == "index":
        body = action.get("_source")
    elif action.get("_op_type") == "update":
        body = action.get("doc")
    else:
        body = None
    return body if isinstance(body, dict) else None


def estimate_bulk_size(actions: List[dict]) -> int:
    """Estimate the size of bulk actions in bytes."""
    return len(json.dumps(actions, cls=DecimalEncoder).encode("utf-8"))


def chunk_bulk_actions(actions: List[dict]) -> List[List[dict]]:
    """
    Split bulk actions into chunks based on size and count limits.

    Returns:
        List of action chunks
    """
    chunks = []
    current_chunk = []
    current_size = 0
    max_size_bytes = MAX_BULK_SIZE_MB * 1024 * 1024

    for action in actions:
        action_size = len(json.dumps(action, cls=DecimalEncoder).encode("utf-8"))

        if (
            len(current_chunk) >= BULK_BATCH_SIZE
            or current_size + action_size > max_size_bytes
        ):
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_size = 0

        current_chunk.append(action)
        current_size += action_size

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


# max_retries trimmed 15 -> 8 (2026-07-23): at 15 a sustained 429 storm held
# a batch slot for ~11.5 minutes of sleep inside one invocation, stalling the
# stream shard and aging the iterator (observed 6-9.6h lag in prd). At 8 the
# worst case is ~4.5 minutes; the event source mapping's own retries (3x with
# DLQ on-failure) still protect the records themselves.
@retry_with_backoff(max_retries=8, base_delay=3, max_delay=60)
def execute_bulk_operation(
    actions: List[dict], action_to_record_map: dict
) -> Tuple[int, List[dict], dict]:
    """
    Execute bulk operation on OpenSearch with retry logic for 429 errors.

    Args:
        actions: List of bulk actions to execute
        action_to_record_map: Mapping of document_id to original DynamoDB record

    Returns:
        Tuple of (success_count, failed_records, error_details_map)
        error_details_map: dict mapping document_id to error details
    """
    if not actions:
        return 0, [], {}

    chunk_start = time.time()
    action_types = {
        "index": len([a for a in actions if a.get("_op_type") == "index"]),
        "update": len([a for a in actions if a.get("_op_type") == "update"]),
        "delete": len([a for a in actions if a.get("_op_type") == "delete"]),
    }
    logger.info(
        f"Executing bulk operation with {len(actions)} actions",
        extra={
            "target_index": INDEX,
            "action_types": action_types,
            "mapping_size": len(action_to_record_map),
        },
    )

    # streaming_bulk with yield_ok=True gives us the per-item OpenSearch
    # response for BOTH successes and failures, so every document can be
    # positively confirmed (result: created/updated/deleted) instead of
    # success being inferred from a bare count.
    success = 0
    failed = []
    # Per-doc positive confirmations: doc_id -> "op:result:status"
    # e.g. "index:created:201", "update:updated:200", "delete:deleted:200"
    success_manifest = {}
    for ok, item in streaming_bulk(
        opensearch_client,
        actions,
        raise_on_error=False,
        raise_on_exception=False,
        max_retries=0,
        yield_ok=True,
    ):
        op = next(iter(item))
        info = item[op]
        if ok:
            success += 1
            success_manifest[info.get("_id", "unknown")] = (
                f"{op}:{info.get('result', '?')}:{info.get('status', '?')}"
            )
        else:
            failed.append(item)

    failed_records = []
    error_details_map = {}
    has_429_errors = False
    # Delete-404s are expected: the ingest connector deletes OpenSearch docs
    # directly during file replacement, so the stream's REMOVE arrives after
    # the doc is already gone. Track them separately so they don't read as
    # (or get DLQ'd as) real failures.
    expected_delete_404_ids = []
    # Mapping-conflict failures we will try to self-heal by stripping the
    # offending field and retrying: doc_id -> latest error reason.
    heal_candidates: Dict[str, str] = {}
    actions_by_id = {a.get("_id"): a for a in actions}

    if failed:
        if VERBOSE_LOGGING:
            logger.info(f"Processing {len(failed)} failed items from bulk operation")

        for idx, item in enumerate(failed):
            # Determine which operation type failed and extract its response
            op_type = "unknown"
            error_info = {}
            for op in ("index", "update", "delete"):
                if op in item:
                    op_type = op
                    error_info = item[op]
                    break
            status = error_info.get("status", 0)
            item_id = error_info.get("_id", "unknown")
            error_details = error_info.get("error", {})
            result = error_info.get("result", "unknown")

            # Mapping conflict on an index/update: OpenSearch names the
            # offending field. Queue for self-healing (strip field + retry)
            # instead of failing the whole document straight to the DLQ.
            _raw_reason = (
                error_details.get("reason", "")
                if isinstance(error_details, dict)
                else str(error_details)
            )
            if (
                op_type in ("index", "update")
                and status == 400
                and item_id in actions_by_id
                and _extract_conflicting_field_path(_raw_reason)
                and _action_document_body(actions_by_id[item_id]) is not None
            ):
                heal_candidates[item_id] = _raw_reason
                continue

            # Expected case: DELETE for a doc the connector already removed
            # directly (file replacement flow). Not a real failure - log at
            # INFO, count it, and skip the DLQ.
            if op_type == "delete" and status == 404:
                expected_delete_404_ids.append(item_id)
                logger.info(
                    "Delete target already absent in OpenSearch (expected: "
                    "connector deletes docs directly on file replacement)",
                    extra={
                        "item_id": item_id,
                        "op_type": op_type,
                        "status": status,
                        "result": result,
                    },
                )
                continue

            # Build a rich error reason that captures all available context
            if error_details and isinstance(error_details, dict):
                error_type = error_details.get("type", "unknown")
                error_reason = error_details.get("reason", "No reason in error payload")
                caused_by = error_details.get("caused_by", {})
            elif error_details:
                error_type = "unknown"
                error_reason = str(error_details)
                caused_by = {}
            else:
                # No error payload — synthesize a reason from the status and result
                error_type = f"http_{status}"
                error_reason = (
                    f"Bulk {op_type} returned status {status} "
                    f"with result '{result}' but no error payload. "
                    f"This typically means the document was not found "
                    f"(for update/delete) or the index does not exist."
                    if status == 404
                    else f"Bulk {op_type} returned status {status} with result '{result}' and no error payload"
                )
                caused_by = {}

            detailed_error_info = {
                "status": status,
                "op_type": op_type,
                "result": result,
                "error_type": error_type,
                "error_reason": error_reason,
                "error_index": error_info.get("_index", INDEX),
                "opensearch_error": (
                    json.dumps(error_details, cls=DecimalEncoder)
                    if error_details
                    else "{}"
                ),
            }
            if caused_by:
                detailed_error_info["caused_by_type"] = caused_by.get("type", "unknown")
                detailed_error_info["caused_by_reason"] = caused_by.get(
                    "reason", "unknown"
                )

            if status == 429:
                has_429_errors = True
                logger.warning(
                    "Bulk operation item failed with 429 - Too Many Requests",
                    extra={"item_id": item_id, "status": status, "op_type": op_type},
                )
            else:
                logger.error(
                    "Bulk operation item failed",
                    extra={
                        "error": (
                            error_details
                            if error_details
                            else {"synthesized": error_reason}
                        ),
                        "status": status,
                        "item_id": item_id,
                        "op_type": op_type,
                        "result": result,
                        "error_type": detailed_error_info["error_type"],
                        "error_reason": detailed_error_info["error_reason"],
                        "error_index": detailed_error_info["error_index"],
                        **(
                            {
                                "caused_by_type": detailed_error_info["caused_by_type"],
                                "caused_by_reason": detailed_error_info[
                                    "caused_by_reason"
                                ],
                            }
                            if caused_by
                            else {}
                        ),
                    },
                )

            # Map failed action back to original record
            if item_id in action_to_record_map:
                failed_records.append(action_to_record_map[item_id])
                error_details_map[item_id] = detailed_error_info
                if VERBOSE_LOGGING:
                    logger.info(
                        f"Mapped failed action to original record",
                        extra={
                            "item_id": item_id,
                            "status": status,
                            "op_type": op_type,
                            "result": result,
                            "failed_item_index": idx,
                            "error_type": detailed_error_info["error_type"],
                        },
                    )
            else:
                logger.warning(
                    f"Failed to map document_id {item_id} back to original record"
                )

    # ------------------------------------------------------------------
    # Self-heal mapping conflicts: strip the field OpenSearch rejected and
    # retry the document. A doc can conflict on several fields, so iterate
    # a few rounds. Documents that still fail go to the DLQ as before.
    # ------------------------------------------------------------------
    healed_docs: Dict[str, List[str]] = {}
    if heal_candidates:
        MAX_HEAL_ROUNDS = 8
        # Docs from some vendor flows (e.g. "Laudert Studio Flow") carry
        # dozens of string values in fields dynamic mapping locked as long.
        # Removing one leaf per round can't converge (observed: 5 rounds
        # exhausted, asset:uuid:ac331190 still failing on the 6th field of
        # the same group). From ESCALATE_FROM_ROUND on, remove progressively
        # broader ancestor SUBTREES of the failing field - one level up per
        # round - so conflicts clustered in one branch (e.g. "Main Articles")
        # are cleared without sacrificing healthy siblings (e.g. "Season").
        # The ceiling is the group directly under Metadata.EmbeddedMetadata;
        # EmbeddedMetadata itself is never removed. The full metadata always
        # remains in DynamoDB.
        ESCALATE_FROM_ROUND = 3
        pending = dict(heal_candidates)
        removed_fields: Dict[str, List[str]] = {i: [] for i in pending}

        def _removal_target(
            segments: List[str], heal_round: int
        ) -> Tuple[List[str], str]:
            """Removal target for this round.

            Rounds 1..ESCALATE_FROM_ROUND-1: the leaf field itself.
            Later rounds (EmbeddedMetadata paths only): back off one ancestor
            level per round, from the leaf's containing object up to - at
            most - Metadata.EmbeddedMetadata.<Group> (segments[:3]).
            """
            under_embedded = (
                len(segments) > 3
                and segments[0] == "Metadata"
                and segments[1] == "EmbeddedMetadata"
            )
            if heal_round < ESCALATE_FROM_ROUND or not under_embedded:
                return segments, "leaf"
            steps_up = heal_round - ESCALATE_FROM_ROUND + 1
            n = max(3, len(segments) - steps_up)
            return segments[:n], ("entire group" if n == 3 else "subtree")

        def _mark_unhealable(doc_id: str, reason: str, status: int = 400):
            error_details_map[doc_id] = {
                "status": status,
                "op_type": actions_by_id[doc_id].get("_op_type", "unknown"),
                "result": "unhealable_mapping_conflict",
                "error_type": "mapper_conflict_unhealed",
                "error_reason": reason,
                "error_index": INDEX,
                "opensearch_error": "{}",
                "removed_fields": ",".join(removed_fields.get(doc_id, [])),
            }
            if doc_id in action_to_record_map:
                failed_records.append(action_to_record_map[doc_id])
            logger.error(
                "Mapping conflict could not be healed - sending to DLQ",
                extra={
                    "item_id": doc_id,
                    "error_reason": reason,
                    "fields_removed_before_giving_up": removed_fields.get(doc_id, []),
                },
            )

        for heal_round in range(1, MAX_HEAL_ROUNDS + 1):
            retry_actions = []
            for doc_id in list(pending.keys()):
                reason = pending[doc_id]
                action = actions_by_id[doc_id]
                body = _action_document_body(action)
                path = _extract_conflicting_field_path(reason)
                segments = path.split(".") if path else []
                removal_label = path
                if segments:
                    segments, kind = _removal_target(segments, heal_round)
                    if kind != "leaf":
                        removal_label = ".".join(segments) + f" ({kind})"
                if (
                    body is None
                    or not segments
                    or not _remove_field_path(body, segments)
                ):
                    _mark_unhealable(
                        doc_id,
                        f"Could not locate/remove conflicting field "
                        f"'{removal_label}' in document: {reason}",
                    )
                    del pending[doc_id]
                    continue
                removed_fields[doc_id].append(removal_label)
                retry_actions.append(action)

            if not retry_actions:
                break

            logger.info(
                f"Heal round {heal_round}: retrying {len(retry_actions)} docs "
                "after stripping conflicting fields",
                extra={
                    "heal_round": heal_round,
                    "doc_ids": [a.get("_id") for a in retry_actions],
                },
            )

            for ok, item in streaming_bulk(
                opensearch_client,
                retry_actions,
                raise_on_error=False,
                raise_on_exception=False,
                max_retries=0,
                yield_ok=True,
            ):
                op = next(iter(item))
                info = item[op]
                doc_id = info.get("_id", "unknown")
                if ok:
                    success += 1
                    healed_docs[doc_id] = removed_fields.get(doc_id, [])
                    success_manifest[doc_id] = (
                        f"{op}:{info.get('result', '?')}:"
                        f"{info.get('status', '?')}:healed"
                    )
                    logger.info(
                        "Healed mapping conflict - document indexed after "
                        "removing conflicting field(s)",
                        extra={
                            "item_id": doc_id,
                            "removed_fields": removed_fields.get(doc_id, []),
                            "heal_round": heal_round,
                        },
                    )
                    pending.pop(doc_id, None)
                else:
                    status = info.get("status", 0)
                    err = info.get("error", {})
                    reason = (
                        err.get("reason", str(err))
                        if isinstance(err, dict)
                        else str(err)
                    )
                    if status == 429:
                        has_429_errors = True
                        pending.pop(doc_id, None)  # chunk-level retry handles it
                    elif _extract_conflicting_field_path(reason):
                        pending[doc_id] = reason  # another field - next round
                    else:
                        _mark_unhealable(doc_id, reason, status)
                        pending.pop(doc_id, None)

        # Rounds exhausted with conflicts remaining
        for doc_id, reason in pending.items():
            _mark_unhealable(
                doc_id, f"Heal rounds exhausted ({MAX_HEAL_ROUNDS}): {reason}"
            )

        if healed_docs:
            metrics.add_metric(
                name="MappingConflictsHealed", unit="Count", value=len(healed_docs)
            )

    # If we got 429 errors, raise exception to trigger retry with backoff
    if has_429_errors:
        raise Exception(
            f"OpenSearch returned 429 errors for {len([f for f in failed if (f.get('index', f.get('update', f.get('delete', {}))).get('status') == 429)])} items"
        )

    real_failure_count = len(failed_records)
    metrics.add_metric(name="BulkOperationSuccess", unit="Count", value=success)
    metrics.add_metric(
        name="BulkOperationFailed", unit="Count", value=real_failure_count
    )
    if expected_delete_404_ids:
        metrics.add_metric(
            name="ExpectedDelete404",
            unit="Count",
            value=len(expected_delete_404_ids),
        )

    # Always-on chunk outcome: positively confirms EVERY document in the
    # chunk. success_docs maps doc_id -> "op:result:status" straight from the
    # OpenSearch per-item response, so "asset X was indexed" is provable by
    # CloudWatch-filtering on its InventoryID - not inferred from a count.
    logger.info(
        "Bulk chunk outcome",
        extra={
            "target_index": INDEX,
            "took_ms": int((time.time() - chunk_start) * 1000),
            "success_count": success,
            "failed_count": real_failure_count,
            "expected_delete_404_count": len(expected_delete_404_ids),
            "expected_delete_404_ids": expected_delete_404_ids,
            "healed_docs": healed_docs,
            "success_docs": success_manifest,
            "failed_ids": list(error_details_map.keys()),
        },
    )

    return success, failed_records, error_details_map


def _coerce_error_status(status) -> int:
    """
    Return an HTTP-status-like integer for the DLQ's Number attribute.

    OpenSearch errors do not always carry a numeric status (a connection
    timeout has none), and a non-numeric value makes SQS reject the entire
    SendMessage, which loses the record instead of parking it. 0 means
    "no status reported".
    """
    if isinstance(status, bool):
        return 0
    if isinstance(status, int):
        return status
    try:
        return int(str(status).strip())
    except (TypeError, ValueError):
        return 0


def send_to_dlq(records: List[dict], reason: str, error_details_map: dict = None):
    """
    Send failed records to DLQ with detailed error information.

    Args:
        records: List of DynamoDB stream records that failed
        reason: General failure reason
        error_details_map: Optional dict mapping InventoryID to detailed error info
    """
    if error_details_map is None:
        error_details_map = {}

    for record in records:
        try:
            event_name = record.get("eventName")

            if event_name == "REMOVE":
                document = sanitize_document(
                    dynamodb_item_to_dict(record["dynamodb"]["OldImage"])
                )
                message_type = "Delete the Index"
            elif event_name in ["INSERT", "MODIFY"]:
                document = sanitize_document(
                    dynamodb_item_to_dict(record["dynamodb"]["NewImage"])
                )
                message_type = (
                    "Insert the Index" if event_name == "INSERT" else "Modify the Index"
                )
            else:
                continue

            inventory_id = document.get("InventoryID", "unknown")
            error_details = error_details_map.get(inventory_id, {})

            message_attributes = {
                "MessageType": {"DataType": "String", "StringValue": message_type},
                "FailureReason": {"DataType": "String", "StringValue": reason},
                "EventName": {"DataType": "String", "StringValue": event_name},
                "InventoryID": {"DataType": "String", "StringValue": inventory_id},
            }

            if error_details:
                message_attributes.update(
                    {
                        # Declared as Number, so the value MUST parse as one.
                        # OpenSearch failures without an HTTP status (connection
                        # timeouts report status None) used to render as "None"
                        # here, and SQS rejected the whole SendMessage with
                        # InvalidParameterValue — silently discarding the record
                        # instead of parking it on the DLQ.
                        "ErrorStatus": {
                            "DataType": "Number",
                            "StringValue": str(
                                _coerce_error_status(error_details.get("status"))
                            ),
                        },
                        "ErrorType": {
                            "DataType": "String",
                            "StringValue": error_details.get("error_type", "unknown"),
                        },
                        "ErrorReason": {
                            "DataType": "String",
                            "StringValue": error_details.get(
                                "error_reason", "No reason provided"
                            )[:256],
                        },
                        "ErrorIndex": {
                            "DataType": "String",
                            "StringValue": error_details.get("error_index", INDEX),
                        },
                    }
                )

                opensearch_error = error_details.get("opensearch_error", "{}")
                if len(opensearch_error) <= 256:
                    message_attributes["OpenSearchError"] = {
                        "DataType": "String",
                        "StringValue": opensearch_error,
                    }

            sqs.send_message(
                QueueUrl=SQS_URL,
                MessageBody=json.dumps(document, cls=DecimalEncoder),
                MessageAttributes=message_attributes,
            )

            metrics.add_metric(name="DLQMessagesSent", unit="Count", value=1)

            if VERBOSE_LOGGING:
                logger.info(
                    "Sent record to DLQ",
                    extra={
                        "inventory_id": inventory_id,
                        "reason": reason,
                        "error_status": error_details.get("status"),
                        "error_type": error_details.get("error_type"),
                    },
                )

        except Exception as e:
            logger.error(
                f"Failed to send record to DLQ",
                extra={"error": str(e), "record": record},
            )


@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event, context):
    logger.info("Lambda invoked", extra={"aws_request_id": context.aws_request_id})

    records = event.get("Records", [])
    total_records = len(records)

    logger.info(f"Processing {total_records} records from DynamoDB stream")
    metrics.add_metric(name="RecordsReceived", unit="Count", value=total_records)

    # Stream lag: age of the oldest record in this batch. If this grows, the
    # indexer is falling behind the DynamoDB stream and "asset in DynamoDB but
    # not in search" is a lag problem, not a failure problem.
    try:
        creation_times = [
            float(r["dynamodb"]["ApproximateCreationDateTime"])
            for r in records
            if r.get("dynamodb", {}).get("ApproximateCreationDateTime") is not None
        ]
        if creation_times:
            lag_seconds = max(0.0, time.time() - min(creation_times))
            logger.info(
                "Stream batch lag",
                extra={
                    "oldest_record_age_seconds": round(lag_seconds, 1),
                    "batch_size": total_records,
                },
            )
            metrics.add_metric(
                name="StreamLagSeconds", unit="Seconds", value=lag_seconds
            )
    except Exception as lag_err:  # never let diagnostics break processing
        logger.warning(f"Could not compute stream lag: {lag_err}")

    try:
        if VERBOSE_LOGGING:
            logger.info(
                "Starting bulk action preparation",
                extra={"total_records": total_records},
            )

        # Prepare bulk actions with mapping
        bulk_actions, action_to_record_map, failed_prep = prepare_bulk_actions(records)

        if failed_prep:
            logger.warning(f"Failed to prepare {len(failed_prep)} records")
            if VERBOSE_LOGGING:
                logger.info(
                    "Sending failed preparation records to DLQ",
                    extra={"failed_prep_count": len(failed_prep)},
                )
            send_to_dlq(failed_prep, "Failed to prepare bulk action")

        if not bulk_actions:
            logger.info("No bulk actions to process")
            return {"statusCode": 200, "body": json.dumps("No actions to process")}

        # Split into chunks if needed
        action_chunks = chunk_bulk_actions(bulk_actions)
        logger.info(
            f"Split {len(bulk_actions)} actions into {len(action_chunks)} chunks"
        )

        if VERBOSE_LOGGING:
            logger.info(
                "Chunk details",
                extra={
                    "total_actions": len(bulk_actions),
                    "chunk_count": len(action_chunks),
                    "chunk_sizes": [len(chunk) for chunk in action_chunks],
                },
            )

        total_success = 0
        total_failed = 0

        # Process each chunk
        for i, chunk in enumerate(action_chunks):
            try:
                logger.info(
                    f"Processing chunk {i+1}/{len(action_chunks)} with {len(chunk)} actions"
                )

                success_count, failed_records, error_details = execute_bulk_operation(
                    chunk, action_to_record_map
                )
                total_success += success_count
                total_failed += len(failed_records)

                if failed_records:
                    logger.warning(f"Chunk {i+1} had {len(failed_records)} failures")
                    if VERBOSE_LOGGING:
                        logger.info(
                            f"Sending {len(failed_records)} failed records from chunk {i+1} to DLQ",
                            extra={
                                "chunk_number": i + 1,
                                "failed_count": len(failed_records),
                                "error_types": list(
                                    set(
                                        e.get("error_type")
                                        for e in error_details.values()
                                    )
                                ),
                            },
                        )
                    send_to_dlq(failed_records, "Bulk operation failed", error_details)
                elif VERBOSE_LOGGING:
                    logger.info(f"Chunk {i+1} completed successfully with no failures")

            except Exception as e:
                logger.error(
                    f"Failed to process chunk {i+1}",
                    extra={"error": str(e), "chunk_size": len(chunk)},
                )
                # Map chunk actions back to original records
                chunk_failed_records = []
                for action in chunk:
                    doc_id = action.get("_id")
                    if doc_id and doc_id in action_to_record_map:
                        chunk_failed_records.append(action_to_record_map[doc_id])
                        if VERBOSE_LOGGING:
                            logger.info(
                                f"Mapped failed chunk action to record",
                                extra={"document_id": doc_id, "chunk": i + 1},
                            )
                    else:
                        logger.warning(
                            f"Could not map action with id {doc_id} to original record"
                        )

                if chunk_failed_records:
                    if VERBOSE_LOGGING:
                        logger.info(
                            f"Sending {len(chunk_failed_records)} chunk failure records to DLQ",
                            extra={
                                "chunk": i + 1,
                                "failed_count": len(chunk_failed_records),
                            },
                        )
                    send_to_dlq(
                        chunk_failed_records, f"Chunk processing failed: {str(e)}"
                    )
                total_failed += len(chunk)

        logger.info(
            f"Bulk processing completed",
            extra={
                "total_records": total_records,
                "success": total_success,
                "failed": total_failed,
                "chunks": len(action_chunks),
            },
        )

        metrics.add_metric(
            name="RecordsProcessedSuccess", unit="Count", value=total_success
        )
        metrics.add_metric(
            name="RecordsProcessedFailed", unit="Count", value=total_failed
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Processing completed",
                    "total_records": total_records,
                    "success": total_success,
                    "failed": total_failed,
                }
            ),
        }

    except Exception as e:
        logger.exception("Unhandled exception processing stream")
        metrics.add_metric(name="UnhandledErrors", unit="Count", value=1)

        # Send all records to DLQ as fallback
        send_to_dlq(records, f"Unhandled exception: {str(e)}")

        return {"statusCode": 500, "body": json.dumps(f"Error processing stream: {e}")}
