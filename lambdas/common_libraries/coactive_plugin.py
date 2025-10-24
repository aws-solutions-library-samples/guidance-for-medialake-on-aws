"""
Coactive AI External Service Plugin
==================================
Plugin for handling Coactive AI asset deletion operations.
"""

import http.client
import json
from typing import Any, Dict, Optional

import boto3
import requests
from botocore.exceptions import ClientError
from search_provider_models import AssetDeletionResult, ExternalServicePlugin


class CoactivePlugin(ExternalServicePlugin):
    """Plugin for Coactive AI external service integration"""

    def __init__(self, config: Dict[str, Any], logger, metrics):
        super().__init__(config, logger, metrics)
        self.secrets_client = boto3.client("secretsmanager")
        self._api_key = None
        self._dataset_id = None

    def get_service_name(self) -> str:
        """Return the name of the external service"""
        return "coactive"

    def is_available(self) -> bool:
        """Check if Coactive AI service is available and properly configured"""
        try:
            # Check if we have the required configuration
            if not self.config.get("dataset_id"):
                self.logger.warning("Coactive dataset_id not configured")
                return False

            if not self.config.get("auth", {}).get("secret_arn"):
                self.logger.warning("Coactive API key not configured")
                return False

            # Try to get the API key to verify it's accessible
            api_key = self._get_api_key()
            if not api_key:
                self.logger.warning("Failed to retrieve Coactive API key")
                return False

            return True

        except Exception as e:
            self.logger.warning(f"Coactive availability check failed: {str(e)}")
            return False

    def supports_asset_type(self, asset_type: str) -> bool:
        """Check if this plugin supports the given asset type"""
        # Coactive supports images and videos
        supported_types = ["image", "video"]
        return asset_type.lower() in supported_types

    def delete_asset(
        self, asset_record: Dict[str, Any], inventory_id: str
    ) -> AssetDeletionResult:
        """Delete asset from Coactive AI dataset by querying with medialake_uuid"""
        try:
            # Get asset type to determine which endpoint to use
            asset_type = (
                asset_record.get("DigitalSourceAsset", {}).get("Type", "").lower()
            )

            if not self.supports_asset_type(asset_type):
                return AssetDeletionResult(
                    success=True,  # Not an error, just not supported
                    message=f"Asset type '{asset_type}' not supported by Coactive",
                    deleted_count=0,
                )

            # Query Coactive to find the asset by medialake_uuid and get its Coactive ID
            coactive_ids = self._find_coactive_ids_by_medialake_uuid(
                inventory_id, asset_type
            )

            if not coactive_ids:
                self.logger.info(
                    f"No Coactive IDs found for MediaLake asset {inventory_id}"
                )
                return AssetDeletionResult(
                    success=True,
                    message=f"Asset not found in Coactive (medialake_uuid: {inventory_id})",
                    deleted_count=0,
                )

            # Delete from Coactive
            deleted_count = 0
            errors = []

            for coactive_id in coactive_ids:
                try:
                    success = self._delete_from_coactive(coactive_id, asset_type)
                    if success:
                        deleted_count += 1
                        self.logger.info(
                            f"Deleted Coactive {asset_type} ID: {coactive_id} (medialake_uuid: {inventory_id})"
                        )
                    else:
                        errors.append(
                            f"Failed to delete {asset_type} ID: {coactive_id}"
                        )
                except Exception as e:
                    error_msg = (
                        f"Error deleting {asset_type} ID {coactive_id}: {str(e)}"
                    )
                    errors.append(error_msg)
                    self.logger.error(error_msg)

            # Record metrics
            if deleted_count > 0:
                self.metrics.add_metric(
                    name="CoactiveAssetsDeleted", unit="Count", value=deleted_count
                )

            if errors:
                self.metrics.add_metric(
                    name="CoactiveDeletionErrors", unit="Count", value=len(errors)
                )

            success = deleted_count > 0 or len(errors) == 0
            message = f"Deleted {deleted_count} Coactive {asset_type}(s) for medialake_uuid: {inventory_id}"
            if errors:
                message += f" with {len(errors)} errors"

            return AssetDeletionResult(
                success=success,
                message=message,
                deleted_count=deleted_count,
                errors=errors,
            )

        except Exception as e:
            self.logger.error(
                f"Coactive asset deletion failed for {inventory_id}: {str(e)}"
            )
            self.metrics.add_metric(
                name="CoactiveDeletionErrors", unit="Count", value=1
            )
            return AssetDeletionResult(
                success=False,
                message=f"Coactive deletion failed: {str(e)}",
                errors=[str(e)],
            )

    def _get_api_key(self) -> Optional[str]:
        """Get Coactive API key from AWS Secrets Manager"""
        if self._api_key:
            return self._api_key

        try:
            secret_arn = self.config.get("auth", {}).get("secret_arn")
            if not secret_arn:
                return None

            response = self.secrets_client.get_secret_value(SecretId=secret_arn)
            secret_data = json.loads(response["SecretString"])
            self._api_key = secret_data.get("x-api-key") or secret_data.get("api_key")
            return self._api_key

        except ClientError as e:
            self.logger.error(f"Failed to retrieve Coactive API key: {e}")
            return None

    def _get_dataset_id(self) -> Optional[str]:
        """Get Coactive dataset ID from configuration"""
        if self._dataset_id:
            return self._dataset_id

        self._dataset_id = self.config.get("dataset_id")
        return self._dataset_id

    def _get_auth_token(self) -> Optional[str]:
        """Get JWT access token by exchanging personal token with Coactive API"""
        try:
            # Get API key (personal token) from config
            api_key = self._get_api_key()
            if not api_key:
                self.logger.warning("No API key available for Coactive authentication")
                return None

            # Exchange personal token for JWT access token
            conn = http.client.HTTPSConnection("api.coactive.ai")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            payload = {"grant_type": "refresh_token"}
            body = json.dumps(payload)

            self.logger.info("Exchanging personal token for JWT access token")
            conn.request("POST", "/api/v0/login", body=body, headers=headers)
            auth_response = conn.getresponse()
            response_data = auth_response.read().decode("utf-8")
            conn.close()

            if auth_response.status != 200:
                self.logger.error(
                    f"Coactive authentication failed: {auth_response.status} - {response_data}"
                )
                return None

            auth_data = json.loads(response_data)
            access_token = auth_data.get("access_token")

            if not access_token:
                self.logger.error(f"No access_token in response: {auth_data}")
                return None

            self.logger.info("Successfully obtained JWT access token from Coactive API")
            return access_token

        except Exception as e:
            self.logger.error(f"Failed to get Coactive auth token: {str(e)}")
            return None

    def _find_coactive_ids_by_medialake_uuid(
        self, medialake_uuid: str, asset_type: str
    ) -> list:
        """
        Query Coactive API to find Coactive IDs by medialake_uuid.
        Uses metadata filtering to find assets indexed with this MediaLake UUID.
        """
        try:
            auth_token = self._get_auth_token()
            if not auth_token:
                self.logger.error("No auth token available for Coactive query")
                return []

            # Build search payload with metadata filter for medialake_uuid
            # Using text-to-image endpoint with empty query and metadata filter
            payload = {
                "dataset_id": self.config.get("dataset_id"),
                "text_query": "",  # Empty query to match all
                "offset": 0,
                "limit": 100,  # Should be enough for one asset
                "metadata_filters": [
                    {
                        "key": "medialake_uuid",
                        "operator": "==",
                        "value": medialake_uuid,
                    }
                ],
            }

            # Add asset_type filter if it's a video
            if asset_type == "video":
                payload["asset_type"] = "video"

            self.logger.info(
                f"Querying Coactive for medialake_uuid: {medialake_uuid} (type: {asset_type})"
            )

            # Make request to Coactive search API
            endpoint = "https://api.coactive.ai/api/v1/search/text-to-image"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth_token}",
            }

            conn = http.client.HTTPSConnection("api.coactive.ai")
            body = json.dumps(payload)
            conn.request(
                "POST", "/api/v1/search/text-to-image", body=body, headers=headers
            )
            response = conn.getresponse()
            response_data = response.read().decode("utf-8")
            conn.close()

            if response.status != 200:
                self.logger.error(
                    f"Coactive query failed: {response.status} - {response_data}"
                )
                return []

            # Parse response and extract Coactive IDs
            result = json.loads(response_data)
            coactive_ids = []

            for item in result.get("data", []):
                if asset_type == "image":
                    # For images, the ID is in the coactiveImageId field
                    if coactive_id := item.get("coactiveImageId"):
                        coactive_ids.append(coactive_id)
                elif asset_type == "video":
                    # For videos, the ID is in video.coactiveVideoId
                    if video_data := item.get("video"):
                        if coactive_id := video_data.get("coactiveVideoId"):
                            coactive_ids.append(coactive_id)

            # Remove duplicates
            coactive_ids = list(dict.fromkeys(coactive_ids))

            self.logger.info(
                f"Found {len(coactive_ids)} Coactive ID(s) for medialake_uuid {medialake_uuid}: {coactive_ids}"
            )

            return coactive_ids

        except Exception as e:
            self.logger.error(
                f"Failed to query Coactive for medialake_uuid {medialake_uuid}: {str(e)}"
            )
            return []

    def _delete_from_coactive(self, coactive_id: str, asset_type: str) -> bool:
        """Delete asset from Coactive AI using their API"""
        try:
            api_key = self._get_api_key()
            dataset_id = self._get_dataset_id()

            if not api_key or not dataset_id:
                self.logger.error("Missing Coactive API key or dataset ID")
                return False

            # Determine the correct endpoint based on asset type (using singular form per API docs)
            if asset_type == "video":
                endpoint = f"https://app.coactive.ai/api/v1/datasets/{dataset_id}/video/{coactive_id}"
            elif asset_type == "image":
                endpoint = f"https://app.coactive.ai/api/v1/datasets/{dataset_id}/image/{coactive_id}"
            else:
                self.logger.error(
                    f"Unsupported asset type for Coactive deletion: {asset_type}"
                )
                return False

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            self.logger.info(
                f"Deleting Coactive {asset_type} ID {coactive_id} from dataset {dataset_id}"
            )

            response = requests.delete(endpoint, headers=headers, timeout=30)

            if response.status_code == 200:
                self.logger.info(
                    f"Successfully deleted Coactive {asset_type} ID: {coactive_id}"
                )
                return True
            elif response.status_code == 404:
                # Asset not found in Coactive - this is OK, maybe it was already deleted
                self.logger.info(
                    f"Coactive {asset_type} ID {coactive_id} not found (already deleted?)"
                )
                return True
            else:
                self.logger.error(
                    f"Coactive deletion failed for {asset_type} ID {coactive_id}: "
                    f"HTTP {response.status_code} - {response.text}"
                )
                return False

        except requests.exceptions.RequestException as e:
            self.logger.error(
                f"Network error deleting Coactive {asset_type} ID {coactive_id}: {str(e)}"
            )
            return False
        except Exception as e:
            self.logger.error(
                f"Unexpected error deleting Coactive {asset_type} ID {coactive_id}: {str(e)}"
            )
            return False
