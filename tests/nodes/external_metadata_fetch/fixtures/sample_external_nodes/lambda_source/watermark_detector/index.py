"""
Watermark Detector Lambda handler stub for testing.

This is a minimal stub used by ExternalNodesSynthHelper tests to verify
that external node Lambda source files are correctly staged from S3.
"""

from __future__ import annotations

from typing import Any


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Detect watermarks in video frames via an external CV API.

    Args:
        event: Pipeline event containing asset data and detection configuration.
        context: Lambda context.

    Returns:
        Detection results per asset.
    """
    assets = event.get("payload", {}).get("assets", [])
    node_config = event.get("payload", {}).get("data", {}).get("node_config", {})

    confidence_threshold = node_config.get("confidence_threshold", 0.85)
    results: list[dict[str, Any]] = []

    for asset in assets:
        inventory_id = asset.get("InventoryID", "unknown")
        results.append(
            {
                "inventory_id": inventory_id,
                "watermark_detected": False,
                "confidence": 0.0,
                "threshold": confidence_threshold,
                "frames_analyzed": 0,
                "status": "success",
            }
        )

    return {
        "statusCode": 200,
        "body": {
            "message": "Watermark detection completed",
            "total_assets": len(assets),
            "results": results,
        },
    }
