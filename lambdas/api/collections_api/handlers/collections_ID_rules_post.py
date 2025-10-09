"""POST /collections/<collection_id>/rules - Create rule."""

import json
import os
import uuid
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from collections_utils import COLLECTION_PK_PREFIX
from user_auth import extract_user_context
from utils.formatting_utils import format_rule

logger = Logger(
    service="collections-ID-rules-post", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-rules-post")
metrics = Metrics(namespace="medialake", service="collection-rules")

RULE_SK_PREFIX = "RULE#"


def register_route(app, dynamodb, table_name):
    """Register POST /collections/<collection_id>/rules route"""

    @app.post("/collections/<collection_id>/rules")
    @tracer.capture_method
    def collections_ID_rules_post(collection_id: str):
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
                        "data": format_rule(rule),
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
            from collections_utils import create_error_response

            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
