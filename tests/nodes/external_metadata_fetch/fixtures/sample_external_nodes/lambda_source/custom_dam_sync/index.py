"""
Custom DAM Sync Lambda handler stub for testing.

This is a minimal stub used by ExternalNodesSynthHelper tests to verify
that external node Lambda source files are correctly staged from S3.
"""

from __future__ import annotations

from typing import Any


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Synchronize metadata with an external DAM system.

    Args:
        event: Pipeline event containing asset data and DAM sync configuration.
        context: Lambda context.

    Returns:
        Sync result with per-asset status.
    """
    assets = event.get("payload", {}).get("assets", [])
    node_config = event.get("payload", {}).get("data", {}).get("node_config", {})

    sync_direction = node_config.get("sync_direction", "pull")
    results: list[dict[str, Any]] = []

    for asset in assets:
        inventory_id = asset.get("InventoryID", "unknown")
        results.append(
            {
                "inventory_id": inventory_id,
                "sync_direction": sync_direction,
                "status": "success",
            }
        )

    return {
        "statusCode": 200,
        "body": {
            "message": "DAM sync completed",
            "total_assets": len(assets),
            "results": results,
        },
    }
