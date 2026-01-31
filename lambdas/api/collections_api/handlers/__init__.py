"""
Collections API Handlers.

All route handlers using AWS Powertools and Pydantic V2.
Each file handles exactly one API endpoint (method + resource).
"""

from . import (
    collections_get,
    collections_ID_ancestors_get,
    collections_ID_assets_get,
    collections_ID_delete,
    collections_ID_get,
    collections_ID_items_get,
    collections_ID_items_ID_delete,
    collections_ID_items_post,
    collections_ID_patch,
    collections_ID_rules_get,
    collections_ID_rules_ID_delete,
    collections_ID_rules_ID_put,
    collections_ID_rules_post,
    collections_ID_share_get,
    collections_ID_share_ID_delete,
    collections_ID_share_post,
    collections_post,
    collections_shared_by_me_get,
    collections_shared_with_me_get,
    groups_get,
    groups_ID_collections_delete,
    groups_ID_collections_post,
    groups_ID_delete,
    groups_ID_get,
    groups_ID_put,
    groups_post,
)

__all__ = [
    "collections_get",
    "collections_post",
    "collections_shared_by_me_get",
    "collections_shared_with_me_get",
    "collections_ID_get",
    "collections_ID_patch",
    "collections_ID_delete",
    "collections_ID_ancestors_get",
    "collections_ID_items_get",
    "collections_ID_items_post",
    "collections_ID_items_ID_delete",
    "collections_ID_assets_get",
    "collections_ID_share_get",
    "collections_ID_share_post",
    "collections_ID_share_ID_delete",
    "collections_ID_rules_get",
    "collections_ID_rules_post",
    "collections_ID_rules_ID_put",
    "collections_ID_rules_ID_delete",
    "groups_get",
    "groups_post",
    "groups_ID_get",
    "groups_ID_put",
    "groups_ID_delete",
    "groups_ID_collections_post",
    "groups_ID_collections_delete",
]


def register_all_routes(app):
    """
    Register all handler routes with the API Gateway resolver.

    Args:
        app: APIGatewayRestResolver instance
    """
    # Collections endpoints
    collections_get.register_route(app)
    collections_post.register_route(app)
    collections_shared_by_me_get.register_route(app)
    collections_shared_with_me_get.register_route(app)

    # Individual collection endpoints
    collections_ID_get.register_route(app)
    collections_ID_patch.register_route(app)
    collections_ID_delete.register_route(app)
    collections_ID_ancestors_get.register_route(app)

    # Collection items endpoints
    collections_ID_items_get.register_route(app)
    collections_ID_items_post.register_route(app)
    collections_ID_items_ID_delete.register_route(app)

    # Collection assets endpoints
    collections_ID_assets_get.register_route(app)

    # Collection share endpoints
    collections_ID_share_get.register_route(app)
    collections_ID_share_post.register_route(app)
    collections_ID_share_ID_delete.register_route(app)

    # Collection rules endpoints
    collections_ID_rules_get.register_route(app)
    collections_ID_rules_post.register_route(app)
    collections_ID_rules_ID_put.register_route(app)
    collections_ID_rules_ID_delete.register_route(app)

    # Collection groups endpoints
    groups_get.register_route(app)
    groups_post.register_route(app)
    groups_ID_get.register_route(app)
    groups_ID_put.register_route(app)
    groups_ID_delete.register_route(app)
    groups_ID_collections_post.register_route(app)
    groups_ID_collections_delete.register_route(app)
