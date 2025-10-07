"""
Collection Shares Routes.

Handles collection sharing operations:
- GET /collections/{collectionId}/share - List collection shares
- POST /collections/{collectionId}/share - Share collection
- DELETE /collections/{collectionId}/share/{userId} - Unshare collection
"""

import json
import os
import sys
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

sys.path.insert(0, "/opt/python")
from collections_utils import (
    COLLECTION_PK_PREFIX,
    create_error_response,
    create_success_response,
)
from user_auth import extract_user_context

logger = Logger(service="shares-routes", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="shares-routes")
metrics = Metrics(namespace="medialake", service="collection-shares")

PERM_SK_PREFIX = "PERM#"
USER_PK_PREFIX = "USER#"


def register_routes(app, dynamodb, table_name):
    """Register collection shares routes"""

    @app.get("/collections/<collection_id>/share")
    @tracer.capture_method
    def list_collection_shares(collection_id: str):
        """Get collection shares"""
        try:
            table = dynamodb.Table(table_name)

            response = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    ":sk_prefix": PERM_SK_PREFIX,
                },
            )

            items = response.get("Items", [])
            formatted_shares = [_format_share(item) for item in items]

            return create_success_response(
                data=formatted_shares,
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error listing collection shares", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )

    @app.post("/collections/<collection_id>/share")
    @tracer.capture_method
    def share_collection(collection_id: str):
        """Share collection with user or group"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            request_data = app.current_event.json_body

            dynamodb.Table(table_name)
            current_timestamp = datetime.utcnow().isoformat() + "Z"

            target_id = request_data["targetId"]
            target_type = request_data.get("targetType", "user")
            role = request_data.get("role", "viewer")

            # Create permission item
            permission_item = {
                "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "SK": f"{PERM_SK_PREFIX}{target_id}",
                "targetType": target_type,
                "targetId": target_id,
                "role": role,
                "grantedBy": user_context.get("user_id"),
                "grantedAt": current_timestamp,
            }

            # Create user relationship item
            user_relationship_item = {
                "PK": f"{USER_PK_PREFIX}{target_id}",
                "SK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "relationship": role.upper(),
                "addedAt": current_timestamp,
                "GSI1_PK": f"{USER_PK_PREFIX}{target_id}",
                "GSI1_SK": current_timestamp,
            }

            # Transactional write
            dynamodb.meta.client.transact_write_items(
                TransactItems=[
                    {"Put": {"TableName": table_name, "Item": permission_item}},
                    {"Put": {"TableName": table_name, "Item": user_relationship_item}},
                ]
            )

            logger.info(f"Collection {collection_id} shared with {target_id}")
            metrics.add_metric(name="SuccessfulShares", unit=MetricUnit.Count, value=1)

            return {
                "statusCode": 201,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": _format_share(permission_item),
                        "meta": {
                            "timestamp": current_timestamp,
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        except Exception as e:
            logger.exception("Error sharing collection", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )

    @app.delete("/collections/<collection_id>/share/<user_id>")
    @tracer.capture_method
    def unshare_collection(collection_id: str, user_id: str):
        """Unshare collection from user"""
        try:
            table = dynamodb.Table(table_name)

            # Delete permission item
            table.delete_item(
                Key={
                    "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    "SK": f"{PERM_SK_PREFIX}{user_id}",
                }
            )

            # Delete user relationship item
            table.delete_item(
                Key={
                    "PK": f"{USER_PK_PREFIX}{user_id}",
                    "SK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                }
            )

            logger.info(f"Collection {collection_id} unshared from {user_id}")

            return create_success_response(
                data={"userId": user_id, "unshared": True},
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error unsharing collection", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )


def _format_share(item):
    """Format share for API response"""
    target_id = item["SK"].replace(PERM_SK_PREFIX, "")
    return {
        "id": f"perm_{target_id}",
        "targetType": item.get("targetType", ""),
        "targetId": item.get("targetId", ""),
        "role": item.get("role", "viewer"),
        "grantedBy": item.get("grantedBy", ""),
        "grantedAt": item.get("grantedAt", ""),
    }
