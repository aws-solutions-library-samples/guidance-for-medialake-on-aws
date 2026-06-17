"""GET /collections/metadata-keys - Return distinct metadata key names."""

import os

from aws_lambda_powertools import Logger, Tracer
from collections_utils import create_error_response, create_success_response
from user_auth import extract_user_context
from utils.collections_search import get_metadata_keys

logger = Logger(
    service="collections-metadata-keys-get",
    level=os.environ.get("LOG_LEVEL", "INFO"),
)
tracer = Tracer(service="collections-metadata-keys-get")


def register_route(app):
    """Register GET /collections/metadata-keys route"""

    @app.get("/collections/metadata-keys")
    @tracer.capture_method
    def collections_metadata_keys_get():
        """Returns sorted list of all metadata key names from the index mapping."""
        request_id = app.current_event.request_context.request_id

        try:
            user_context = extract_user_context(app.current_event.raw_event)
            user_id = user_context.get("user_id")

            if not user_id:
                return create_error_response(
                    error_code="Unauthorized",
                    error_message="Authentication required to fetch metadata keys",
                    status_code=401,
                    request_id=request_id,
                )

            keys = get_metadata_keys(user_id)

            return create_success_response(
                data={"keys": keys},
                request_id=request_id,
            )

        except Exception as e:
            logger.exception("Error fetching metadata keys", exc_info=e)
            return create_error_response(
                error_code="InternalServerError",
                error_message="Failed to fetch metadata keys",
                status_code=500,
                request_id=request_id,
            )
