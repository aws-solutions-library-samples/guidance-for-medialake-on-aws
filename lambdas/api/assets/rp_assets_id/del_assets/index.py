"""
Asset Deletion Lambda Handler
─────────────────────────────
• Uses centralized AssetDeletionService from common_libraries
• Simplified handler that delegates to shared deletion logic
• Maintains backward compatibility with existing API
"""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from typing import Any, Dict, Optional

from asset_deletion_service import AssetDeletionError, AssetDeletionService
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from personal_asset_access import caller_owns_personal_asset, get_caller_sub
from pydantic import BaseModel, Field

# ── Powertools ───────────────────────────────────────────────────────────────
logger = Logger(service="asset-deletion-api")
tracer = Tracer(service="asset-deletion-api")
metrics = Metrics(namespace="AssetDeletionAPI", service="asset-deletion-api")

# ── Environment ──────────────────────────────────────────────────────────────
DYNAMODB_TABLE_NAME = os.environ.get("MEDIALAKE_ASSET_TABLE", "")

# Module-level so the client is reused across invocations. Created lazily because the
# table name comes from the environment and is empty in some test contexts.
_asset_table = None


def _get_asset_table():
    global _asset_table
    if _asset_table is None and DYNAMODB_TABLE_NAME:
        import boto3

        _asset_table = boto3.resource("dynamodb").Table(DYNAMODB_TABLE_NAME)
    return _asset_table


@tracer.capture_method
def check_personal_asset_ownership(
    event, inventory_id: str
) -> Optional[Dict[str, Any]]:
    """Deny deleting another user's personal ("My Assets") asset.

    Deletion is delegated to AssetDeletionService, which does not authorize the caller, so
    without this check any authenticated user could destroy another user's private asset.

    Returns None when the delete may proceed, or a response to return to the caller.
    Fails closed: if ownership cannot be established the delete is refused, because the
    operation is irreversible. A missing asset is allowed through so the deletion service
    reports the usual 404 rather than this check leaking existence via 403.
    """
    table = _get_asset_table()
    if table is None:
        logger.error("Cannot verify asset ownership: asset table is not configured")
        return create_response(
            HTTPStatus.INTERNAL_SERVER_ERROR, "Internal configuration error"
        )

    try:
        item = (table.get_item(Key={"InventoryID": inventory_id}) or {}).get("Item")
    except Exception:
        logger.exception(
            "Cannot verify asset ownership; refusing delete",
            extra={"inventory_id": inventory_id},
        )
        return create_response(
            HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to verify asset ownership"
        )

    if item is None:
        return None

    if not caller_owns_personal_asset(item, get_caller_sub(event)):
        logger.warning(
            "Denying personal asset delete: caller is not the owner",
            extra={"inventory_id": inventory_id},
        )
        metrics.add_metric(name="PersonalAssetAccessDenied", unit="Count", value=1)
        return create_response(HTTPStatus.FORBIDDEN, "Access denied")

    return None


class DeleteRequest(BaseModel):
    inventoryId: str = Field(..., description="Inventory ID of the asset to delete")


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal types"""

    def default(self, o):
        from decimal import Decimal

        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def create_response(
    status: int, msg: str, data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create standardized API Gateway response"""
    body = {
        "status": "success" if status < 400 else "error",
        "message": msg,
        "data": data or {},
    }

    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True,
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: APIGatewayProxyEvent, _ctx: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for single asset deletion using centralized AssetDeletionService.

    Path: DELETE /api/assets/{id}
    """
    inventory_id = None
    try:
        # Extract inventory ID from path parameters
        path_params = event.get("pathParameters") or {}
        inventory_id = path_params.get("id")
        if not inventory_id:
            return create_response(
                HTTPStatus.BAD_REQUEST,
                "Missing inventory ID in path parameters",
            )

        logger.info(f"Starting deletion for asset: {inventory_id}")

        ownership_denial = check_personal_asset_ownership(event, inventory_id)
        if ownership_denial is not None:
            return ownership_denial

        # Use centralized deletion service
        deletion_service = AssetDeletionService(
            dynamodb_table_name=DYNAMODB_TABLE_NAME,
            logger=logger,
            metrics=metrics,
            tracer=tracer,
        )

        result = deletion_service.delete_asset(
            inventory_id=inventory_id, publish_event=True
        )

        # Return success response with deletion details
        return create_response(
            HTTPStatus.OK,
            "Asset deleted successfully",
            {
                "inventoryId": inventory_id,
                "s3ObjectsDeleted": result.s3_objects_deleted,
                "openSearchDocsDeleted": result.opensearch_docs_deleted,
                "vectorsDeleted": result.vectors_deleted,
                "externalServicesDeleted": len(result.external_services_deleted),
                "dynamodbDeleted": result.dynamodb_deleted,
                "eventPublished": result.event_published,
            },
        )

    except AssetDeletionError as e:
        logger.warning(
            "Asset deletion failed",
            extra={"inventory_id": inventory_id, "error": str(e)},
        )
        # Map to appropriate HTTP status
        status_code = (
            HTTPStatus.NOT_FOUND
            if "not found" in str(e).lower()
            else HTTPStatus.INTERNAL_SERVER_ERROR
        )
        return create_response(status_code, str(e))

    except Exception as e:
        logger.error(
            "Unexpected error during asset deletion",
            extra={"inventory_id": inventory_id, "error": str(e)},
            exc_info=True,
        )
        from aws_lambda_powertools.metrics import MetricUnit

        metrics.add_metric("AssetDeletionErrors", MetricUnit.Count, 1)
        return create_response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            f"An unexpected error occurred during asset deletion: {str(e)}",
        )
