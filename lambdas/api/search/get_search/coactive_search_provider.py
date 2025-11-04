"""
Coactive search provider implementation for external semantic service architecture.
"""

import http.client
import json
import os
import time
from typing import Any, Dict, List, Optional

import boto3
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
            # Note: dataset_id is optional for search operations - can search across all datasets
            if not self.config.dataset_id:
                self.logger.info(
                    "Coactive dataset_id not configured - will search across all available datasets"
                )

            # Check if we can retrieve the auth token from Secrets Manager
            auth_token = self._get_auth_token()
            if not auth_token:
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

    def _get_auth_token(self) -> Optional[str]:
        """Get JWT access token by exchanging personal token with Coactive API"""
        try:
            self.logger.info(f"Auth config: {self.config.auth}")

            if not self.config.auth or not self.config.auth.get("secret_arn"):
                self.logger.warning(
                    f"No secret_arn found in auth config. Auth: {self.config.auth}"
                )
                # Try to get token directly from config (for backward compatibility)
                if self.config.auth and self.config.auth.get("token"):
                    self.logger.info("Found token directly in config")
                    return self.config.auth.get("token")
                return None

            secret_arn = self.config.auth.get("secret_arn")
            self.logger.info(f"Retrieving personal token from secret ARN: {secret_arn}")

            secretsmanager = boto3.client("secretsmanager")
            response = secretsmanager.get_secret_value(SecretId=secret_arn)

            if response and "SecretString" in response:
                import json

                secret_data = json.loads(response["SecretString"])
                self.logger.info(f"Secret data keys: {list(secret_data.keys())}")
                # Get the personal token using the x-api-key format
                personal_token = secret_data.get("x-api-key")
                if not personal_token:
                    self.logger.warning(
                        f"No valid personal token key found in secret. Available keys: {list(secret_data.keys())}"
                    )
                    return None

                self.logger.info(
                    "Successfully retrieved personal token, exchanging for JWT access token"
                )

                # Exchange personal token for JWT access token using the working pattern
                import http.client
                import json as json_lib

                try:
                    conn = http.client.HTTPSConnection("api.coactive.ai")
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {personal_token}",
                    }
                    payload = {"grant_type": "refresh_token"}
                    body = json_lib.dumps(payload)

                    self.logger.info("Making authentication request to /api/v0/login")
                    conn.request("POST", "/api/v0/login", body=body, headers=headers)
                    auth_response = conn.getresponse()
                    response_data = auth_response.read().decode("utf-8")
                    conn.close()

                    if auth_response.status != 200:
                        self.logger.error(
                            f"Authentication failed: {auth_response.status} - {response_data}"
                        )
                        return None

                    auth_data = json_lib.loads(response_data)
                    access_token = auth_data.get("access_token")

                    if not access_token:
                        self.logger.error(f"No access_token in response: {auth_data}")
                        return None

                    self.logger.info(
                        "Successfully obtained JWT access token from Coactive API"
                    )
                    return access_token

                except Exception as auth_e:
                    self.logger.error(
                        f"Failed to exchange personal token for JWT: {str(auth_e)}"
                    )
                    return None

        except Exception as e:
            self.logger.error(f"Failed to get Coactive auth token: {str(e)}")

        return None

    def execute_external_search(self, query: SearchQuery) -> SearchResult:
        """Execute search against Coactive API"""
        start_time = time.time()

        try:
            # Build Coactive request payload for POST request
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
        """Build Coactive API request payload for new POST endpoint"""
        payload = {
            "dataset_id": self.config.dataset_id,
            "text_query": query.query_text,
            "offset": query.page_offset,
            "limit": query.page_size,
        }

        # Only add asset_type filter if explicitly provided in query filters
        # Don't automatically filter by asset_type based on include_clips
        # as this would exclude images when in clip mode
        if query.filters:
            for filter_item in query.filters:
                if (
                    filter_item.field == "asset_type"
                    or filter_item.field == "DigitalSourceAsset.Type"
                ):
                    payload["asset_type"] = filter_item.value
                    break

        self.logger.info(f"Built Coactive payload: {payload}")
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
        """Make HTTP request to Coactive API using new POST endpoint"""
        # Use the new Coactive search endpoint
        endpoint = "https://api.coactive.ai/api/v1/search/text-to-image"

        # Get auth token from Secrets Manager
        auth_token = self._get_auth_token()
        if not auth_token:
            raise Exception("Coactive auth token not available")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}",
        }

        self.logger.info(f"Making Coactive API request to {endpoint}")
        self.logger.debug(f"Coactive request payload: {json.dumps(payload, indent=2)}")

        # Use POST request with JSON payload
        from urllib.parse import urlparse

        parsed_url = urlparse(endpoint)
        host = parsed_url.netloc
        path = parsed_url.path

        self.logger.info(f"Making POST request to {host}{path}")

        # Make HTTP request using http.client
        conn = http.client.HTTPSConnection(host)
        body = json.dumps(payload)
        conn.request("POST", path, body=body, headers=headers)
        response = conn.getresponse()
        response_data = response.read().decode("utf-8")
        conn.close()

        if response.status != 200:
            self.logger.error(f"Coactive API error response: {response_data}")
            raise Exception(f"Coactive API error: {response.status} - {response_data}")

        # Log the raw response from Coactive
        self.logger.info(f"Raw Coactive API response: {response_data}")

        try:
            parsed_response = json.loads(response_data)
            self.logger.info(
                f"Parsed Coactive response structure: {json.dumps(parsed_response, indent=2)}"
            )
            return parsed_response
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Coactive response as JSON: {e}")
            self.logger.error(f"Raw response that failed to parse: {response_data}")
            raise Exception(f"Invalid JSON response from Coactive API: {e}")

    def _convert_coactive_response(
        self, response: Dict[str, Any], query: SearchQuery
    ) -> SearchResult:
        """
        Convert Coactive API response to SearchResult with proper MediaLake format.

        Coactive returns results in relevance order but doesn't provide explicit ranking scores.
        This method converts the positional order to a 0.0-1.0 ranking score where:
        - First result gets 1.0 (highest relevance)
        - Subsequent results get progressively lower scores using exponential decay
        - Minimum score is 0.1 to maintain meaningful differences
        """
        # Based on working example, results are in 'data' field
        results = response.get("data", [])
        total_count = response.get("total_count", len(results))

        self.logger.info(
            f"Processing {len(results)} Coactive search results with order-based ranking conversion"
        )

        # Group results by MediaLake asset UUID to create proper clips structure
        assets_with_clips = {}
        max_score = 1.0  # Since we're normalizing, max score will be 1.0
        for i, result in enumerate(results):
            self.logger.info(f"[CLIP_DEBUG] Processing result {i+1}/{len(results)}")

            # Extract MediaLake UUID from different locations based on media type
            medialake_uuid = None
            coactive_metadata = {}

            # For images: UUID is directly in metadata
            if result.get("metadata", {}).get("medialake_uuid"):
                medialake_uuid = result["metadata"]["medialake_uuid"]
                coactive_metadata = result.get("metadata", {})

            # For videos: UUID is in video.metadata, with timing info in shot
            elif result.get("video", {}).get("metadata", {}).get("medialake_uuid"):
                medialake_uuid = result["video"]["metadata"]["medialake_uuid"]
                coactive_metadata = result["video"].get("metadata", {})

                # Add timing information for video clips
                if result.get("shot"):
                    coactive_metadata.update(
                        {
                            "start_time_ms": result["shot"].get("start_time_ms", 0),
                            "end_time_ms": result["shot"].get("end_time_ms", 0),
                            "timestamp_ms": result.get("timestamp", 0),
                            "shot_id": result["shot"].get("shot_id"),
                        }
                    )

                # Add Coactive video ID
                if result.get("video", {}).get("coactiveVideoId"):
                    coactive_metadata["coactive_video_id"] = result["video"][
                        "coactiveVideoId"
                    ]

            if not medialake_uuid:
                self.logger.warning(
                    f"No MediaLake UUID found in Coactive result: {result}"
                )
                continue

            # Convert order-based ranking to 0.0-1.0 score
            # First result gets 1.0, subsequent results get progressively lower scores
            if len(results) > 1:
                # Use exponential decay to create meaningful score differences
                # This ensures first result gets 1.0, and scores decrease meaningfully
                ranking_score = max(0.1, 1.0 - (i * 0.8 / (len(results) - 1)))
            else:
                ranking_score = 1.0

            # Keep original score for reference but use ranking score for sorting
            original_score = float(
                result.get("relevance_score") or result.get("score", ranking_score)
            )
            score = ranking_score

            if score > max_score:
                max_score = score

            # Group clips by asset UUID
            if medialake_uuid not in assets_with_clips:
                assets_with_clips[medialake_uuid] = {
                    "asset_id": medialake_uuid,
                    "clips": [],
                    "max_score": score,
                }
            else:
                # Update max score for this asset
                if score > assets_with_clips[medialake_uuid]["max_score"]:
                    assets_with_clips[medialake_uuid]["max_score"] = score

            # Create clip data with both ranking score and original score
            clip_data = {
                "score": score,  # Use ranking score for sorting
                "original_score": original_score,  # Keep original for reference
                "ranking_position": i + 1,  # 1-based position for debugging
                "coactive_metadata": coactive_metadata,
                "coactive_result": result,  # Store full result for debugging
            }

            assets_with_clips[medialake_uuid]["clips"].append(clip_data)

        self.logger.info(f"Grouped results into {len(assets_with_clips)} unique assets")

        # Log ranking conversion for debugging
        if results:
            self.logger.info("Coactive ranking conversion applied:")
            for index, result in enumerate(results[:5]):  # Log first 5 for debugging
                ranking_score = (
                    max(0.1, 1.0 - (index * 0.8 / (len(results) - 1)))
                    if len(results) > 1
                    else 1.0
                )
                original_score = result.get("relevance_score") or result.get(
                    "score", "N/A"
                )
                self.logger.info(
                    f"  Position {index + 1}: original_score={original_score} -> ranking_score={ranking_score:.3f}"
                )

        # Convert to SearchHit format
        hits = []
        for asset_uuid, asset_data in assets_with_clips.items():
            # Determine media type from first clip
            first_clip = asset_data["clips"][0] if asset_data["clips"] else {}
            media_type_str = first_clip.get("coactive_metadata", {}).get(
                "media_type", "video"
            )
            try:
                media_type = MediaType(media_type_str.lower())
            except ValueError:
                media_type = MediaType.VIDEO  # default fallback

            hit = SearchHit(
                asset_id=asset_uuid,
                score=asset_data["max_score"],
                source=asset_data,  # Store grouped clips data
                media_type=media_type,
                provider_metadata={
                    "provider": "coactive",
                    "clips_count": len(asset_data["clips"]),
                },
            )
            hits.append(hit)

        # Sort hits by score
        hits.sort(key=lambda x: x.score, reverse=True)

        self.logger.info(f"Created {len(hits)} SearchHits with max_score: {max_score}")

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
                    # Use the MediaLake OpenSearch record as the base
                    enriched_source = medialake_source.copy()

                    # For videos, add clips array with proper structure
                    if (
                        hit.media_type.value == "video"
                        and isinstance(hit.source, dict)
                        and "clips" in hit.source
                    ):
                        clips = []
                        # Sort clips by ranking score to maintain Coactive's order
                        sorted_clips = sorted(
                            hit.source["clips"],
                            key=lambda x: x.get("score", 0),
                            reverse=True,
                        )
                        for clip_index, clip_data in enumerate(sorted_clips):
                            coactive_metadata = clip_data.get("coactive_metadata", {})

                            # Extract asset information from MediaLake source
                            digital_source_asset = enriched_source.get(
                                "DigitalSourceAsset", {}
                            )
                            main_rep = digital_source_asset.get(
                                "MainRepresentation", {}
                            )
                            storage_info = main_rep.get("StorageInfo", {})
                            primary_location = storage_info.get("PrimaryLocation", {})
                            object_key = primary_location.get("ObjectKey", {})
                            file_info = primary_location.get("FileInfo", {})

                            # Create clip with required structure and proper asset information
                            clip = {
                                "DigitalSourceAsset": {
                                    "ID": digital_source_asset.get("ID", hit.asset_id)
                                },
                                "score": clip_data.get("score", hit.score),
                                "assetType": digital_source_asset.get("Type", ""),
                                "format": main_rep.get("Format", ""),
                                "objectName": object_key.get("Name", ""),
                                "fullPath": object_key.get("FullPath", ""),
                                "bucket": primary_location.get("Bucket", ""),
                                "fileSize": file_info.get("Size", 0),
                                "createdAt": file_info.get("CreateDate", ""),
                                "embedding_scope": "clip",
                                "type": "video",
                                "embedding_option": "visual-text",
                            }

                            # Add timing information from Coactive with proper timecode conversion
                            if coactive_metadata.get("start_time_ms") is not None:
                                start_ms = coactive_metadata["start_time_ms"]
                                end_ms = coactive_metadata.get("end_time_ms", start_ms)

                                # Convert milliseconds to timecode format
                                clip["start_timecode"] = self._ms_to_timecode(start_ms)
                                clip["end_timecode"] = self._ms_to_timecode(end_ms)
                                clip["timestamp"] = digital_source_asset.get(
                                    "CreateDate", ""
                                )

                                self.logger.info(
                                    f"Clip {clip_index + 1} timecodes - start: {clip['start_timecode']}, end: {clip['end_timecode']}"
                                )
                            else:
                                # Fallback timecodes if Coactive doesn't provide timing
                                clip["start_timecode"] = "00:00:00:00"
                                clip["end_timecode"] = "00:00:00:00"

                            clips.append(clip)

                        enriched_source["clips"] = clips
                    else:
                        # For non-video assets, ensure clips is an empty array
                        enriched_source["clips"] = []

                    # Update the hit with enriched data
                    hit.source = enriched_source
                    enriched_hits.append(hit)
                else:
                    # Discard hits without MediaLake data
                    self.logger.warning(
                        f"Discarding result - no MediaLake data found for asset {hit.asset_id}"
                    )

            # Update results with enriched hits
            results.hits = enriched_hits

            # Update total_results to reflect the actual number of results after filtering
            results.total_results = len(enriched_hits)

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

    def _ms_to_timecode(self, milliseconds):
        """
        Convert milliseconds to SMPTE timecode format (HH:MM:SS:FF).

        Args:
            milliseconds: Time in milliseconds

        Returns:
            String in format "HH:MM:SS:FF" (assuming 30fps)
        """
        if not isinstance(milliseconds, (int, float)) or milliseconds < 0:
            return "00:00:00:00"

        # Convert to seconds
        total_seconds = milliseconds / 1000.0

        # Extract hours, minutes, seconds, and frames (assuming 30fps)
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        frames = int((total_seconds % 1) * 30)  # 30fps

        # Format as timecode
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

    def _fetch_medialake_metadata(
        self, asset_ids: List[str], query: SearchQuery
    ) -> List[Dict[str, Any]]:
        """Fetch MediaLake metadata from OpenSearch with filter support"""
        try:
            client = self._get_opensearch_client()
            index_name = os.environ["OPENSEARCH_INDEX"]

            # Build query for specific asset IDs using match queries (same as S3VectorEmbeddingStore)
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
                        "filter": [],
                    }
                },
                "size": len(asset_ids),
            }

            # Apply filters from the original query to the enrichment
            filters_to_add = self._build_filters_from_query(query)
            if filters_to_add:
                opensearch_query["query"]["bool"]["filter"].extend(filters_to_add)
                self.logger.info(
                    f"Applied {len(filters_to_add)} filters to MediaLake enrichment query"
                )

            # For MediaLake enrichment, we always need complete records
            # Ignore any field restrictions from the original query
            # This ensures we get all the MediaLake asset structure needed for the response

            response = client.search(body=opensearch_query, index=index_name)
            hits = response.get("hits", {}).get("hits", [])

            self.logger.info(
                f"Fetched MediaLake metadata for {len(hits)} assets (after filters)"
            )

            # Debug: Log what fields are actually returned
            if hits:
                sample_hit = hits[0]
                source_keys = list(sample_hit.get("_source", {}).keys())
                self.logger.info(f"OpenSearch returned fields: {source_keys}")
                self.logger.info(
                    f"Sample record structure: {sample_hit.get('_source', {})}"
                )

            return hits

        except Exception as e:
            self.logger.error(f"Failed to fetch MediaLake metadata: {str(e)}")
            return []

    def _build_filters_from_query(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Build OpenSearch filters from SearchQuery unified filters"""
        filters = []

        if not query.filters:
            return filters

        # Process unified filters from SearchQuery
        for filter_item in query.filters:
            filter_key = filter_item.get("key")
            filter_operator = filter_item.get("operator")
            filter_value = filter_item.get("value")

            if not filter_key or not filter_operator:
                continue

            # Map filter keys to OpenSearch field paths
            opensearch_field = self._map_filter_field_to_opensearch(filter_key)

            # Build OpenSearch filter based on operator
            if filter_operator == "==" or filter_operator == "term":
                filters.append({"term": {opensearch_field: filter_value}})

            elif filter_operator == "in":
                if isinstance(filter_value, list):
                    filters.append({"terms": {opensearch_field: filter_value}})
                else:
                    # Single value, treat as term
                    filters.append({"term": {opensearch_field: filter_value}})

            elif filter_operator == "range":
                if isinstance(filter_value, dict):
                    range_query = {"range": {opensearch_field: {}}}
                    if "gte" in filter_value:
                        range_query["range"][opensearch_field]["gte"] = filter_value[
                            "gte"
                        ]
                    if "lte" in filter_value:
                        range_query["range"][opensearch_field]["lte"] = filter_value[
                            "lte"
                        ]
                    if "gt" in filter_value:
                        range_query["range"][opensearch_field]["gt"] = filter_value[
                            "gt"
                        ]
                    if "lt" in filter_value:
                        range_query["range"][opensearch_field]["lt"] = filter_value[
                            "lt"
                        ]
                    filters.append(range_query)

            elif filter_operator in [">=", "gte"]:
                filters.append({"range": {opensearch_field: {"gte": filter_value}}})

            elif filter_operator in ["<=", "lte"]:
                filters.append({"range": {opensearch_field: {"lte": filter_value}}})

            elif filter_operator in [">", "gt"]:
                filters.append({"range": {opensearch_field: {"gt": filter_value}}})

            elif filter_operator in ["<", "lt"]:
                filters.append({"range": {opensearch_field: {"lt": filter_value}}})

        return filters

    def _map_filter_field_to_opensearch(self, filter_key: str) -> str:
        """Map unified filter field names to OpenSearch field paths"""
        # Field mappings from unified filter format to OpenSearch paths
        field_mappings = {
            # Media type filters
            "mediaType": "DigitalSourceAsset.Type",
            "DigitalSourceAsset.Type": "DigitalSourceAsset.Type",
            # Format/extension filters
            "format": "DigitalSourceAsset.MainRepresentation.Format",
            "extension": "DigitalSourceAsset.MainRepresentation.Format",
            "DigitalSourceAsset.MainRepresentation.Format": "DigitalSourceAsset.MainRepresentation.Format",
            # File size filters
            "fileSize": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size",
            "asset_size": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size",
            # Date filters
            "createdAt": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.CreateDate",
            "ingested_date": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.CreateDate",
            # Bucket filters
            "bucket": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.Bucket",
            # Object name filters
            "objectName": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name",
            "fileName": "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name",
        }

        return field_mappings.get(filter_key, filter_key)
