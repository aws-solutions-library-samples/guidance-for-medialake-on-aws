"""PUT /collections/<collection_id>/rules/<rule_id> - Update rule."""

import os
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from collections_utils import (
    COLLECTION_PK_PREFIX,
    RULE_SK_PREFIX,
    create_error_response,
    create_success_response,
)
from db_models import RuleModel
from pynamodb.exceptions import DoesNotExist, UpdateError

logger = Logger(
    service="collections-ID-rules-ID-put", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-rules-ID-put")
metrics = Metrics(namespace="medialake", service="collection-rules")


def register_route(app):
    """Register PUT /collections/<collection_id>/rules/<rule_id> route"""

    @app.put("/collections/<collection_id>/rules/<rule_id>")
    @tracer.capture_method
    def collections_ID_rules_ID_put(collection_id: str, rule_id: str):
        """Update collection rule"""
        try:
            request_data = app.current_event.json_body
            current_timestamp = datetime.utcnow().isoformat() + "Z"

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

            # Build update actions
            actions = [RuleModel.updatedAt.set(current_timestamp)]

            if "name" in request_data:
                actions.append(RuleModel.name.set(request_data["name"]))

            if "criteria" in request_data:
                actions.append(RuleModel.criteria.set(request_data["criteria"]))

            if "isActive" in request_data:
                actions.append(RuleModel.isActive.set(request_data["isActive"]))

            if "priority" in request_data:
                actions.append(RuleModel.priority.set(request_data["priority"]))

            if "description" in request_data:
                actions.append(RuleModel.description.set(request_data["description"]))

            # Update the rule
            rule.update(actions=actions)

            logger.info(f"Rule {rule_id} updated")

            return create_success_response(
                data={"id": rule_id, "updatedAt": current_timestamp},
                request_id=app.current_event.request_context.request_id,
            )

        except UpdateError as e:
            logger.exception("Error updating rule", exc_info=e)
            return create_error_response(
                error_code="UpdateError",
                error_message=f"Failed to update rule: {str(e)}",
                status_code=500,
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
