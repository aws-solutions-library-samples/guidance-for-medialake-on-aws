"""POST /settings/portals/validate — Validate a portal config without writing.

Runs the same shared validation (``common_libraries/portal_validation.py``) the
create/update handlers and the ``manage_portal`` pipeline node use, and returns
structured results. Backs the canvas node "Validate" button and the admin UI so
authors get the same errors everywhere, before anything is persisted.
"""

import os

from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import validate_portal_config
from response_utils import create_error_response, create_success_response

logger = Logger(service="portals-validate", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="portals-validate")


def register_route(app):
    @app.post("/settings/portals/validate")
    @tracer.capture_method
    def portals_validate_post():
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            body = app.current_event.json_body or {}

            # `partial` lets callers validate an in-progress / mapping-driven
            # config: when true, name/slug aren't required but any present value
            # is still format-checked. Defaults to a full-create validation.
            partial = bool(body.get("partial", False))
            config = body.get("config", body)

            errors = validate_portal_config(config, partial=partial)

            return create_success_response(
                data={"valid": not errors, "errors": errors},
                request_id=request_id,
            )

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error validating portal config", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )
