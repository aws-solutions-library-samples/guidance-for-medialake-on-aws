"""
Base embedding store interface for semantic search implementations.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from api_utils import get_api_key


@dataclass
class SearchResult:
    """Standardized search result format"""

    hits: List[Dict[str, Any]]
    total_results: int
    aggregations: Optional[Dict[str, Any]] = None
    suggestions: Optional[Dict[str, Any]] = None


class BaseEmbeddingStore(ABC):
    """Abstract base class for embedding store implementations"""

    def __init__(self, logger, metrics):
        self.logger = logger
        self.metrics = metrics

    @abstractmethod
    def build_semantic_query(self, params) -> Dict[str, Any]:
        """
        Build a semantic search query for the specific embedding store.

        Args:
            params: Search parameters

        Returns:
            Query object specific to the embedding store
        """

    @abstractmethod
    def execute_search(self, query: Dict[str, Any], params) -> SearchResult:
        """
        Execute the search query against the embedding store.

        Args:
            query: Query object from build_semantic_query
            params: Original search parameters

        Returns:
            SearchResult with standardized format
        """

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the embedding store is available and properly configured.

        Returns:
            True if the store is available, False otherwise
        """

    def generate_text_embedding(self, query_text: str) -> List[float]:
        """
        Generate text embedding using TwelveLabs API.

        Args:
            query_text: The text to generate embedding for

        Returns:
            List of float values representing the embedding

        Raises:
            Exception: If embedding generation fails
        """
        from twelvelabs import TwelveLabs

        start_time = time.time()
        self.logger.info(
            f"[PERF] Starting centralized embedding generation for query: {query_text}"
        )

        # Get the API key from Secrets Manager
        api_key_start = time.time()
        api_key = get_api_key()
        self.logger.info(
            f"[PERF] API key retrieval took: {time.time() - api_key_start:.3f}s"
        )

        if not api_key:
            raise Exception(
                "Search provider API key not configured or provider not enabled"
            )

        # Initialize the Twelve Labs client
        client_init_start = time.time()
        twelve_labs_client = TwelveLabs(api_key=api_key)
        self.logger.info(
            f"[PERF] TwelveLabs client initialization took: {time.time() - client_init_start:.3f}s"
        )

        try:
            # Create embedding for the search query
            embedding_start = time.time()
            self.logger.info(
                f"[PERF] Starting embedding creation for query: {query_text}"
            )
            res = twelve_labs_client.embed.create(
                model_name="Marengo-retrieval-2.7",
                text=query_text,
            )
            self.logger.info(
                f"[PERF] Embedding creation took: {time.time() - embedding_start:.3f}s"
            )

            if (
                res.text_embedding is not None
                and res.text_embedding.segments is not None
            ):
                embedding = list(res.text_embedding.segments[0].embeddings_float)
                if not all(isinstance(x, (int, float)) for x in embedding):
                    raise Exception("Invalid embedding format")

                self.logger.info(
                    f"Generated embedding for query: {query_text} (length: {len(embedding)})"
                )
                self.logger.info(
                    f"[PERF] Total embedding generation time: {time.time() - start_time:.3f}s"
                )

                return embedding
            else:
                raise Exception("Failed to generate embedding for search term")

        except Exception as e:
            self.logger.exception("Error generating embedding for search term")
            raise Exception(f"Error generating embedding: {str(e)}")

    def search(self, params) -> SearchResult:
        """
        Main search method that orchestrates the search process.

        Args:
            params: Search parameters

        Returns:
            SearchResult with standardized format
        """
        if not self.is_available():
            raise Exception(f"{self.__class__.__name__} is not available or configured")

        query = self.build_semantic_query(params)
        return self.execute_search(query, params)
