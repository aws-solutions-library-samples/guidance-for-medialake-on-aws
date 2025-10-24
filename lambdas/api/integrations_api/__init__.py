"""
Integrations API Handlers.

All route handlers using AWS Powertools and Pydantic V2.
Each file handles exactly one API endpoint (method + resource).
"""

from . import (
    integrations_get,
    integrations_ID_delete,
    integrations_ID_put,
    integrations_post,
)

__all__ = [
    "integrations_get",
    "integrations_post",
    "integrations_ID_put",
    "integrations_ID_delete",
]


def register_all_routes(app):
    """
    Register all handler routes with the API Gateway resolver.

    Args:
        app: APIGatewayRestResolver instance
    """
    # Integrations endpoints
    integrations_get.register_route(app)
    integrations_post.register_route(app)
    integrations_ID_put.register_route(app)
    integrations_ID_delete.register_route(app)
