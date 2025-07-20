"""
Factory for creating embedding store instances based on system configuration.
"""

import os
from typing import Optional

import boto3
from base_embedding_store import BaseEmbeddingStore
from opensearch_embedding_store import OpenSearchEmbeddingStore
from s3_vector_embedding_store import S3VectorEmbeddingStore


class EmbeddingStoreFactory:
    """Factory class for creating embedding store instances"""

    def __init__(self, logger, metrics):
        self.logger = logger
        self.metrics = metrics
        self._cached_setting = None
        self._cached_store = None

    def get_embedding_store_setting(self) -> str:
        """Get the current embedding store setting from system settings"""
        try:
            dynamodb = boto3.resource("dynamodb")
            system_settings_table = dynamodb.Table(
                os.environ.get("SYSTEM_SETTINGS_TABLE")
            )

            response = system_settings_table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "EMBEDDING_STORE"}
            )

            embedding_store = response.get("Item", {})
            if embedding_store:
                return embedding_store.get("type", "opensearch")
            else:
                return "opensearch"  # Default to opensearch
        except Exception as e:
            self.logger.warning(f"Error getting embedding store setting: {str(e)}")
            return "opensearch"  # Default fallback

    def create_embedding_store(
        self, store_type: Optional[str] = None
    ) -> BaseEmbeddingStore:
        """
        Create an embedding store instance based on the specified type or system setting.

        Args:
            store_type: Optional store type override. If None, uses system setting.

        Returns:
            BaseEmbeddingStore instance

        Raises:
            ValueError: If store type is not supported
            Exception: If store is not available or configured
        """
        if store_type is None:
            store_type = self.get_embedding_store_setting()

        # Return cached store if it matches the requested type
        if (
            self._cached_store is not None
            and self._cached_setting == store_type
            and self._cached_store.is_available()
        ):
            return self._cached_store

        # Create new store instance
        if store_type == "opensearch":
            store = OpenSearchEmbeddingStore(self.logger, self.metrics)
        elif store_type == "s3-vector":
            store = S3VectorEmbeddingStore(self.logger, self.metrics)
        else:
            raise ValueError(f"Unsupported embedding store type: {store_type}")

        # Verify the store is available with detailed logging
        if not store.is_available():
            self.logger.error(
                f"Embedding store '{store_type}' is not available or properly configured"
            )
            # Log available stores for debugging
            available_stores = self.get_available_stores()
            self.logger.info(f"Available embedding stores: {available_stores}")
            raise Exception(
                f"Embedding store '{store_type}' is not available or properly configured"
            )

        # Cache the store
        self._cached_setting = store_type
        self._cached_store = store

        self.logger.info("Initialized embedding store client: %s", store_type)
        return store

    def get_available_stores(self) -> dict:
        """
        Get a dictionary of available embedding stores and their availability status.

        Returns:
            Dict with store names as keys and availability status as values
        """
        stores = {}

        # Check OpenSearch
        try:
            opensearch_store = OpenSearchEmbeddingStore(self.logger, self.metrics)
            stores["opensearch"] = opensearch_store.is_available()
        except Exception as e:
            self.logger.warning(f"Error checking OpenSearch availability: {str(e)}")
            stores["opensearch"] = False

        # Check S3 Vector
        try:
            s3_vector_store = S3VectorEmbeddingStore(self.logger, self.metrics)
            stores["s3-vector"] = s3_vector_store.is_available()
        except Exception as e:
            self.logger.warning(f"Error checking S3 Vector availability: {str(e)}")
            stores["s3-vector"] = False

        return stores

    def clear_cache(self):
        """Clear the cached store instance"""
        self._cached_setting = None
        self._cached_store = None
