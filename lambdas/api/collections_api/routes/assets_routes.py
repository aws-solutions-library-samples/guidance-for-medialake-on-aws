"""
Collection Assets Routes.

Handles operations related to assets in collections.
Currently a placeholder for future asset-specific endpoints.
"""

import os

from aws_lambda_powertools import Logger

logger = Logger(service="assets-routes", level=os.environ.get("LOG_LEVEL", "INFO"))


def register_routes(app, dynamodb, table_name):
    """
    Register collection assets routes.

    Currently a placeholder - asset operations are handled via
    /collections/{collectionId}/assets endpoint in assets_routes module.
    """
    logger.info("Collection assets routes registered (placeholder)")
