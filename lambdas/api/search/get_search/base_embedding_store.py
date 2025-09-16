"""
Base embedding store interface for semantic search implementations.
"""

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import boto3
from api_utils import get_api_key, get_search_provider_config
from twelvelabs import TwelveLabs


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
        Generate text embedding using TwelveLabs API or Bedrock based on configuration.

        Args:
            query_text: The text to generate embedding for

        Returns:
            List of float values representing the embedding

        Raises:
            Exception: If embedding generation fails
        """
        start_time = time.time()
        self.logger.info(
            f"[PERF] Starting centralized embedding generation for query: {query_text}"
        )

        # Get search provider configuration to determine which method to use
        config_start = time.time()
        search_provider_config = get_search_provider_config()
        provider_type = search_provider_config.get("type", "twelvelabs")
        self.logger.info(
            f"[PERF] Provider config retrieval took: {time.time() - config_start:.3f}s"
        )
        self.logger.info(f"Using search provider type: {provider_type}")

        if provider_type == "twelvelabs-bedrock":
            return self._generate_embedding_via_bedrock(query_text, start_time)
        else:
            return self._generate_embedding_via_twelvelabs_api(query_text, start_time)

    def _generate_embedding_via_bedrock(
        self, query_text: str, start_time: float
    ) -> List[float]:
        """
        Generate text embedding using TwelveLabs model via AWS Bedrock InvokeModel with inference profile.

        Args:
            query_text: The text to generate embedding for
            start_time: Start time for performance logging

        Returns:
            List of float values representing the embedding
        """

        try:
            # Initialize Bedrock client
            bedrock_init_start = time.time()
            bedrock_client = boto3.client("bedrock-runtime")
            self.logger.info(
                f"[PERF] Bedrock client initialization took: {time.time() - bedrock_init_start:.3f}s"
            )

            # Use AWS system-defined cross-Region inference profile for TwelveLabs Marengo Embed v2.7
            # This is a pre-built inference profile provided by AWS
            inference_profile_id = os.environ.get(
                "BEDROCK_INFERENCE_PROFILE_ARN", "us.twelvelabs.marengo-embed-2-7-v1:0"
            )

            self.logger.info(f"Using Bedrock inference profile: {inference_profile_id}")

            # Prepare model input for TwelveLabs Marengo on Bedrock
            # Based on AWS docs: for text input with InvokeModel, use {"inputType": "text"}
            payload = {"inputType": "text", "inputText": query_text}

            # Invoke model using inference profile ARN
            embedding_start = time.time()
            self.logger.info(
                f"[PERF] Starting Bedrock embedding creation for query: {query_text} using profile: {inference_profile_id}"
            )

            response = bedrock_client.invoke_model(
                modelId=inference_profile_id,  # Use inference profile ID directly as modelId
                contentType="application/json",
                accept="application/json",
                body=json.dumps(payload),
            )

            self.logger.info(
                f"[PERF] Bedrock embedding creation took: {time.time() - embedding_start:.3f}s"
            )

            # Parse response
            response_body = json.loads(response["body"].read())

            # Extract embedding from TwelveLabs Bedrock response
            # Support multiple response formats for compatibility
            embedding = None

            # Format 1: TwelveLabs Bedrock format - {"data": [{"embedding": [float, ...]}]}
            if "data" in response_body and response_body["data"]:
                if (
                    isinstance(response_body["data"], list)
                    and len(response_body["data"]) > 0
                ):
                    if "embedding" in response_body["data"][0]:
                        embedding = response_body["data"][0]["embedding"]
                        self.logger.info(
                            "[DEBUG] Using TwelveLabs Bedrock format: data[0].embedding"
                        )

            # Format 2: Direct embedding field (standard Bedrock format)
            elif "embedding" in response_body:
                embedding = response_body["embedding"]
                self.logger.info("[DEBUG] Using direct embedding format")

            # Format 3: TwelveLabs API-like format (for compatibility)
            elif "text_embedding" in response_body:
                text_emb = response_body["text_embedding"]
                if "segments" in text_emb and len(text_emb["segments"]) > 0:
                    seg = text_emb["segments"][0]
                    # Try different field names used by TwelveLabs API
                    embedding = (
                        seg.get("float_")
                        or seg.get("embeddings_float")
                        or seg.get("values")
                        or seg.get("vector")
                    )
                    if embedding:
                        self.logger.info(
                            "[DEBUG] Using TwelveLabs API-like format: text_embedding.segments[0]"
                        )

            if embedding is None:
                self.logger.error(
                    f"No embedding found in Bedrock response: {response_body}"
                )
                raise Exception("No embedding found in Bedrock response")

            # Ensure embedding is a list of floats
            if not isinstance(embedding, list):
                embedding = list(embedding)

            if not all(isinstance(x, (int, float)) for x in embedding):
                raise Exception("Invalid embedding format from Bedrock")

            self.logger.info(
                f"Generated Bedrock embedding for query: {query_text} (length: {len(embedding)})"
            )
            self.logger.info(
                f"[PERF] Total Bedrock embedding generation time: {time.time() - start_time:.3f}s"
            )

            return embedding

        except Exception as e:
            self.logger.exception("Error generating embedding via Bedrock")
            raise Exception(f"Error generating Bedrock embedding: {str(e)}")

    def _generate_embedding_via_twelvelabs_api(
        self, query_text: str, start_time: float
    ) -> List[float]:
        """
        Generate text embedding using TwelveLabs API directly.

        Args:
            query_text: The text to generate embedding for
            start_time: Start time for performance logging

        Returns:
            List of float values representing the embedding
        """

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
                f"[PERF] Starting TwelveLabs API embedding creation for query: {query_text}"
            )
            res = twelve_labs_client.embed.create(
                model_name="Marengo-retrieval-2.7",
                text=query_text,
            )
            self.logger.info(
                f"[PERF] TwelveLabs API embedding creation took: {time.time() - embedding_start:.3f}s"
            )

            if (
                res.text_embedding is not None
                and res.text_embedding.segments is not None
            ):
                seg = res.text_embedding.segments[0]

                vec = (
                    getattr(seg, "float_", None)  # current SDK field (v1.3)
                    or getattr(
                        seg, "embeddings_float", None
                    )  # legacy field used in older examples
                    # optional extra fallbacks if you want to be defensive:
                    or getattr(seg, "values", None)
                    or getattr(seg, "vector", None)
                )

                if not vec:
                    # one-time debug can help confirm the actual keys:
                    # logger.info(f"Segment keys: {list(getattr(seg, 'model_dump', lambda: {})().keys())}")
                    raise Exception(
                        "Embedding vector missing on Twelve Labs response segment"
                    )

                embedding = list(vec)
                if not all(isinstance(x, (int, float)) for x in embedding):
                    raise Exception("Invalid embedding format")

                self.logger.info(
                    f"Generated TwelveLabs API embedding for query: {query_text} (length: {len(embedding)})"
                )
                self.logger.info(
                    f"[PERF] Total TwelveLabs API embedding generation time: {time.time() - start_time:.3f}s"
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
