"""
External Metadata Fetch Node Lambda Handler.

This Lambda function orchestrates the external metadata enrichment process:
1. Extracts or uses override correlation ID
2. Authenticates with external system
3. Fetches metadata from external API
4. Normalizes metadata
5. Stores metadata in DynamoDB asset record
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

# Conditional import for lambda_middleware to support local testing
# When running locally, the middleware can be mocked before importing this module
try:
    from lambda_middleware import lambda_middleware
except ImportError:
    # Provide a no-op decorator for local testing
    def lambda_middleware(**kwargs):
        def decorator(fn):
            return fn

        return decorator


# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.adapters import AdapterConfig, create_adapter
    from nodes.external_metadata_fetch.auth import AuthConfig, create_auth_strategy
    from nodes.external_metadata_fetch.correlation_id import (
        CorrelationIdError,
        resolve_correlation_id,
    )
    from nodes.external_metadata_fetch.dynamodb_operations import (
        update_asset_external_asset_id,
        update_asset_status_failed,
        update_asset_status_pending,
        update_asset_with_metadata,
    )
    from nodes.external_metadata_fetch.normalizer import MetadataNormalizer
    from nodes.external_metadata_fetch.normalizers import resolve_normalizer_config
    from nodes.external_metadata_fetch.retry import RetryConfig, execute_with_retry
    from nodes.external_metadata_fetch.secrets_retriever import (
        AuthenticationError,
        CredentialRetrievalError,
        SecretsRetriever,
    )
except ImportError:
    from adapters import AdapterConfig, create_adapter
    from auth import AuthConfig, create_auth_strategy
    from correlation_id import CorrelationIdError, resolve_correlation_id
    from dynamodb_operations import (
        update_asset_external_asset_id,
        update_asset_status_failed,
        update_asset_status_pending,
        update_asset_with_metadata,
    )
    from normalizer import MetadataNormalizer
    from normalizers import resolve_normalizer_config
    from retry import RetryConfig, execute_with_retry
    from secrets_retriever import (
        AuthenticationError,
        CredentialRetrievalError,
        SecretsRetriever,
    )

logger = Logger(service="external-metadata-fetch")
tracer = Tracer()


@dataclass
class NodeConfig:
    """Configuration for the External Metadata Fetch Node.

    Attributes:
        adapter_type: Type of metadata adapter (e.g., "generic_rest")
        auth_type: Type of authentication (e.g., "oauth2_client_credentials", "api_key", "basic_auth")
        secret_arn: AWS Secrets Manager ARN for credentials
        auth_endpoint: OAuth/token endpoint URL (may be empty for API key/basic auth)
        metadata_endpoint: Metadata API endpoint URL
        max_retries: Maximum retry attempts for transient errors
        initial_backoff_seconds: Initial backoff delay for retries
        auth_config: Auth strategy-specific configuration
        adapter_config: Adapter-specific configuration
        normalizer_config: Normalizer configuration section containing:
            - source_type: Normalizer type (e.g., "generic_xml")
            - config: Inline normalizer configuration
            - config_s3_path: S3 path to configuration file
    """

    adapter_type: str
    auth_type: str
    secret_arn: str
    auth_endpoint: str
    metadata_endpoint: str
    max_retries: int = 3
    initial_backoff_seconds: float = 1.0
    auth_config: dict[str, Any] | None = None
    adapter_config: dict[str, Any] | None = None
    normalizer_config: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> NodeConfig:
        """Create NodeConfig from a dictionary.

        Args:
            config: Configuration dictionary

        Returns:
            NodeConfig instance

        Raises:
            ValueError: If required fields are missing
        """
        required_fields = [
            "adapter_type",
            "auth_type",
            "secret_arn",
            "metadata_endpoint",
        ]
        missing = [f for f in required_fields if not config.get(f)]
        if missing:
            raise ValueError(f"Missing required configuration fields: {missing}")

        return cls(
            adapter_type=config["adapter_type"],
            auth_type=config["auth_type"],
            secret_arn=config["secret_arn"],
            auth_endpoint=config.get("auth_endpoint", ""),
            metadata_endpoint=config["metadata_endpoint"],
            max_retries=config.get("max_retries", 3),
            initial_backoff_seconds=config.get("initial_backoff_seconds", 1.0),
            auth_config=config.get("auth_config"),
            adapter_config=config.get("adapter_config"),
            normalizer_config=config.get("normalizer_config"),
        )


class EnrichmentStatus:
    """Enumeration of enrichment status values for Step Function routing.

    These status values are used by the Step Function Choice node to route
    to the appropriate end state:
    - SUCCESS: Metadata successfully retrieved and stored -> Success end state
    - NO_MATCH: Correlation ID invalid, missing, or not found -> NoMatch Fail state
    - AUTH_ERROR: Authentication failures -> AuthError Fail state
    - ERROR: Unexpected errors (HTTP 500, unhandled exceptions) -> Error Fail state
    """

    SUCCESS = "success"
    NO_MATCH = "no_match"
    AUTH_ERROR = "auth_error"
    ERROR = "error"


@dataclass
class EnrichmentResult:
    """Result of an enrichment operation.

    Attributes:
        success: Whether the enrichment succeeded
        enrichment_status: Status for Step Function routing (success, no_match, auth_error, error)
        correlation_id: The correlation ID used for lookup
        metadata: The normalized metadata (if successful)
        error_message: Error message (if failed)
        attempt_count: Number of attempts made
    """

    success: bool
    enrichment_status: str = EnrichmentStatus.ERROR
    correlation_id: str | None = None
    metadata: dict[str, Any] | None = None
    error_message: str | None = None
    attempt_count: int = 0


def _get_node_config(event: dict[str, Any]) -> NodeConfig:
    """Extract node configuration from the event.

    The configuration can come from:
    1. Environment variables (for Lambda deployment)
    2. Event payload data (for testing or dynamic configuration)

    Args:
        event: The standardized Lambda event

    Returns:
        NodeConfig instance

    Raises:
        ValueError: If configuration is invalid or missing
    """
    # Try to get config from event payload first (for testing/dynamic config)
    payload_data = event.get("payload", {}).get("data", {})
    node_config = payload_data.get("node_config", {})

    # Build auth_config from environment variables if not in event
    auth_config = node_config.get("auth_config")
    if not auth_config:
        # Build auth_config from environment variables
        auth_config = {}
        scope = os.environ.get("SCOPE", "")
        if scope:
            auth_config["scope"] = scope

    # Build adapter_config from environment variables if not in event
    adapter_config = node_config.get("adapter_config")
    if not adapter_config:
        adapter_config = {}
        correlation_id_param = os.environ.get("CORRELATION_ID_PARAM", "")
        if correlation_id_param:
            adapter_config["correlation_id_param"] = correlation_id_param
        response_metadata_path = os.environ.get("RESPONSE_METADATA_PATH", "")
        if response_metadata_path:
            adapter_config["response_metadata_path"] = response_metadata_path

    # Get normalizer_config from event or environment variables
    normalizer_config = node_config.get("normalizer_config")
    if not normalizer_config:
        # Build normalizer_config from environment variables
        normalizer_source_type = os.environ.get("NORMALIZER_SOURCE_TYPE", "")
        normalizer_config_s3_path = os.environ.get("NORMALIZER_CONFIG_S3_PATH", "")
        if normalizer_source_type or normalizer_config_s3_path:
            normalizer_config = {}
            if normalizer_source_type:
                normalizer_config["source_type"] = normalizer_source_type
            if normalizer_config_s3_path:
                normalizer_config["config_s3_path"] = normalizer_config_s3_path

    # Fall back to environment variables
    config = {
        "adapter_type": node_config.get("adapter_type")
        or os.environ.get("ADAPTER_TYPE", ""),
        "auth_type": node_config.get("auth_type") or os.environ.get("AUTH_TYPE", ""),
        "secret_arn": node_config.get("secret_arn") or os.environ.get("SECRET_ARN", ""),
        "auth_endpoint": node_config.get("auth_endpoint")
        or os.environ.get("AUTH_ENDPOINT", ""),
        "metadata_endpoint": node_config.get("metadata_endpoint")
        or os.environ.get("METADATA_ENDPOINT", ""),
        "max_retries": node_config.get("max_retries")
        or int(os.environ.get("MAX_RETRIES", "3")),
        "initial_backoff_seconds": node_config.get("initial_backoff_seconds")
        or float(os.environ.get("INITIAL_BACKOFF_SECONDS", "1.0")),
        "auth_config": auth_config if auth_config else None,
        "adapter_config": adapter_config if adapter_config else None,
        "normalizer_config": normalizer_config if normalizer_config else None,
    }

    return NodeConfig.from_dict(config)


def _get_correlation_id_override(event: dict[str, Any]) -> str | None:
    """Extract correlation ID override from event params.

    The correlation_id can be in different locations depending on how the
    pipeline was triggered:

    1. Via trigger API with params nesting: payload.data.params.correlation_id
       (when trigger API preserves the {"params": {"correlation_id": "..."}} structure)

    2. Via trigger API with flattened params: payload.data.correlation_id
       (when trigger API flattens the item structure)

    3. Via middleware map handling: payload.data.correlation_id
       (when middleware puts item_obj directly into payload.data)

    Args:
        event: The standardized Lambda event

    Returns:
        Correlation ID override if provided, None otherwise
    """
    payload_data = event.get("payload", {}).get("data", {})

    # Check nested params location first (from trigger API with params nesting)
    params = payload_data.get("params", {})
    if isinstance(params, dict) and params.get("correlation_id"):
        return params.get("correlation_id")

    # Fall back to direct location (flattened or middleware map handling)
    return payload_data.get("correlation_id")


def _get_filename_from_asset(asset: dict[str, Any]) -> str | None:
    """Extract filename from asset record.

    The filename can be found in multiple locations in the asset record.
    This function checks them in order of preference:

    1. MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name
       (most specific - just the filename)

    2. StoragePath (root level, format: "bucket:filename" or just "filename")
       (fallback - may need to extract filename from path)

    Args:
        asset: Asset record from DynamoDB

    Returns:
        Filename if found, None otherwise
    """
    # Try the most specific path first: ObjectKey.Name
    digital_source = asset.get("DigitalSourceAsset", {})
    main_rep = digital_source.get("MainRepresentation", {})
    storage_info = main_rep.get("StorageInfo", {})
    primary_location = storage_info.get("PrimaryLocation", {})
    object_key = primary_location.get("ObjectKey", {})

    filename = object_key.get("Name")
    if filename:
        return filename

    # Fallback: try FullPath and extract just the filename
    full_path = object_key.get("FullPath")
    if full_path:
        # FullPath might be "path/to/file.mp4" - extract just the filename
        return full_path.split("/")[-1] if "/" in full_path else full_path

    # Last resort: try StoragePath at root level
    # Format is typically "bucket:filename" or "bucket:path/filename"
    storage_path = asset.get("StoragePath")
    if storage_path:
        # Remove bucket prefix if present (format: "bucket:path")
        if ":" in storage_path:
            path_part = storage_path.split(":", 1)[1]
        else:
            path_part = storage_path
        # Extract just the filename from the path
        return path_part.split("/")[-1] if "/" in path_part else path_part

    return None


def _get_inventory_id(asset: dict[str, Any]) -> str:
    """Extract inventory ID from asset record.

    Args:
        asset: Asset record from DynamoDB

    Returns:
        Inventory ID

    Raises:
        ValueError: If inventory ID is not found
    """
    inventory_id = asset.get("InventoryID")
    if not inventory_id:
        raise ValueError("Asset record missing InventoryID")
    return inventory_id


def _get_existing_external_id(asset: dict[str, Any]) -> str | None:
    """Extract existing ExternalAssetId from asset record if previous lookup succeeded.

    This is used to preserve previously successful correlation IDs
    when re-running enrichment without an explicit override.

    Only returns the existing ID if:
    1. ExternalAssetId is present and non-empty
    2. ExternalMetadataStatus.status is "success" (previous lookup worked)

    This prevents re-using a bad correlation ID that was set during a
    failed attempt (e.g., extracted from filename but API returned no data).

    Args:
        asset: Asset record from DynamoDB

    Returns:
        ExternalAssetId if present, non-empty, and previous lookup succeeded; None otherwise
    """
    external_id = asset.get("ExternalAssetId")
    if not external_id or not isinstance(external_id, str) or not external_id.strip():
        return None

    # Check if previous lookup was successful
    metadata_status = asset.get("ExternalMetadataStatus", {})
    if not isinstance(metadata_status, dict):
        return None

    status = metadata_status.get("status")
    if status != "success":
        # Previous attempt failed or status unknown - don't trust the existing ID
        return None

    return external_id.strip()


def _is_no_match_error(error_message: str) -> bool:
    """Check if an error message indicates a "no match" condition.

    "No match" errors occur when the correlation ID is invalid, missing,
    or not found in the external system. These are distinct from auth errors
    or unexpected system errors.

    Common patterns include:
    - 404 Not Found responses
    - Empty responses (API returns no content or empty XML)
    - "Asset not found" messages
    - "No data" or "No results" messages
    - Correlation ID validation failures (empty, missing, cannot extract)

    Args:
        error_message: The error message to check

    Returns:
        True if the error indicates a no-match condition
    """
    if not error_message:
        return False

    error_lower = error_message.lower()

    # Patterns that indicate the asset/correlation ID was not found
    no_match_patterns = [
        # HTTP status and general not found
        "not found",
        "404",
        "does not exist",
        "unknown asset",
        "asset not found",
        "no match",
        # Empty response patterns
        "empty response",  # Covers "empty response from API"
        "empty xml",  # Covers "empty xml response from API"
        "no data",
        "no results",
        "no metadata",
        # Correlation ID validation failures
        "cannot be empty",  # From correlation_id.py and generic_rest.py
        "cannot determine correlation",  # From correlation_id.py
        "failed to extract correlation",  # From correlation_id.py
        "invalid correlation",
    ]

    return any(pattern in error_lower for pattern in no_match_patterns)


def process_asset(
    asset: dict[str, Any],
    node_config: NodeConfig,
    correlation_id_override: str | None,
    secrets_retriever: SecretsRetriever,
    normalizer: MetadataNormalizer,
) -> EnrichmentResult:
    """Process a single asset for metadata enrichment.

    This function orchestrates the full enrichment flow:
    1. Extract or use override correlation ID
    2. Update asset with ExternalAssetId and pending status
    3. Authenticate with external system
    4. Fetch metadata with retry logic
    5. Normalize metadata
    6. Store metadata in asset record

    Args:
        asset: Asset record from DynamoDB
        node_config: Node configuration
        correlation_id_override: Optional correlation ID override from params
        secrets_retriever: SecretsRetriever instance for credential management
        normalizer: MetadataNormalizer instance

    Returns:
        EnrichmentResult with success/failure status and metadata
    """
    inventory_id = _get_inventory_id(asset)
    correlation_id: str | None = None
    attempt_count = 0

    try:
        # Step 1: Resolve correlation ID
        # Priority: override > existing ExternalAssetId > filename extraction
        filename = _get_filename_from_asset(asset)
        existing_external_id = _get_existing_external_id(asset)
        correlation_result = resolve_correlation_id(
            filename=filename,
            override_correlation_id=correlation_id_override,
            existing_external_id=existing_external_id,
        )
        correlation_id = correlation_result.correlation_id

        logger.info(
            "Resolved correlation ID",
            extra={
                "inventory_id": inventory_id,
                "correlation_id": correlation_id,
                "source": correlation_result.source,
            },
        )

        # Step 2: Update asset with ExternalAssetId and pending status
        update_asset_external_asset_id(inventory_id, correlation_id)
        update_asset_status_pending(inventory_id)

        # Step 3: Create auth strategy and authenticate
        auth_config = AuthConfig(
            auth_endpoint_url=node_config.auth_endpoint,
            additional_config=node_config.auth_config or {},
        )
        auth_strategy = create_auth_strategy(node_config.auth_type, auth_config)

        credentials = secrets_retriever.get_credentials(node_config.secret_arn)
        auth_result = secrets_retriever.get_auth(
            auth_strategy=auth_strategy,
            credentials=credentials,
            cache_key=node_config.secret_arn,
        )

        # Extract additional headers from credentials (if present)
        # These are stored in the secret alongside auth credentials for security
        credential_headers: dict[str, str] | None = credentials.get(
            "additional_headers"
        )

        logger.info(
            "Authentication successful",
            extra={
                "inventory_id": inventory_id,
                "auth_type": node_config.auth_type,
                "has_credential_headers": credential_headers is not None,
            },
        )

        # Step 4: Create adapter and fetch metadata with retry
        adapter_config = AdapterConfig(
            metadata_endpoint=node_config.metadata_endpoint,
            additional_config=node_config.adapter_config or {},
        )
        adapter = create_adapter(
            adapter_type=node_config.adapter_type,
            config=adapter_config,
            auth_strategy=auth_strategy,
        )

        retry_config = RetryConfig(
            max_retries=node_config.max_retries,
            initial_backoff_seconds=node_config.initial_backoff_seconds,
        )

        def fetch_operation():
            return adapter.fetch_metadata(
                correlation_id, auth_result, credential_headers
            )

        retry_result = execute_with_retry(
            operation=fetch_operation,
            config=retry_config,
            operation_name=f"fetch_metadata:{correlation_id}",
        )

        attempt_count = retry_result.attempt_count

        if not retry_result.success or retry_result.result is None:
            raise RuntimeError(retry_result.error_message or "Metadata fetch failed")

        fetch_result = retry_result.result
        if not fetch_result.success or fetch_result.raw_metadata is None:
            raise RuntimeError(fetch_result.error_message or "Metadata fetch failed")

        logger.info(
            "Metadata fetch successful",
            extra={
                "inventory_id": inventory_id,
                "correlation_id": correlation_id,
                "attempt_count": attempt_count,
            },
        )

        # Step 5: Normalize metadata
        source_system = adapter.get_full_source_name()
        normalized = normalizer.normalize(
            raw_metadata=fetch_result.raw_metadata,
            source_system=source_system,
            correlation_id=correlation_id,
        )

        # Step 6: Store metadata in asset record
        # Handle both NormalizedMetadata objects and dicts
        if isinstance(normalized, dict):
            normalized_dict = normalized
        else:
            normalized_dict = normalized.to_dict()
        update_asset_with_metadata(inventory_id, normalized_dict)

        logger.info(
            "Enrichment completed successfully",
            extra={
                "inventory_id": inventory_id,
                "correlation_id": correlation_id,
            },
        )

        return EnrichmentResult(
            success=True,
            enrichment_status=EnrichmentStatus.SUCCESS,
            correlation_id=correlation_id,
            metadata=normalized_dict,
            attempt_count=attempt_count,
        )

    except CorrelationIdError as e:
        error_msg = f"Correlation ID error: {e}"
        logger.error(error_msg, extra={"inventory_id": inventory_id})
        update_asset_status_failed(inventory_id, error_msg, attempt_count)
        return EnrichmentResult(
            success=False,
            enrichment_status=EnrichmentStatus.NO_MATCH,
            correlation_id=correlation_id,
            error_message=error_msg,
            attempt_count=attempt_count,
        )

    except CredentialRetrievalError as e:
        error_msg = f"Credential retrieval error: {e}"
        logger.error(error_msg, extra={"inventory_id": inventory_id})
        update_asset_status_failed(inventory_id, error_msg, attempt_count)
        return EnrichmentResult(
            success=False,
            enrichment_status=EnrichmentStatus.AUTH_ERROR,
            correlation_id=correlation_id,
            error_message=error_msg,
            attempt_count=attempt_count,
        )

    except AuthenticationError as e:
        error_msg = f"Authentication error: {e}"
        logger.error(error_msg, extra={"inventory_id": inventory_id})
        update_asset_status_failed(inventory_id, error_msg, attempt_count)
        return EnrichmentResult(
            success=False,
            enrichment_status=EnrichmentStatus.AUTH_ERROR,
            correlation_id=correlation_id,
            error_message=error_msg,
            attempt_count=attempt_count,
        )

    except Exception as e:
        error_msg = str(e)
        # Check if this is a "not found" type error (no_match)
        # These include: 404 responses, empty XML responses, asset not found messages
        is_no_match = _is_no_match_error(error_msg)
        enrichment_status = (
            EnrichmentStatus.NO_MATCH if is_no_match else EnrichmentStatus.ERROR
        )

        logger.exception(
            "Enrichment failed",
            extra={
                "inventory_id": inventory_id,
                "correlation_id": correlation_id,
                "error": error_msg,
                "enrichment_status": enrichment_status,
            },
        )
        update_asset_status_failed(inventory_id, error_msg, attempt_count)
        return EnrichmentResult(
            success=False,
            enrichment_status=enrichment_status,
            correlation_id=correlation_id,
            error_message=error_msg,
            attempt_count=attempt_count,
        )


@lambda_middleware(event_bus_name=os.environ.get("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """
    Main handler for external metadata fetch node.

    Event structure (normalized by middleware):
    {
        "metadata": {...},
        "payload": {
            "data": {
                "params": {"correlation_id": "ABC123"},  # Optional override
                "node_config": {...}  # Optional dynamic config
            },
            "assets": [
                {
                    "InventoryID": "...",
                    "DigitalSourceAsset": {
                        "FileName": "ABC123.mp4",
                        ...
                    }
                }
            ]
        }
    }

    The node:
    1. Extracts correlation_id (from params or filename)
    2. Creates the appropriate AuthStrategy based on auth_type config
    3. Creates the appropriate MetadataAdapter with the auth strategy
    4. Authenticates using the auth strategy
    5. Fetches metadata using the adapter
    6. Normalizes and stores the metadata

    Args:
        event: Standardized Lambda event from middleware
        context: Lambda context

    Returns:
        Response with enrichment results for each asset
    """
    logger.info(
        "External metadata fetch node started", extra={"event_keys": list(event.keys())}
    )

    try:
        # Get node configuration
        node_config = _get_node_config(event)

        # Get correlation ID override from params
        correlation_id_override = _get_correlation_id_override(event)

        # Get assets to process
        assets = event.get("payload", {}).get("assets", [])
        if not assets:
            raise ValueError("No assets provided in event payload")

        # Initialize shared components
        secrets_retriever = SecretsRetriever()

        # Create normalizer with configuration (if provided)
        normalizer_config = node_config.normalizer_config
        if normalizer_config:
            source_type = normalizer_config.get("source_type")
            resolved_config = resolve_normalizer_config(normalizer_config)
            normalizer = MetadataNormalizer(
                source_type=source_type,
                config=resolved_config,
            )
        else:
            # Use placeholder normalizer for backward compatibility
            normalizer = MetadataNormalizer()

        # Process each asset
        results: list[dict[str, Any]] = []
        success_count = 0
        failure_count = 0
        # Track the last enrichment_status for single-asset case
        last_enrichment_status = EnrichmentStatus.ERROR

        for asset in assets:
            result = process_asset(
                asset=asset,
                node_config=node_config,
                correlation_id_override=correlation_id_override,
                secrets_retriever=secrets_retriever,
                normalizer=normalizer,
            )

            if result.success:
                success_count += 1
            else:
                failure_count += 1

            last_enrichment_status = result.enrichment_status

            results.append(
                {
                    "inventory_id": asset.get("InventoryID"),
                    "success": result.success,
                    "enrichment_status": result.enrichment_status,
                    "correlation_id": result.correlation_id,
                    "error_message": result.error_message,
                    "attempt_count": result.attempt_count,
                }
            )

        # Determine overall enrichment_status for Step Function routing
        # For single asset: use that asset's status
        # For multiple assets: use "success" if all succeeded, otherwise use the first failure's status
        if len(results) == 1:
            overall_enrichment_status = last_enrichment_status
        elif failure_count == 0:
            overall_enrichment_status = EnrichmentStatus.SUCCESS
        else:
            # Find the first failure's status
            for r in results:
                if not r["success"]:
                    overall_enrichment_status = r["enrichment_status"]
                    break
            else:
                overall_enrichment_status = EnrichmentStatus.ERROR

        logger.info(
            "External metadata fetch node completed",
            extra={
                "total_assets": len(assets),
                "success_count": success_count,
                "failure_count": failure_count,
                "enrichment_status": overall_enrichment_status,
            },
        )

        return {
            "statusCode": 200,
            "body": {
                "message": "External metadata enrichment completed",
                "enrichment_status": overall_enrichment_status,
                "total_assets": len(assets),
                "success_count": success_count,
                "failure_count": failure_count,
                "results": results,
            },
        }

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return {
            "statusCode": 400,
            "body": {
                "error": str(e),
                "message": "Invalid configuration or input",
                "enrichment_status": EnrichmentStatus.ERROR,
            },
        }

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return {
            "statusCode": 500,
            "body": {
                "error": str(e),
                "message": "Internal server error",
                "enrichment_status": EnrichmentStatus.ERROR,
            },
        }
