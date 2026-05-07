"""POST /collections/<collection_id>/rules - Create rule."""

import json
import os
import uuid
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from collections_utils import (
    COLLECTION_PK_PREFIX,
    RULE_SK_PREFIX,
    create_error_response,
)
from db_models import RuleModel
from user_auth import extract_user_context
from utils.formatting_utils import format_rule

logger = Logger(
    service="collections-ID-rules-post", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-rules-post")
metrics = Metrics(namespace="medialake", service="collection-rules")


def register_route(app):
    """Register POST /collections/<collection_id>/rules route"""

    @app.post("/collections/<collection_id>/rules")
    @tracer.capture_method
    def collections_ID_rules_post(collection_id: str):
        """Create collection rule"""
        try:
            extract_user_context(app.current_event.raw_event)
            request_data = app.current_event.json_body

            current_timestamp = datetime.utcnow().isoformat() + "Z"
            rule_id = f"rule_{str(uuid.uuid4())[:8]}"

            # Create rule model instance
            rule = RuleModel()
            rule.PK = f"{COLLECTION_PK_PREFIX}{collection_id}"
            rule.SK = f"{RULE_SK_PREFIX}{rule_id}"
            rule.name = request_data["name"]
            rule.ruleType = request_data["ruleType"]
            rule.criteria = request_data["criteria"]
            rule.isActive = request_data.get("isActive", True)
            rule.priority = request_data.get("priority", 0)
            rule.matchCount = 0
            rule.createdAt = current_timestamp
            rule.updatedAt = current_timestamp

            if request_data.get("description"):
                rule.description = request_data["description"]

            # Save to DynamoDB
            rule.save()

            logger.info(f"Rule created for collection {collection_id}")
            metrics.add_metric(
                name="SuccessfulRuleCreations", unit=MetricUnit.Count, value=1
            )

            # Convert to dict for formatting
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

            return {
                "statusCode": 201,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": format_rule(rule_dict),
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
