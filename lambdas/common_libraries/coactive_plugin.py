"""
Coactive AI External Service Plugin
==================================
Plugin for handling Coactive AI asset deletion operations.
"""

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
        """Delete asset from Coactive AI dataset"""
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

            # Look for Coactive IDs in the asset metadata
            coactive_ids = self._extract_coactive_ids(asset_record, asset_type)

            if not coactive_ids:
                self.logger.info(f"No Coactive IDs found for asset {inventory_id}")
                return AssetDeletionResult(
                    success=True,
                    message="No Coactive IDs found for this asset",
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
                            f"Deleted Coactive {asset_type} ID: {coactive_id}"
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
            message = f"Deleted {deleted_count} Coactive {asset_type}(s)"
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

    def _extract_coactive_ids(
        self, asset_record: Dict[str, Any], asset_type: str
    ) -> list:
        """Extract Coactive IDs from asset record metadata"""
        coactive_ids = []

        # Look in various places where Coactive IDs might be stored
        # Check main metadata
        metadata = asset_record.get("Metadata", {})
        if isinstance(metadata, dict):
            # Look for coactive_video_id or coactive_image_id
            if asset_type == "video":
                if coactive_id := metadata.get("coactive_video_id"):
                    coactive_ids.append(coactive_id)
            elif asset_type == "image":
                if coactive_id := metadata.get("coactive_image_id"):
                    coactive_ids.append(coactive_id)

        # Check embedded metadata
        embedded = asset_record.get("Metadata", {}).get("Embedded", {})
        if isinstance(embedded, dict):
            # Look for Coactive metadata in S3 metadata
            s3_metadata = embedded.get("S3", {}).get("Metadata", {})
            if isinstance(s3_metadata, dict):
                if asset_type == "video":
                    if coactive_id := s3_metadata.get("coactive_video_id"):
                        coactive_ids.append(coactive_id)
                elif asset_type == "image":
                    if coactive_id := s3_metadata.get("coactive_image_id"):
                        coactive_ids.append(coactive_id)

        # Remove duplicates while preserving order
        return list(dict.fromkeys(coactive_ids))

    def _delete_from_coactive(self, coactive_id: str, asset_type: str) -> bool:
        """Delete asset from Coactive AI using their API"""
        try:
            api_key = self._get_api_key()
            dataset_id = self._get_dataset_id()

            if not api_key or not dataset_id:
                self.logger.error("Missing Coactive API key or dataset ID")
                return False

            # Determine the correct endpoint based on asset type
            if asset_type == "video":
                endpoint = f"https://app.coactive.ai/api/v1/datasets/{dataset_id}/videos/{coactive_id}"
            elif asset_type == "image":
                endpoint = f"https://app.coactive.ai/api/v1/datasets/{dataset_id}/images/{coactive_id}"
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
