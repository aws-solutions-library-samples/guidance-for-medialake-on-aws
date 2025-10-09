"""PUT /collections/<collection_id>/rules/<rule_id> - Update rule."""

import os
import sys
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer

sys.path.insert(0, "/opt/python")
from collections_utils import (
    COLLECTION_PK_PREFIX,
    create_error_response,
    create_success_response,
)

logger = Logger(
    service="collections-ID-rules-ID-put", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-rules-ID-put")
metrics = Metrics(namespace="medialake", service="collection-rules")

RULE_SK_PREFIX = "RULE#"


def register_route(app, dynamodb, table_name):
    """Register PUT /collections/<collection_id>/rules/<rule_id> route"""

    @app.put("/collections/<collection_id>/rules/<rule_id>")
    @tracer.capture_method
    def collections_ID_rules_ID_put(collection_id: str, rule_id: str):
        """Update collection rule"""
        try:
            request_data = app.current_event.json_body
            table = dynamodb.Table(table_name)
            current_timestamp = datetime.utcnow().isoformat() + "Z"

            update_expr_parts = ["updatedAt = :timestamp"]
            expr_attr_values = {":timestamp": current_timestamp}

            if "name" in request_data:
                update_expr_parts.append("#name = :name")
                expr_attr_values[":name"] = request_data["name"]

            if "criteria" in request_data:
                update_expr_parts.append("criteria = :criteria")
                expr_attr_values[":criteria"] = request_data["criteria"]

            if "isActive" in request_data:
                update_expr_parts.append("isActive = :isActive")
                expr_attr_values[":isActive"] = request_data["isActive"]

            table.update_item(
                Key={
                    "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    "SK": f"{RULE_SK_PREFIX}{rule_id}",
                },
                UpdateExpression=f"SET {', '.join(update_expr_parts)}",
                ExpressionAttributeValues=expr_attr_values,
                ExpressionAttributeNames=(
                    {"#name": "name"} if "name" in request_data else None
                ),
            )

            logger.info(f"Rule {rule_id} updated")

            return create_success_response(
                data={"id": rule_id, "updatedAt": current_timestamp},
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error updating rule", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
