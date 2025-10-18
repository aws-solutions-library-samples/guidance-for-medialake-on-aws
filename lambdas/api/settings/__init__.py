"""
Settings API handlers registration module.

This module imports and registers all handler routes with the API Gateway resolver.
All handlers follow the pattern of defining a `register_route(app)` function that
registers their routes with the provided APIGatewayRestResolver instance.
"""

from . import (  # Collection types handlers; System settings handlers; API keys handlers; Users handlers
    api_keys_get,
    api_keys_ID_delete,
    api_keys_ID_get,
    api_keys_ID_put,
    api_keys_post,
    collection_types_get,
    collection_types_ID_delete,
    collection_types_ID_migrate_post,
    collection_types_ID_put,
    collection_types_post,
    settings_users_get,
    system_get,
    system_search_delete,
    system_search_get,
    system_search_post,
    system_search_put,
)

__all__ = [
    "collection_types_get",
    "collection_types_post",
    "collection_types_ID_put",
    "collection_types_ID_delete",
    "collection_types_ID_migrate_post",
    "system_get",
    "system_search_get",
    "system_search_post",
    "system_search_put",
    "system_search_delete",
    "api_keys_get",
    "api_keys_post",
    "api_keys_ID_get",
    "api_keys_ID_put",
    "api_keys_ID_delete",
    "settings_users_get",
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

    # System settings endpoints (/settings/system)
    system_get.register_route(app)
    system_search_get.register_route(app)
    system_search_post.register_route(app)
    system_search_put.register_route(app)
    system_search_delete.register_route(app)

    # API keys endpoints (/settings/api-keys)
    api_keys_get.register_route(app)
    api_keys_post.register_route(app)
    api_keys_ID_get.register_route(app)
    api_keys_ID_put.register_route(app)
    api_keys_ID_delete.register_route(app)

    # Users endpoints (/settings/users)
    settings_users_get.register_route(app)
