"""
Settings API Handlers.

All route handlers for settings-related endpoints using AWS Powertools.
Each file handles exactly one API endpoint (method + resource).
"""

from . import (
    collection_types_get,
    collection_types_ID_delete,
    collection_types_ID_migrate_post,
    collection_types_ID_put,
    collection_types_post,
)

__all__ = [
    "collection_types_get",
    "collection_types_post",
    "collection_types_ID_put",
    "collection_types_ID_delete",
    "collection_types_ID_migrate_post",
]


def register_all_routes(app):
    """
    Register all handler routes with the API Gateway resolver.

    Args:
        app: APIGatewayRestResolver instance
    """
    # Collection types endpoints (/settings/collection-types)
    collection_types_get.register_route(app)
    collection_types_post.register_route(app)
    collection_types_ID_put.register_route(app)
    collection_types_ID_delete.register_route(app)
    collection_types_ID_migrate_post.register_route(app)
