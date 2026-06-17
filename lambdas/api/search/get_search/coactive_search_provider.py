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
        self._cached_token = None
        self._token_expiry = 0
        self._response_adapter = None

    def _get_response_adapter(self):
        """Get or create the response adapter based on configuration."""
        if self._response_adapter is None:
            from coactive_response_adapters import get_response_adapter

            fmt = self.config.response_format or "v1"
            self._response_adapter = get_response_adapter(fmt)
            self.logger.info(
                f"Using Coactive response adapter: {self._response_adapter.get_format_version()}"
            )
        return self._response_adapter

    def _get_search_endpoint(self) -> str:
        """Get the configured search endpoint, falling back to defaults."""
        from coactive_response_adapters import get_default_endpoints

        if self.config.search_endpoint:
            return self.config.search_endpoint
        if self.config.endpoint:
            return self.config.endpoint
        fmt = self.config.response_format or "v1"
        return get_default_endpoints(fmt)["search"]

    def _get_auth_endpoint(self) -> str:
        """Get the configured auth endpoint, falling back to default."""
        from coactive_response_adapters import get_default_endpoints

        if self.config.auth_endpoint:
            return self.config.auth_endpoint
        fmt = self.config.response_format or "v1"
        return get_default_endpoints(fmt)["auth"]

    def _get_provider_location(self) -> ProviderLocation:
        return ProviderLocation.EXTERNAL

    def _get_opensearch_client(self) -> OpenSearch:
        """Create and return a cached OpenSearch client for metadata enrichment.

        Uses refreshable credentials so that long-lived Lambda containers
        never sign requests with expired IAM tokens.
        """
        if self._opensearch_client is None:
            from refreshable_auth import get_refreshable_credentials

            host = os.environ["OPENSEARCH_ENDPOINT"].replace("https://", "")
            region = os.environ["AWS_REGION"]
            service_scope = os.environ["SCOPE"]

            auth = RequestsAWSV4SignerAuth(
                get_refreshable_credentials(), region, service_scope
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
        # Return cached token if still valid
        now = time.time()
        if self._cached_token and self._token_expiry > now:
            return self._cached_token

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
                    auth_endpoint = self._get_auth_endpoint()
                    from urllib.parse import urlparse

                    parsed_auth = urlparse(auth_endpoint)
                    auth_host = parsed_auth.netloc
                    auth_path = parsed_auth.path

                    conn = http.client.HTTPSConnection(auth_host)
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {personal_token}",
                    }
                    payload = {"grant_type": "refresh_token"}
                    body = json_lib.dumps(payload)

                    self.logger.info(
                        f"Making authentication request to {auth_endpoint}"
                    )
                    conn.request("POST", auth_path, body=body, headers=headers)
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
                    self._cached_token = access_token
                    self._token_expiry = time.time() + 3300  # 55 minutes
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
        """Build Coactive API request payload.

        Uses 'query' field for custom endpoints (v2) and 'text_query' for the
        default Coactive API (v1).
        """
        from coactive_response_adapters import COACTIVE_DEFAULT_ENDPOINTS

        search_endpoint = self._get_search_endpoint()
        is_default_endpoint = search_endpoint in [
            defaults["search"] for defaults in COACTIVE_DEFAULT_ENDPOINTS.values()
        ]

        # Custom endpoints use 'query'; default Coactive API uses 'text_query'
        query_field = "text_query" if is_default_endpoint else "query"

        payload = {
            "dataset_id": self.config.dataset_id,
            query_field: query.query_text,
            "offset": query.page_offset,
            "limit": query.page_size,
        }

        # Only add asset_type filter if explicitly provided in query filters
        # Don't automatically filter by asset_type based on include_clips
        # as this would exclude images when in clip mode
        if query.filters:
            for filter_item in query.filters:
                key = filter_item.get("key", filter_item.get("field", ""))
                if key in ("asset_type", "DigitalSourceAsset.Type"):
                    payload["asset_type"] = filter_item.get("value")
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
        """Make HTTP request to Coactive API using configured search endpoint"""
        from coactive_response_adapters import COACTIVE_DEFAULT_ENDPOINTS

        # Use the configurable search endpoint
        endpoint = self._get_search_endpoint()

        # Get auth token from Secrets Manager
        auth_token = self._get_auth_token()
        if not auth_token:
            raise Exception("Coactive auth token not available")

        # Determine if this is a custom endpoint or the default Coactive API
        is_default_endpoint = endpoint in [
            defaults["search"] for defaults in COACTIVE_DEFAULT_ENDPOINTS.values()
        ]

        # Default Coactive API uses Authorization: Bearer
        # Custom endpoints use x-coactive-key header
        if is_default_endpoint:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth_token}",
            }
        else:
            headers = {
                "Content-Type": "application/json",
                "x-coactive-key": auth_token,
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
        Convert Coactive API response to SearchResult using the configured response adapter.

        The adapter pattern allows this method to remain format-agnostic. The active
        adapter (V1 or V2) handles all response-format-specific field extraction.

        If no explicit response_format is configured, the adapter is auto-detected
        from the response structure.
        """
        from coactive_response_adapters import (
            detect_response_format,
            get_response_adapter,
        )

        # Use configured adapter, or auto-detect from response
        if self.config.response_format:
            adapter = self._get_response_adapter()
        else:
            detected_format = detect_response_format(response)
            adapter = get_response_adapter(detected_format)
            self.logger.info(
                f"Auto-detected Coactive response format: {detected_format}"
            )

        results = adapter.get_results(response)
        total_count = adapter.get_total_count(response, results)

        self.logger.info(
            f"Processing {len(results)} Coactive search results "
            f"(format: {adapter.get_format_version()})"
        )

        # Group results by MediaLake asset UUID to create proper clips structure
        assets_with_clips = {}
        max_score = 1.0
        for i, result in enumerate(results):
            self.logger.info(f"[CLIP_DEBUG] Processing result {i+1}/{len(results)}")

            medialake_uuid = adapter.get_medialake_uuid(result)
            if not medialake_uuid:
                self.logger.warning(
                    f"No MediaLake UUID found in Coactive result: {result}"
                )
                continue

            rank = i + 1
            score = adapter.get_score(result, rank)

            if score > max_score:
                max_score = score

            coactive_metadata = adapter.get_coactive_metadata(result)

            # Group clips by asset UUID
            if medialake_uuid not in assets_with_clips:
                assets_with_clips[medialake_uuid] = {
                    "asset_id": medialake_uuid,
                    "clips": [],
                    "max_score": score,
                }
            else:
                if score > assets_with_clips[medialake_uuid]["max_score"]:
                    assets_with_clips[medialake_uuid]["max_score"] = score

            # Create clip data with rank and score
            clip_data = {
                "score": score,
                "rank": rank,
                "coactive_metadata": coactive_metadata,
                "coactive_result": result,
            }

            assets_with_clips[medialake_uuid]["clips"].append(clip_data)

        self.logger.info(f"Grouped results into {len(assets_with_clips)} unique assets")

        # Convert to SearchHit format
        hits = []
        for asset_uuid, asset_data in assets_with_clips.items():
            # Determine media type from first clip's result
            first_clip = asset_data["clips"][0] if asset_data["clips"] else {}
            first_result = first_clip.get("coactive_result", {})
            media_type_str = adapter.get_media_type(first_result)
            try:
                media_type = MediaType(media_type_str.lower())
            except ValueError:
                media_type = MediaType.VIDEO

            hit = SearchHit(
                asset_id=asset_uuid,
                score=asset_data["max_score"],
                source=asset_data,
                media_type=media_type,
                provider_metadata={
                    "provider": "coactive",
                    "clips_count": len(asset_data["clips"]),
                    "response_format": adapter.get_format_version(),
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
            took_ms=0,
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
        """Fetch MediaLake metadata from OpenSearch with filter support.

        Uses the shared ``fetch_parent_docs_batch`` utility so metadata filters
        are applied at query time by OpenSearch, and only the required + UI-requested
        fields are returned.
        """
        try:
            from metadata_filter_utils import fetch_parent_docs_batch

            client = self._get_opensearch_client()
            index_name = os.environ["OPENSEARCH_INDEX"]

            # Extract deferred/metadata filters from the query
            filters = query.filters if query.filters else None

            parent_lookup = fetch_parent_docs_batch(
                client=client,
                index_name=index_name,
                inventory_ids=asset_ids,
                filters=filters,
                ui_fields=query.fields,
            )

            self.logger.info(
                f"Fetched MediaLake metadata for {len(parent_lookup)} assets "
                f"(requested {len(asset_ids)}, after filters)"
            )

            # Return in the format expected by enrich_results_with_medialake_data
            return [{"_source": source} for source in parent_lookup.values()]

        except Exception as e:
            self.logger.error(f"Failed to fetch MediaLake metadata: {str(e)}")
            return []

    def _build_filters_from_query(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Build OpenSearch filters from SearchQuery unified filters.

        Delegates to the shared ``build_opensearch_filters`` utility so filter
        behavior is consistent across all providers.
        """
        from metadata_filter_utils import build_opensearch_filters

        if not query.filters:
            return []

        return build_opensearch_filters(query.filters)

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
