"""
Collections API Handlers.

All route handlers using AWS Powertools and Pydantic V2.
Each file handles exactly one API endpoint (method + resource).
"""

from . import (
    collection_types_get,
    collection_types_post,
    collections_get,
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
    collections_shared_with_me_get,
)

__all__ = [
    "collections_get",
    "collections_post",
    "collections_shared_with_me_get",
    "collections_ID_get",
    "collections_ID_patch",
    "collections_ID_delete",
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
    "collection_types_get",
    "collection_types_post",
]


def register_all_routes(app, dynamodb, table_name):
    """
    Register all handler routes with the API Gateway resolver.

    Args:
        app: APIGatewayRestResolver instance
        dynamodb: DynamoDB resource
        table_name: Collections table name
    """
    # Collection types endpoints
    collection_types_get.register_route(app, dynamodb, table_name)
    collection_types_post.register_route(app, dynamodb, table_name)

    # Collections endpoints
    collections_get.register_route(app, dynamodb, table_name)
    collections_post.register_route(app, dynamodb, table_name)
    collections_shared_with_me_get.register_route(app, dynamodb, table_name)

    # Individual collection endpoints
    collections_ID_get.register_route(app, dynamodb, table_name)
    collections_ID_patch.register_route(app, dynamodb, table_name)
    collections_ID_delete.register_route(app, dynamodb, table_name)

    # Collection items endpoints
    collections_ID_items_get.register_route(app, dynamodb, table_name)
    collections_ID_items_post.register_route(app, dynamodb, table_name)
    collections_ID_items_ID_delete.register_route(app, dynamodb, table_name)

    # Collection assets endpoints
    collections_ID_assets_get.register_route(app, dynamodb, table_name)

    # Collection share endpoints
    collections_ID_share_get.register_route(app, dynamodb, table_name)
    collections_ID_share_post.register_route(app, dynamodb, table_name)
    collections_ID_share_ID_delete.register_route(app, dynamodb, table_name)

    # Collection rules endpoints
    collections_ID_rules_get.register_route(app, dynamodb, table_name)
    collections_ID_rules_post.register_route(app, dynamodb, table_name)
    collections_ID_rules_ID_put.register_route(app, dynamodb, table_name)
    collections_ID_rules_ID_delete.register_route(app, dynamodb, table_name)
