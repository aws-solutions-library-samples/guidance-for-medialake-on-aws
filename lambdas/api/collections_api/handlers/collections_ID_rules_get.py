"""GET /collections/<collection_id>/rules - List collection rules."""

import os

from aws_lambda_powertools import Logger, Metrics, Tracer
from collections_utils import (
    COLLECTION_PK_PREFIX,
    RULE_SK_PREFIX,
    create_error_response,
    create_success_response,
)
from db_models import RuleModel
from utils.formatting_utils import format_rule

logger = Logger(
    service="collections-ID-rules-get", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-rules-get")
metrics = Metrics(namespace="medialake", service="collection-rules")


def register_route(app):
    """Register GET /collections/<collection_id>/rules route"""

    @app.get("/collections/<collection_id>/rules")
    @tracer.capture_method
    def collections_ID_rules_get(collection_id: str):
        """Get collection rules"""
        try:
            # Query rules for this collection
            rules = []
            for rule in RuleModel.query(
                f"{COLLECTION_PK_PREFIX}{collection_id}",
                RuleModel.SK.startswith(RULE_SK_PREFIX),
            ):
                rule_dict = {
                    "PK": rule.PK,
                    "SK": rule.SK,
                    "name": rule.name,
                    "ruleType": rule.ruleType,
                    "criteria": dict(rule.criteria) if rule.criteria else {},
                    "isActive": rule.isActive,
                    "priority": rule.priority,
                    "matchCount": rule.matchCount,
                    "createdAt": rule.createdAt,
                    "updatedAt": rule.updatedAt,
                }
                if rule.description:
                    rule_dict["description"] = rule.description
                rules.append(rule_dict)

            formatted_rules = [format_rule(item) for item in rules]

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
