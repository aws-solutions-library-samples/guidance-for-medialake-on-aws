"""POST /collections/groups - Create a new collection group."""

import json
import os
import uuid
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import ValidationError, parse
from collection_groups_utils import (
    create_collection_group,
    format_collection_group_item,
)
from models.group_models import CreateCollectionGroupRequest
from user_auth import extract_user_context

# Initialize DynamoDB resource
dynamodb = boto3.resource("dynamodb")
table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
groups_table = dynamodb.Table(table_name)

logger = Logger(service="groups-post", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="groups-post")
metrics = Metrics(namespace="medialake", service="collection-groups")


def register_route(app):
    """Register POST /collections/groups route"""

    @app.post("/collections/groups")
    @tracer.capture_method
    def groups_post():
        """Create a new collection group with Pydantic V2 validation"""
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                raise BadRequestError(
                    "Valid authentication is required to create collection groups"
                )

            # Parse and validate request body using Pydantic
            try:
                request_data = parse(
                    event=app.current_event.json_body,
                    model=CreateCollectionGroupRequest,
                )
            except ValidationError as e:
                logger.warning(f"Request validation error: {e}")
                metrics.add_metric(
                    name="ValidationErrors", unit=MetricUnit.Count, value=1
                )
                raise BadRequestError(f"Validation error: {str(e)}")

            # Generate ID
            group_id = f"grp_{str(uuid.uuid4())[:8]}"

            # Prepare group data
            group_data = {
                "id": group_id,
                "name": request_data.name,
                "ownerId": user_id,
                "isPublic": request_data.isPublic,
            }

            if request_data.description:
                group_data["description"] = request_data.description

            # Create group
            group_item = create_collection_group(groups_table, group_data)

            logger.info(
                f"Collection group created: {group_id}",
                extra={"group_id": group_id, "owner_id": user_id},
            )
            metrics.add_metric(
                name="SuccessfulGroupCreations", unit=MetricUnit.Count, value=1
            )

            # Format response
            response_data = format_collection_group_item(group_item, user_context)

            return {
                "statusCode": 201,
                "body": json.dumps(
                    {
                        "success": True,
                        "data": response_data,
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "version": "v1",
                            "request_id": app.current_event.request_context.request_id,
                        },
                    }
                ),
            }

        except BadRequestError:
            raise
        except Exception as e:
            logger.exception("Unexpected error creating group", exc_info=e)
            metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
            from collections_utils import create_error_response

            return create_error_response(
                error_code="InternalServerError",
                error_message="An unexpected error occurred",
                status_code=500,
                request_id=app.current_event.request_context.request_id,
            )
