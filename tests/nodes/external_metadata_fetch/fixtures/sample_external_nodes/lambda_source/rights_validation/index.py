"""
Rights Validation Lambda handler stub for testing.

This is a minimal stub used by ExternalNodesSynthHelper tests to verify
that external node Lambda source files are correctly staged from S3.
"""

from __future__ import annotations

from typing import Any


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Validate distribution rights against an external rights management system.

    Args:
        event: Pipeline event containing asset data and rights validation config.
        context: Lambda context.

    Returns:
        Validation results per asset with clearance status.
    """
    assets = event.get("payload", {}).get("assets", [])
    node_config = event.get("payload", {}).get("data", {}).get("node_config", {})

    territory_codes = [
        t.strip()
        for t in node_config.get("territory_codes", "US").split(",")
        if t.strip()
    ]
    block_on_failure = node_config.get("block_on_failure", True)
    results: list[dict[str, Any]] = []

    for asset in assets:
        inventory_id = asset.get("InventoryID", "unknown")
        results.append(
            {
                "inventory_id": inventory_id,
                "territories_checked": territory_codes,
                "all_cleared": True,
                "clearance_details": {
                    territory: {"cleared": True, "expires": None}
                    for territory in territory_codes
                },
                "status": "success",
            }
        )

    return {
        "statusCode": 200,
        "body": {
            "message": "Rights validation completed",
            "total_assets": len(assets),
            "all_cleared": all(r["all_cleared"] for r in results),
            "block_on_failure": block_on_failure,
            "results": results,
        },
    }
