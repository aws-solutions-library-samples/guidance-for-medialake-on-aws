"""POST /collections/<collection_id>/share - Share collection."""

import json
import os
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError,
)
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError, parse
from collections_utils import (
    COLLECTION_PK_PREFIX,
    METADATA_SK,
    PERM_SK_PREFIX,
    USER_PK_PREFIX,
    get_user_collection_role,
)
from custom_exceptions import ForbiddenError
from db_models import CollectionModel, ShareModel, UserRelationshipModel
from models import ShareCollectionRequest
from pynamodb.connection import Connection
from pynamodb.exceptions import DoesNotExist
from pynamodb.transactions import TransactWrite
from user_auth import extract_user_context
from utils.formatting_utils import format_share

logger = Logger(
    service="collections-ID-share-post", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="collections-ID-share-post")
metrics = Metrics(namespace="medialake", service="collection-shares")


def register_route(app):
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

            granter_id = user_context.get("user_id")
            if not granter_id:
                raise BadRequestError("Authentication required")

            # Authorize: the collection must exist and only its owner may
            # manage who it is shared with.
            try:
                collection = CollectionModel.get(
                    f"{COLLECTION_PK_PREFIX}{collection_id}", METADATA_SK
                )
            except DoesNotExist:
                raise NotFoundError(f"Collection '{collection_id}' not found")

            if get_user_collection_role(collection, granter_id) != "OWNER":
                logger.warning(
                    f"User {granter_id} attempted to share collection "
                    f"{collection_id} they do not own"
                )
                raise ForbiddenError(
                    "Only the collection owner can share this collection"
                )

            # Create permission model instance
            permission = ShareModel()
            permission.PK = f"{COLLECTION_PK_PREFIX}{collection_id}"
            permission.SK = f"{PERM_SK_PREFIX}{target_id}"
            permission.targetType = "user"
            permission.targetId = target_id
            permission.role = role
            permission.grantedBy = granter_id
            permission.grantedAt = current_timestamp

            # GSI6 - For "shared by me" queries
            permission.GSI6_PK = f"GRANTOR#{granter_id}"
            permission.GSI6_SK = f"{COLLECTION_PK_PREFIX}{collection_id}"

            if request_data.message:
                permission.message = request_data.message

            # Create user relationship model instance
            user_relationship = UserRelationshipModel()
            user_relationship.PK = f"{USER_PK_PREFIX}{target_id}"
            user_relationship.SK = f"{COLLECTION_PK_PREFIX}{collection_id}"
            user_relationship.relationship = role.upper()
            user_relationship.addedAt = current_timestamp
            user_relationship.lastAccessed = current_timestamp
            user_relationship.isFavorite = False
            user_relationship.GSI1_PK = f"{USER_PK_PREFIX}{target_id}"
            user_relationship.GSI1_SK = current_timestamp
            user_relationship.GSI2_PK = f"{COLLECTION_PK_PREFIX}{collection_id}"
            user_relationship.GSI2_SK = f"{USER_PK_PREFIX}{target_id}"

            # Transactional write
            connection = Connection(region=os.environ.get("AWS_REGION", "us-east-1"))
            with TransactWrite(connection=connection) as transaction:
                transaction.save(permission)
                transaction.save(user_relationship)

            logger.info(f"Collection {collection_id} shared with {target_id}")
            metrics.add_metric(
                name="SuccessfulShareOperations", unit=MetricUnit.Count, value=1
            )

            # Convert to dict for formatting
            permission_dict = {
                "PK": permission.PK,
                "SK": permission.SK,
                "targetType": permission.targetType,
                "targetId": permission.targetId,
                "role": permission.role,
                "grantedBy": permission.grantedBy,
                "grantedAt": permission.grantedAt,
            }
            if permission.message:
                permission_dict["message"] = permission.message

            from aws_lambda_powertools.event_handler import Response, content_types

            return Response(
                status_code=201,
                content_type=content_types.APPLICATION_JSON,
                body=json.dumps(
                    {
                        "success": True,
                        "data": format_share(permission_dict),
                        "meta": {
                            "timestamp": current_timestamp,
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            )

        except (BadRequestError, ForbiddenError, NotFoundError):
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
