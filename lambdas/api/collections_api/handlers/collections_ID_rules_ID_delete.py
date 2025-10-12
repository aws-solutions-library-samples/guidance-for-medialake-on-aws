"""DELETE /collections/<collection_id>/rules/<rule_id> - Delete rule."""

import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from collections_utils import (
    COLLECTION_PK_PREFIX,
    RULE_SK_PREFIX,
    create_error_response,
    create_success_response,
)
from db_models import RuleModel
from pynamodb.exceptions import DeleteError, DoesNotExist

logger = Logger(
    service="collections-ID-rules-ID-delete", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-rules-ID-delete")
metrics = Metrics(namespace="medialake", service="collection-rules")


def register_route(app):
    """Register DELETE /collections/<collection_id>/rules/<rule_id> route"""

    @app.delete("/collections/<collection_id>/rules/<rule_id>")
    @tracer.capture_method
    def collections_ID_rules_ID_delete(collection_id: str, rule_id: str):
        """Delete collection rule"""
        try:
            pk = f"{COLLECTION_PK_PREFIX}{collection_id}"
            sk = f"{RULE_SK_PREFIX}{rule_id}"

            # Get the rule
            try:
                rule = RuleModel.get(pk, sk)
            except DoesNotExist:
                return create_error_response(
                    error_code="NotFound",
                    error_message=f"Rule {rule_id} not found",
                    status_code=404,
                    request_id=app.current_event.request_context.request_id,
                )

            # Delete the rule
            rule.delete()

            logger.info(f"Rule {rule_id} deleted")

            return create_success_response(
                data={"id": rule_id, "deleted": True},
                request_id=app.current_event.request_context.request_id,
            )

        except DeleteError as e:
            logger.exception("Error deleting rule", exc_info=e)
            return create_error_response(
                error_code="DeleteError",
                error_message=f"Failed to delete rule: {str(e)}",
                status_code=500,
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
