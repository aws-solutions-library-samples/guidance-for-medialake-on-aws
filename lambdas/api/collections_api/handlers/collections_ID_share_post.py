"""POST /collections/<collection_id>/share - Share collection."""

import json
import os
import sys
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError, parse

sys.path.insert(0, "/opt/python")
from collections_utils import COLLECTION_PK_PREFIX, USER_PK_PREFIX
from models import ShareCollectionRequest
from user_auth import extract_user_context
from utils.formatting_utils import format_share

logger = Logger(
    service="collections-ID-share-post", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-share-post")
metrics = Metrics(namespace="medialake", service="collection-shares")

PERM_SK_PREFIX = "PERM#"


def register_route(app, dynamodb, table_name):
    """Register POST /collections/<collection_id>/share route"""

    @app.post("/collections/<collection_id>/share")
    @tracer.capture_method
    def collections_ID_share_post(collection_id: str):
        """Share collection with user or group with Pydantic validation"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)

            # Parse and validate with Pydantic
            try:
                request_data = parse(
                    event=app.current_event.json_body,
                    model=ShareCollectionRequest,
                )
            except ValidationError as e:
                logger.warning(f"Validation error sharing collection: {e}")
                raise BadRequestError(f"Validation error: {str(e)}")

            current_timestamp = datetime.utcnow().isoformat() + "Z"

            target_id = request_data.targetUserId
            role = request_data.accessLevel.value

            # Create permission item
            permission_item = {
                "PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "SK": f"{PERM_SK_PREFIX}{target_id}",
                "targetType": "user",
                "targetId": target_id,
                "role": role,
                "grantedBy": user_context.get("user_id"),
                "grantedAt": current_timestamp,
            }

            if request_data.message:
                permission_item["message"] = request_data.message

            # Create user relationship item
            user_relationship_item = {
                "PK": f"{USER_PK_PREFIX}{target_id}",
                "SK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "relationship": role.upper(),
                "addedAt": current_timestamp,
                "lastAccessed": current_timestamp,
                "isFavorite": False,
                "GSI1_PK": f"{USER_PK_PREFIX}{target_id}",
                "GSI1_SK": current_timestamp,
                "GSI2_PK": f"{COLLECTION_PK_PREFIX}{collection_id}",
                "GSI2_SK": f"{USER_PK_PREFIX}{target_id}",
            }

            # Transactional write
            dynamodb.meta.client.transact_write_items(
                TransactItems=[
                    {"Put": {"TableName": table_name, "Item": permission_item}},
                    {"Put": {"TableName": table_name, "Item": user_relationship_item}},
                ]
            )

            logger.info(f"Collection {collection_id} shared with {target_id}")
            metrics.add_metric(
                name="SuccessfulShareOperations", unit=MetricUnit.Count, value=1
            )

            return {
                "statusCode": 201,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": format_share(permission_item),
                        "meta": {
                            "timestamp": current_timestamp,
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        except BadRequestError:
            raise
        except Exception as e:
            logger.exception("Error sharing collection", exc_info=e)
            from collections_utils import create_error_response

            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
