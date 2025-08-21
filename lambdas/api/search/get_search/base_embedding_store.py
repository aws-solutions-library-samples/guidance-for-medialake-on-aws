"""
Base embedding store interface for semantic search implementations.
"""

import json
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import boto3
from api_utils import get_api_key, get_search_provider_config


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
        Generate text embedding using either TwelveLabs API or Bedrock TwelveLabs.

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

        # Get the search provider configuration to determine which method to use
        search_provider = get_search_provider_config()
        provider_type = search_provider.get("type", "").lower()

        self.logger.info(f"Search provider type: {provider_type}")

        if provider_type == "bedrock twelvelabs":
            return self._generate_bedrock_twelvelabs_embedding(query_text, start_time)
        else:
            return self._generate_twelvelabs_api_embedding(query_text, start_time)

    def _generate_twelvelabs_api_embedding(
        self, query_text: str, start_time: float
    ) -> List[float]:
        """
        Generate text embedding using TwelveLabs API.

        Args:
            query_text: The text to generate embedding for
            start_time: Start time for performance tracking

        Returns:
            List of float values representing the embedding
        """
        from twelvelabs import TwelveLabs

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

    def _generate_bedrock_twelvelabs_embedding(
        self, query_text: str, start_time: float
    ) -> List[float]:
        """
        Generate text embedding using Bedrock TwelveLabs model.

        Args:
            query_text: The text to generate embedding for
            start_time: Start time for performance tracking

        Returns:
            List of float values representing the embedding
        """
        try:
            # Initialize Bedrock runtime client
            bedrock_runtime = boto3.client(
                "bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-west-2")
            )
            s3 = boto3.client(
                "s3", region_name=os.environ.get("AWS_REGION", "us-west-2")
            )

            # Get S3 bucket for embedding output
            s3_bucket_name = os.environ.get("S3_VECTOR_BUCKET_NAME")
            if not s3_bucket_name:
                raise Exception(
                    "S3_VECTOR_BUCKET_NAME environment variable not set for Bedrock embeddings"
                )

            start_datetime = time.time()
            self.logger.info(f"Starting Bedrock async invoke at: {start_datetime}")

            # Start async invoke for text embedding
            response = bedrock_runtime.start_async_invoke(
                modelId="twelvelabs.marengo-embed-2-7-v1:0",
                modelInput={"inputType": "text", "inputText": query_text},
                outputDataConfig={
                    "s3OutputDataConfig": {
                        "s3Uri": f"s3://{s3_bucket_name}/textEmbedding"
                    }
                },
            )

            text_invocation_arn = response["invocationArn"]
            self.logger.info(
                f"Started text embedding async invoke with ARN: {text_invocation_arn}"
            )

            # Extract UID from ARN
            text_uid_match = re.search(r"/([^/]+)$", text_invocation_arn)
            if text_uid_match:
                text_uid = text_uid_match.group(1)
                embedding_text_response_location = f"textEmbedding/{text_uid}"
            else:
                raise Exception("Could not extract UID from invocation ARN")

            # Wait for embedding result
            max_wait_time, wait_interval, waited_time = 150, 1, 0
            text_embedding_vector = None

            self.logger.info("Waiting for text embedding to complete...")

            while waited_time < max_wait_time:
                try:
                    response = s3.list_objects_v2(
                        Bucket=s3_bucket_name, Prefix=embedding_text_response_location
                    )

                    if "Contents" in response:
                        response_files = [
                            obj
                            for obj in response["Contents"]
                            if obj["Key"].endswith("output.json")
                        ]
                        if response_files:
                            response_key = response_files[0]["Key"]
                            response_obj = s3.get_object(
                                Bucket=s3_bucket_name, Key=response_key
                            )
                            response_content = (
                                response_obj["Body"].read().decode("utf-8")
                            )
                            response_data = json.loads(response_content)

                            if "data" in response_data:
                                text_embedding_vector = response_data["data"][0][
                                    "embedding"
                                ]
                                self.logger.info(
                                    f"Extracted embedding vector (length: {len(text_embedding_vector)})"
                                )
                                self.logger.info(
                                    f"First 10 values: {text_embedding_vector[:10]}"
                                )
                                break
                except Exception as e:
                    self.logger.warning(f"Error checking for response: {e}")

                time.sleep(wait_interval)
                waited_time += wait_interval

            if not text_embedding_vector:
                raise Exception("Timeout or no embedding vector found")

            # Validate embedding format
            if not all(isinstance(x, (int, float)) for x in text_embedding_vector):
                raise Exception("Invalid embedding format from Bedrock")

            self.logger.info(
                f"Generated Bedrock embedding for query: {query_text} (length: {len(text_embedding_vector)})"
            )
            self.logger.info(
                f"[PERF] Total Bedrock embedding generation time: {time.time() - start_time:.3f}s"
            )

            return text_embedding_vector

        except Exception as e:
            self.logger.exception("Error generating Bedrock embedding for search term")
            raise Exception(f"Error generating Bedrock embedding: {str(e)}")

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
