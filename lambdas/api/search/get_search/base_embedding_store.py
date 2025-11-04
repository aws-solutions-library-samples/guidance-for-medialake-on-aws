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

    def _get_regional_inference_profile(self) -> str:
        """
        Get the appropriate TwelveLabs Marengo Embed v2.7 inference profile based on AWS region.

        Returns:
            Regional inference profile ID for TwelveLabs Marengo Embed v2.7
        """
        # Allow override via environment variable
        if "BEDROCK_INFERENCE_PROFILE_ARN" in os.environ:
            return os.environ["BEDROCK_INFERENCE_PROFILE_ARN"]

        # Get current AWS region
        aws_region = os.environ.get("AWS_REGION", "us-east-1")

        # Common suffix for all TwelveLabs Marengo Embed v2.7 inference profiles
        model_suffix = ".twelvelabs.marengo-embed-2-7-v1:0"

        # Map regions to regional prefixes based on AWS documentation
        if aws_region.startswith("us-"):
            # US regions: us-east-1, us-east-2, us-west-1, us-west-2
            regional_prefix = "us"
        elif aws_region.startswith("eu-"):
            # EU regions: eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3
            regional_prefix = "eu"
        elif aws_region.startswith("ap-"):
            # APAC regions: ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4
            regional_prefix = "apac"
        else:
            # Default to US profile for unknown regions
            self.logger.warning(
                f"Unknown AWS region: {aws_region}, defaulting to US inference profile"
            )
            regional_prefix = "us"

        inference_profile_id = f"{regional_prefix}{model_suffix}"
        self.logger.info(
            f"Selected inference profile {inference_profile_id} for region {aws_region}"
        )
        return inference_profile_id

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

            # Determine the correct inference profile based on AWS region
            inference_profile_id = self._get_regional_inference_profile()

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
