"""DELETE /collections/<collection_id>/rules/<rule_id> - Delete rule."""

import os
import sys

from aws_lambda_powertools import Logger, Metrics, Tracer

sys.path.insert(0, "/opt/python")
from collections_utils import (
    COLLECTION_PK_PREFIX,
    create_error_response,
    create_success_response,
)

logger = Logger(
    service="collections-ID-rules-ID-delete", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-rules-ID-delete")
metrics = Metrics(namespace="medialake", service="collection-rules")

RULE_SK_PREFIX = "RULE#"


def register_route(app, dynamodb, table_name):
    """Register DELETE /collections/<collection_id>/rules/<rule_id> route"""

    @app.delete("/collections/<collection_id>/rules/<rule_id>")
    @tracer.capture_method
    def collections_ID_rules_ID_delete(collection_id: str, rule_id: str):
        """Delete collection rule"""
        try:
            table = dynamodb.Table(table_name)

            table.delete_item(
                Key={
                    "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                    "SK": f"{RULE_SK_PREFIX}{rule_id}",
                }
            )

            logger.info(f"Rule {rule_id} deleted")

            return create_success_response(
                data={"id": rule_id, "deleted": True},
                request_id=app.current_event.request_context.request_id,
            )

        except Exception as e:
            logger.exception("Error deleting rule", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
