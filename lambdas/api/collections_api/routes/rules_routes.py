"""
Collection Rules Routes.

Handles collection rules operations:
- GET /collections/{collectionId}/rules - List collection rules
- POST /collections/{collectionId}/rules - Create rule
- PUT /collections/{collectionId}/rules/{ruleId} - Update rule
- DELETE /collections/{collectionId}/rules/{ruleId} - Delete rule
"""

import json
import os
import sys
import uuid
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

logger = Logger(service="rules-routes", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="rules-routes")
metrics = Metrics(namespace="medialake", service="collection-rules")

RULE_SK_PREFIX = "RULE#"


def register_routes(app, dynamodb, table_name):
    """Register collection rules routes"""

    @app.get("/collections/<collection_id>/rules")
    @tracer.capture_method
    def list_collection_rules(collection_id: str):
        """Get collection rules"""
        try:
            table = dynamodb.Table(table_name)

            response = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    ":sk_prefix": RULE_SK_PREFIX,
                },
            )

            items = response.get("Items", [])
            formatted_rules = [_format_rule(item) for item in items]

            return create_success_response(
                data=formatted_rules,
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error listing collection rules", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )

    @app.post("/collections/<collection_id>/rules")
    @tracer.capture_method
    def create_collection_rule(collection_id: str):
        """Create collection rule"""
        try:
            extract_user_context(app.current_event.raw_event)
            request_data = app.current_event.json_body

            table = dynamodb.Table(table_name)
            current_timestamp = datetime.utcnow().isoformat() + "Z"
            rule_id = f"rule_{str(uuid.uuid4())[:8]}"

            rule = {
                "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "SK": f"{RULE_SK_PREFIX}{rule_id}",
                "name": request_data["name"],
                "ruleType": request_data["ruleType"],
                "criteria": request_data["criteria"],
                "isActive": request_data.get("isActive", True),
                "priority": request_data.get("priority", 0),
                "matchCount": 0,
                "createdAt": current_timestamp,
                "updatedAt": current_timestamp,
            }

            if request_data.get("description"):
                rule["description"] = request_data["description"]

            table.put_item(Item=rule)

            logger.info(f"Rule created for collection {collection_id}")
            metrics.add_metric(
                name="SuccessfulRuleCreations", unit=MetricUnit.Count, value=1
            )

            return {
                "statusCode": 201,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": _format_rule(rule),
                        "meta": {
                            "timestamp": current_timestamp,
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        except Exception as e:
            logger.exception("Error creating collection rule", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )

    @app.put("/collections/<collection_id>/rules/<rule_id>")
    @tracer.capture_method
    def update_collection_rule(collection_id: str, rule_id: str):
        """Update collection rule"""
        try:
            request_data = app.current_event.json_body
            table = dynamodb.Table(table_name)
            current_timestamp = datetime.utcnow().isoformat() + "Z"

            update_expr = "SET updatedAt = :timestamp"
            expr_values = {":timestamp": current_timestamp}

            if "name" in request_data:
                update_expr += ", #name = :name"
                expr_values[":name"] = request_data["name"]

            if "criteria" in request_data:
                update_expr += ", criteria = :criteria"
                expr_values[":criteria"] = request_data["criteria"]

            if "isActive" in request_data:
                update_expr += ", isActive = :isActive"
                expr_values[":isActive"] = request_data["isActive"]

            table.update_item(
                Key={
                    "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    "SK": f"{RULE_SK_PREFIX}{rule_id}",
                },
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
                ExpressionAttributeNames=(
                    {"#name": "name"} if "name" in request_data else None
                ),
            )

            return create_success_response(
                data={"id": rule_id, "updated": True},
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error updating collection rule", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )

    @app.delete("/collections/<collection_id>/rules/<rule_id>")
    @tracer.capture_method
    def delete_collection_rule(collection_id: str, rule_id: str):
        """Delete collection rule"""
        try:
            table = dynamodb.Table(table_name)

            table.delete_item(
                Key={
                    "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    "SK": f"{RULE_SK_PREFIX}{rule_id}",
                }
            )

            logger.info(f"Rule deleted from collection {collection_id}")

            return create_success_response(
                data={"id": rule_id, "deleted": True},
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error deleting collection rule", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )


def _format_rule(item):
    """Format rule for API response"""
    sk_parts = item["SK"].split("#")
    rule_id = sk_parts[-1] if len(sk_parts) > 1 else item.get("ruleId", "")

    return {
        "id": rule_id,
        "name": item.get("name", ""),
        "description": item.get("description", ""),
        "ruleType": item.get("ruleType", ""),
        "criteria": item.get("criteria", {}),
        "isActive": item.get("isActive", True),
        "priority": item.get("priority", 0),
        "matchCount": item.get("matchCount", 0),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
    }
