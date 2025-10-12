"""POST /collections - Create a new collection."""

import json
import os
import uuid
from datetime import datetime

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError, parse
from collections_utils import (
    CHILD_SK_PREFIX,
    COLLECTION_PK_PREFIX,
    COLLECTIONS_GSI5_PK,
    METADATA_SK,
    USER_PK_PREFIX,
    format_collection_item,
)
from db_models import ChildReferenceModel, CollectionModel, UserRelationshipModel
from models import CreateCollectionRequest
from pynamodb.connection import Connection
from pynamodb.transactions import TransactWrite
from user_auth import extract_user_context

logger = Logger(service="collections-post", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="collections-post")
metrics = Metrics(namespace="medialake", service="collections")


def register_route(app):
    """Register POST /collections route"""

    @app.post("/collections")
    @tracer.capture_method
    def collections_post():
        """Create a new collection with Pydantic V2 validation"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                raise BadRequestError(
                    "Valid authentication is required to create collections"
                )

            # Parse and validate request body using Pydantic
            try:
                request_data = parse(
                    event=app.current_event.json_body,
                    model=CreateCollectionRequest,
                )
            except ValidationError as e:
                logger.warning(f"Request validation error: {e}")
                metrics.add_metric(
                    name="ValidationErrors", unit=MetricUnit.Count, value=1
                )
                raise BadRequestError(f"Validation error: {str(e)}")

            # Generate ID and timestamp
            collection_id = f"col_{str(uuid.uuid4())[:8]}"
            current_timestamp = datetime.utcnow().isoformat() + "Z"

            # Create collection model instance
            collection = CollectionModel()
            collection.PK = f"{COLLECTION_PK_PREFIX}{collection_id}"
            collection.SK = METADATA_SK
            collection.name = request_data.name
            collection.ownerId = user_id
            collection.status = "ACTIVE"
            collection.itemCount = 0
            collection.childCollectionCount = 0
            collection.isPublic = request_data.isPublic
            collection.createdAt = current_timestamp
            collection.updatedAt = current_timestamp
            collection.GSI5_PK = COLLECTIONS_GSI5_PK
            collection.GSI5_SK = current_timestamp

            # Add optional fields from Pydantic model
            if request_data.description:
                collection.description = request_data.description
            if request_data.collectionTypeId:
                collection.collectionTypeId = request_data.collectionTypeId
                collection.GSI3_PK = request_data.collectionTypeId
                collection.GSI3_SK = f"{COLLECTION_PK_PREFIX}{collection_id}"
            if request_data.parentId:
                collection.parentId = request_data.parentId
            if request_data.metadata:
                collection.customMetadata = request_data.metadata
            if request_data.tags:
                collection.tags = request_data.tags

            # Create user relationship model instance
            user_relationship = UserRelationshipModel()
            user_relationship.PK = f"{USER_PK_PREFIX}{user_id}"
            user_relationship.SK = f"{COLLECTION_PK_PREFIX}{collection_id}"
            user_relationship.relationship = "OWNER"
            user_relationship.addedAt = current_timestamp
            user_relationship.lastAccessed = current_timestamp
            user_relationship.isFavorite = False
            user_relationship.GSI1_PK = f"{USER_PK_PREFIX}{user_id}"
            user_relationship.GSI1_SK = current_timestamp
            user_relationship.GSI2_PK = f"{COLLECTION_PK_PREFIX}{collection_id}"
            user_relationship.GSI2_SK = f"{USER_PK_PREFIX}{user_id}"

            # Execute transactional write
            # Create a proper Connection object for transactions
            connection = Connection(region=os.environ.get("AWS_REGION", "us-east-1"))
            with TransactWrite(connection=connection) as transaction:
                transaction.save(collection)
                transaction.save(user_relationship)

                # If this is a child collection, create CHILD# reference in parent
                if request_data.parentId:
                    # Create child reference item in parent's partition
                    child_reference = ChildReferenceModel()
                    child_reference.PK = (
                        f"{COLLECTION_PK_PREFIX}{request_data.parentId}"
                    )
                    child_reference.SK = f"{CHILD_SK_PREFIX}{collection_id}"
                    child_reference.childCollectionId = collection_id
                    child_reference.childCollectionName = request_data.name
                    child_reference.addedAt = current_timestamp
                    child_reference.type = "CHILD_COLLECTION"
                    child_reference.GSI4_PK = f"CHILD#{collection_id}"
                    child_reference.GSI4_SK = (
                        f"{COLLECTION_PK_PREFIX}{request_data.parentId}"
                    )

                    transaction.save(child_reference)

                    # Increment parent's childCollectionCount and update timestamp
                    parent_pk = f"{COLLECTION_PK_PREFIX}{request_data.parentId}"
                    parent = CollectionModel.get(parent_pk, METADATA_SK)
                    transaction.update(
                        parent,
                        actions=[
                            CollectionModel.childCollectionCount.add(1),
                            CollectionModel.updatedAt.set(current_timestamp),
                        ],
                    )

            logger.info(
                f"Collection created: {collection_id}",
                extra={"collection_id": collection_id},
            )
            metrics.add_metric(
                name="SuccessfulCollectionCreations", unit=MetricUnit.Count, value=1
            )

            # Format response - convert PynamoDB model to dict for formatting
            collection_dict = {
                "PK": collection.PK,
                "SK": collection.SK,
                "name": collection.name,
                "ownerId": collection.ownerId,
                "status": collection.status,
                "itemCount": collection.itemCount,
                "childCollectionCount": collection.childCollectionCount,
                "isPublic": collection.isPublic,
                "createdAt": collection.createdAt,
                "updatedAt": collection.updatedAt,
            }
            if collection.description:
                collection_dict["description"] = collection.description
            if collection.collectionTypeId:
                collection_dict["collectionTypeId"] = collection.collectionTypeId
            if collection.parentId:
                collection_dict["parentId"] = collection.parentId
            if collection.customMetadata:
                collection_dict["customMetadata"] = dict(collection.customMetadata)
            if collection.tags:
                collection_dict["tags"] = list(collection.tags)

            response_data = format_collection_item(collection_dict, user_context)

            return {
                "statusCode": 201,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": response_data,
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
            logger.exception("Unexpected error creating collection", exc_info=e)
            metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
            from collections_utils import create_error_response

            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
