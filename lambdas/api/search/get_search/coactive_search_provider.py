"""
Coactive search provider implementation for external semantic service architecture.
"""

import json
import os
import time
from typing import Any, Dict, List

import boto3
import requests
from opensearchpy import (
    OpenSearch,
    RequestsAWSV4SignerAuth,
    RequestsHttpConnection,
)
from unified_search_models import (
    MediaType,
    ProviderLocation,
    SearchArchitectureType,
    SearchHit,
    SearchQuery,
    SearchResult,
)
from unified_search_provider import ExternalSemanticServiceProvider


class CoactiveSearchProvider(ExternalSemanticServiceProvider):
    """Coactive external semantic service provider"""

    def __init__(self, config, logger, metrics):
        super().__init__(config, logger, metrics)
        self._opensearch_client = None

    def _get_provider_location(self) -> ProviderLocation:
        return ProviderLocation.EXTERNAL

    def _get_opensearch_client(self) -> OpenSearch:
        """Create and return a cached OpenSearch client for metadata enrichment"""
        if self._opensearch_client is None:
            host = os.environ["OPENSEARCH_ENDPOINT"].replace("https://", "")
            region = os.environ["AWS_REGION"]
            service_scope = os.environ["SCOPE"]

            auth = RequestsAWSV4SignerAuth(
                boto3.Session().get_credentials(), region, service_scope
            )

            self._opensearch_client = OpenSearch(
                hosts=[{"host": host, "port": 443}],
                http_auth=auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                region=region,
                timeout=30,
                max_retries=2,
                retry_on_timeout=True,
                maxsize=20,
            )

        return self._opensearch_client

    def is_available(self) -> bool:
        """Check if Coactive provider is available and properly configured"""
        try:
            # Check required configuration
            if not self.config.dataset_id:
                self.logger.warning("Coactive dataset_id not configured")
                return False

            if not self.config.auth or not self.config.auth.get("token"):
                self.logger.warning("Coactive auth token not configured")
                return False

            # Check required environment variables for enrichment
            required_env_vars = [
                "OPENSEARCH_ENDPOINT",
                "AWS_REGION",
                "SCOPE",
                "OPENSEARCH_INDEX",
            ]
            missing_vars = [var for var in required_env_vars if not os.environ.get(var)]

            if missing_vars:
                self.logger.warning(
                    f"Missing required environment variables for enrichment: {missing_vars}"
                )
                return False

            return True
        except Exception as e:
            self.logger.warning(f"Coactive availability check failed: {str(e)}")
            return False

    def execute_external_search(self, query: SearchQuery) -> SearchResult:
        """Execute search against Coactive API"""
        start_time = time.time()

        try:
            # Build Coactive request payload
            payload = self._build_coactive_payload(query)

            # Make request to Coactive API
            response = self._make_coactive_request(payload)

            # Convert Coactive response to SearchResult
            search_result = self._convert_coactive_response(response, query)

            took_ms = int((time.time() - start_time) * 1000)
            search_result.took_ms = took_ms

            self.logger.info(
                f"Coactive search completed in {took_ms}ms, returned {len(search_result.hits)} hits"
            )

            return search_result

        except Exception as e:
            self.logger.error(f"Coactive search failed: {str(e)}")
            # Return empty result on failure
            return SearchResult(
                hits=[],
                total_results=0,
                max_score=0.0,
                took_ms=int((time.time() - start_time) * 1000),
                provider="coactive",
                architecture_type=SearchArchitectureType.EXTERNAL_SEMANTIC_SERVICE,
                provider_location=ProviderLocation.EXTERNAL,
            )

    def _build_coactive_payload(self, query: SearchQuery) -> Dict[str, Any]:
        """Build Coactive API request payload"""
        # Build metadata_filters from unified filters
        metadata_filters = []

        if query.filters:
            for filter_item in query.filters:
                key = filter_item.get("key")
                operator = filter_item.get("operator")
                value = filter_item.get("value")

                # Map MediaLake field names to Coactive metadata field names
                mapped_key = self._map_field_name(key)

                # Convert operator format
                coactive_operator = self._map_operator(operator)

                metadata_filters.append(
                    {"key": mapped_key, "operator": coactive_operator, "value": value}
                )

        payload = {
            "query": query.query_text,
            "dataset_id": self.config.dataset_id,
            "offset": query.page_offset,
            "limit": min(query.page_size, 200),  # enforce max 200
        }

        if metadata_filters:
            payload["metadata_filters"] = metadata_filters

        return payload

    def _map_field_name(self, field_name: str) -> str:
        """Map MediaLake field names to Coactive metadata field names"""
        if self.config.metadata_mapping:
            return self.config.metadata_mapping.get(field_name, field_name)

        # Default mappings
        field_mappings = {
            "mediaType": "media_type",
            "DigitalSourceAsset.Type": "media_type",
            "fileSize": "file_size",
            "createdAt": "created_at",
            "duration": "duration_ms",
        }

        return field_mappings.get(field_name, field_name)

    def _map_operator(self, operator: str) -> str:
        """Map MediaLake operators to Coactive operators"""
        operator_mappings = {
            "==": "==",
            "in": "in",
            "range": "range",
            "gte": ">=",
            "lte": "<=",
            "gt": ">",
            "lt": "<",
        }

        return operator_mappings.get(operator, operator)

    def _make_coactive_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to Coactive API"""
        endpoint = self.config.endpoint or "https://app.coactive.ai/api/v1/search"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.auth['token']}",
        }

        self.logger.info(f"Making Coactive API request to {endpoint}")
        self.logger.debug(f"Coactive request payload: {json.dumps(payload, indent=2)}")

        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)

        if response.status_code != 200:
            raise Exception(
                f"Coactive API error: {response.status_code} - {response.text}"
            )

        return response.json()

    def _convert_coactive_response(
        self, response: Dict[str, Any], query: SearchQuery
    ) -> SearchResult:
        """Convert Coactive API response to SearchResult"""
        results = response.get("results", [])
        total_count = response.get("total_count", len(results))

        hits = []
        max_score = 0.0

        for result in results:
            # Extract asset information from Coactive result
            metadata = result.get("metadata", {})
            score = float(result.get("score", 0.0))

            if score > max_score:
                max_score = score

            # Get MediaLake asset ID from metadata
            asset_id = metadata.get("medialake_uuid") or metadata.get("asset_id", "")

            # Determine media type
            media_type_str = metadata.get("media_type", "video")
            try:
                media_type = MediaType(media_type_str.lower())
            except ValueError:
                media_type = MediaType.VIDEO  # default fallback

            # Create SearchHit
            hit = SearchHit(
                asset_id=asset_id,
                score=score,
                source=metadata,  # Store Coactive metadata in source
                media_type=media_type,
                provider_metadata={
                    "coactive_id": result.get("id"),
                    "coactive_url": result.get("url"),
                    "coactive_thumbnail": result.get("thumbnail_url"),
                },
            )

            hits.append(hit)

        return SearchResult(
            hits=hits,
            total_results=total_count,
            max_score=max_score,
            took_ms=0,  # Will be set by caller
            provider="coactive",
            architecture_type=SearchArchitectureType.EXTERNAL_SEMANTIC_SERVICE,
            provider_location=ProviderLocation.EXTERNAL,
        )

    def enrich_results_with_medialake_data(
        self, results: SearchResult, query: SearchQuery
    ) -> SearchResult:
        """Enrich Coactive results with MediaLake metadata"""
        if not results.hits:
            return results

        start_time = time.time()

        try:
            # Extract asset IDs from Coactive results
            asset_ids = [hit.asset_id for hit in results.hits if hit.asset_id]

            if not asset_ids:
                self.logger.warning("No valid asset IDs found in Coactive results")
                return results

            # Query OpenSearch for MediaLake metadata
            medialake_data = self._fetch_medialake_metadata(asset_ids, query)

            # Create lookup map for MediaLake data
            medialake_lookup = {
                data["_source"].get("InventoryID", ""): data["_source"]
                for data in medialake_data
            }

            # Enrich each hit with MediaLake data
            enriched_hits = []
            for hit in results.hits:
                medialake_source = medialake_lookup.get(hit.asset_id)

                if medialake_source:
                    # Merge Coactive metadata with MediaLake data
                    enriched_source = self._merge_metadata(
                        hit.source, medialake_source, query
                    )

                    # Update the hit with enriched data
                    hit.source = enriched_source
                    enriched_hits.append(hit)
                else:
                    # Keep original hit if no MediaLake data found
                    self.logger.warning(
                        f"No MediaLake data found for asset {hit.asset_id}"
                    )
                    enriched_hits.append(hit)

            # Update results with enriched hits
            results.hits = enriched_hits

            enrichment_time = int((time.time() - start_time) * 1000)
            self.logger.info(
                f"MediaLake enrichment completed in {enrichment_time}ms for {len(enriched_hits)} hits"
            )

            return results

        except Exception as e:
            self.logger.error(
                f"Failed to enrich Coactive results with MediaLake data: {str(e)}"
            )
            # Return original results on enrichment failure
            return results

    def _fetch_medialake_metadata(
        self, asset_ids: List[str], query: SearchQuery
    ) -> List[Dict[str, Any]]:
        """Fetch MediaLake metadata from OpenSearch"""
        try:
            client = self._get_opensearch_client()
            index_name = os.environ["OPENSEARCH_INDEX"]

            # Build query for specific asset IDs
            should_clauses = [
                {"match": {"InventoryID": asset_id}} for asset_id in asset_ids
            ]

            opensearch_query = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "bool": {
                                    "should": should_clauses,
                                    "minimum_should_match": 1,
                                }
                            }
                        ],
                        "must_not": [{"term": {"embedding_scope": "clip"}}],
                    }
                },
                "size": len(asset_ids),
            }

            # Apply field selection if specified
            if query.fields:
                opensearch_query["_source"] = {"includes": query.fields}
            else:
                # Default fields for UI
                opensearch_query["_source"] = {
                    "includes": [
                        "InventoryID",
                        "DigitalSourceAsset",
                        "DerivedRepresentations",
                        "FileHash",
                        "Metadata",
                    ]
                }

            response = client.search(body=opensearch_query, index=index_name)
            hits = response.get("hits", {}).get("hits", [])

            self.logger.info(f"Fetched MediaLake metadata for {len(hits)} assets")

            return hits

        except Exception as e:
            self.logger.error(f"Failed to fetch MediaLake metadata: {str(e)}")
            return []

    def _merge_metadata(
        self,
        coactive_metadata: Dict[str, Any],
        medialake_source: Dict[str, Any],
        query: SearchQuery,
    ) -> Dict[str, Any]:
        """Merge Coactive metadata with MediaLake source data"""
        # Start with MediaLake data as base
        merged = medialake_source.copy()

        # Add Coactive-specific metadata under a separate key
        merged["coactive_metadata"] = coactive_metadata

        # Preserve any additional fields that might be useful
        if "highlights" in coactive_metadata:
            merged["highlights"] = coactive_metadata["highlights"]

        return merged
