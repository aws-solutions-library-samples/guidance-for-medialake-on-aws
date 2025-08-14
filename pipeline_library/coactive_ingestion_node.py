"""
Pipeline node for ingesting assets into Coactive for semantic search.
Handles dataset registration, proxy URL generation, and ingestion callbacks.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional

import boto3
import requests


class CoactiveIngestionNode:
    """Pipeline node for ingesting MediaLake assets into Coactive"""

    def __init__(self, logger, metrics):
        self.logger = logger
        self.metrics = metrics
        self.s3_client = boto3.client("s3")
        self.secretsmanager = boto3.client("secretsmanager")
        self.dynamodb = boto3.resource("dynamodb")

        # Configuration will be loaded from system settings
        self.config = None
        self._load_configuration()

    def _load_configuration(self):
        """Load Coactive configuration from system settings"""
        try:
            system_settings_table = self.dynamodb.Table(
                os.environ.get("SYSTEM_SETTINGS_TABLE")
            )

            # Try to get unified search provider config first
            response = system_settings_table.get_item(
                Key={"PK": "SYSTEM_SETTINGS", "SK": "SEARCH_PROVIDERS"}
            )

            if response.get("Item") and response["Item"].get("providers"):
                for provider in response["Item"]["providers"]:
                    if provider.get("provider") == "coactive":
                        self.config = provider
                        break

            # Fall back to legacy Coactive config
            if not self.config:
                coactive_response = system_settings_table.get_item(
                    Key={"PK": "SYSTEM_SETTINGS", "SK": "COACTIVE_SEARCH"}
                )

                if coactive_response.get("Item") and coactive_response["Item"].get(
                    "isEnabled"
                ):
                    item = coactive_response["Item"]
                    self.config = {
                        "provider": "coactive",
                        "dataset_id": item.get("datasetId"),
                        "endpoint": item.get(
                            "endpoint", "https://app.coactive.ai/api/v1"
                        ),
                        "auth": {"secret_arn": item.get("secretArn")},
                        "metadata_mapping": item.get("metadataMapping", {}),
                    }

            if self.config:
                self.logger.info("Loaded Coactive configuration for ingestion")
            else:
                self.logger.warning("No Coactive configuration found")

        except Exception as e:
            self.logger.error(f"Failed to load Coactive configuration: {str(e)}")
            self.config = None

    def is_available(self) -> bool:
        """Check if Coactive ingestion is available and configured"""
        return (
            self.config is not None
            and self.config.get("dataset_id")
            and self.config.get("auth", {}).get("secret_arn")
        )

    def process_asset(self, asset_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single asset for Coactive ingestion.

        Args:
            asset_data: MediaLake asset data

        Returns:
            Processing result with status and metadata
        """
        if not self.is_available():
            return {
                "status": "skipped",
                "message": "Coactive ingestion not configured",
                "asset_id": asset_data.get("InventoryID", "unknown"),
            }

        start_time = time.time()
        asset_id = asset_data.get("InventoryID", "")

        try:
            self.logger.info(f"Processing asset for Coactive ingestion: {asset_id}")

            # Extract asset information
            asset_info = self._extract_asset_info(asset_data)

            if not asset_info:
                return {
                    "status": "skipped",
                    "message": "Asset not suitable for Coactive ingestion",
                    "asset_id": asset_id,
                }

            # Generate proxy URL for Coactive access
            proxy_url = self._generate_proxy_url(asset_info)

            if not proxy_url:
                return {
                    "status": "failed",
                    "message": "Failed to generate proxy URL",
                    "asset_id": asset_id,
                }

            # Prepare metadata for Coactive
            metadata = self._prepare_metadata(asset_data, asset_info)

            # Submit to Coactive for ingestion
            coactive_result = self._submit_to_coactive(proxy_url, metadata, asset_id)

            processing_time = time.time() - start_time

            if coactive_result.get("success"):
                self.logger.info(
                    f"Successfully submitted asset to Coactive: {asset_id} in {processing_time:.2f}s"
                )
                return {
                    "status": "success",
                    "message": "Asset submitted to Coactive",
                    "asset_id": asset_id,
                    "coactive_id": coactive_result.get("coactive_id"),
                    "processing_time": processing_time,
                }
            else:
                self.logger.error(f"Failed to submit asset to Coactive: {asset_id}")
                return {
                    "status": "failed",
                    "message": coactive_result.get("error", "Unknown error"),
                    "asset_id": asset_id,
                    "processing_time": processing_time,
                }

        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(
                f"Error processing asset {asset_id} for Coactive: {str(e)}"
            )
            return {
                "status": "error",
                "message": str(e),
                "asset_id": asset_id,
                "processing_time": processing_time,
            }

    def _extract_asset_info(
        self, asset_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract relevant asset information for Coactive ingestion"""
        try:
            digital_source_asset = asset_data.get("DigitalSourceAsset", {})
            main_rep = digital_source_asset.get("MainRepresentation", {})
            storage_info = main_rep.get("StorageInfo", {}).get("PrimaryLocation", {})

            # Check if asset is suitable for Coactive (video, audio, image)
            asset_type = digital_source_asset.get("Type", "").lower()
            if asset_type not in ["video", "audio", "image"]:
                self.logger.debug(f"Asset type {asset_type} not suitable for Coactive")
                return None

            # Extract storage information
            bucket = storage_info.get("Bucket")
            key = storage_info.get("ObjectKey", {}).get("FullPath")

            if not bucket or not key:
                self.logger.warning("Missing S3 bucket or key information")
                return None

            return {
                "bucket": bucket,
                "key": key,
                "asset_type": asset_type,
                "format": main_rep.get("Format", ""),
                "file_size": storage_info.get("FileSize", 0),
                "storage_info": storage_info,
            }

        except Exception as e:
            self.logger.error(f"Error extracting asset info: {str(e)}")
            return None

    def _generate_proxy_url(self, asset_info: Dict[str, Any]) -> Optional[str]:
        """Generate a proxy URL for Coactive to access the asset"""
        try:
            bucket = asset_info["bucket"]
            key = asset_info["key"]

            # Generate presigned URL with longer expiration for ingestion
            presigned_url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=3600 * 24,  # 24 hours
            )

            self.logger.debug(f"Generated proxy URL for {bucket}/{key}")
            return presigned_url

        except Exception as e:
            self.logger.error(f"Error generating proxy URL: {str(e)}")
            return None

    def _prepare_metadata(
        self, asset_data: Dict[str, Any], asset_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare metadata for Coactive ingestion"""
        try:
            # Base metadata
            metadata = {
                "medialake_uuid": asset_data.get("InventoryID", ""),
                "media_type": asset_info["asset_type"],
                "file_format": asset_info["format"],
                "file_size": asset_info["file_size"],
            }

            # Add consolidated metadata if available
            consolidated_metadata = asset_data.get("Metadata", {}).get(
                "Consolidated", {}
            )
            if consolidated_metadata:
                # Map common fields
                field_mappings = {
                    "duration": "duration_ms",
                    "width": "width",
                    "height": "height",
                    "title": "title",
                    "description": "description",
                }

                for source_field, target_field in field_mappings.items():
                    if source_field in consolidated_metadata:
                        metadata[target_field] = consolidated_metadata[source_field]

            # Add creation date
            digital_source_asset = asset_data.get("DigitalSourceAsset", {})
            if "CreateDate" in digital_source_asset:
                metadata["created_at"] = digital_source_asset["CreateDate"]

            # Apply custom metadata mapping if configured
            if self.config.get("metadata_mapping"):
                mapped_metadata = {}
                for source_field, target_field in self.config[
                    "metadata_mapping"
                ].items():
                    if source_field in metadata:
                        mapped_metadata[target_field] = metadata[source_field]
                    else:
                        # Try to extract from nested structure
                        value = self._extract_nested_value(asset_data, source_field)
                        if value is not None:
                            mapped_metadata[target_field] = value

                # Merge with existing metadata
                metadata.update(mapped_metadata)

            return metadata

        except Exception as e:
            self.logger.error(f"Error preparing metadata: {str(e)}")
            return {"medialake_uuid": asset_data.get("InventoryID", "")}

    def _extract_nested_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """Extract value from nested dictionary using dot notation"""
        try:
            keys = field_path.split(".")
            value = data

            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None

            return value

        except Exception:
            return None

    def _submit_to_coactive(
        self, proxy_url: str, metadata: Dict[str, Any], asset_id: str
    ) -> Dict[str, Any]:
        """Submit asset to Coactive for ingestion"""
        try:
            # Get API key from Secrets Manager
            api_key = self._get_api_key()
            if not api_key:
                return {"success": False, "error": "Failed to get API key"}

            # Prepare Coactive ingestion payload
            payload = {
                "dataset_id": self.config["dataset_id"],
                "url": proxy_url,
                "metadata": metadata,
                "external_id": asset_id,  # Use MediaLake asset ID as external ID
            }

            # Make request to Coactive ingestion API
            endpoint = f"{self.config['endpoint'].rstrip('/')}/ingest"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }

            self.logger.debug(f"Submitting to Coactive: {endpoint}")

            response = requests.post(
                endpoint, headers=headers, json=payload, timeout=30
            )

            if response.status_code == 200 or response.status_code == 201:
                result = response.json()
                return {
                    "success": True,
                    "coactive_id": result.get("id"),
                    "status": result.get("status", "submitted"),
                }
            else:
                self.logger.error(
                    f"Coactive API error: {response.status_code} - {response.text}"
                )
                return {"success": False, "error": f"API error: {response.status_code}"}

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error submitting to Coactive: {str(e)}")
            return {"success": False, "error": f"Request error: {str(e)}"}
        except Exception as e:
            self.logger.error(f"Error submitting to Coactive: {str(e)}")
            return {"success": False, "error": str(e)}

    def _get_api_key(self) -> Optional[str]:
        """Get Coactive API key from Secrets Manager"""
        try:
            secret_arn = self.config.get("auth", {}).get("secret_arn")
            if not secret_arn:
                self.logger.error("No secret ARN configured for Coactive")
                return None

            response = self.secretsmanager.get_secret_value(SecretId=secret_arn)

            if response and "SecretString" in response:
                secret_data = json.loads(response["SecretString"])
                return secret_data.get("api_key") or secret_data.get("token")

            return None

        except Exception as e:
            self.logger.error(f"Error getting Coactive API key: {str(e)}")
            return None

    def process_batch(self, assets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a batch of assets for Coactive ingestion.

        Args:
            assets: List of MediaLake asset data

        Returns:
            Batch processing results
        """
        if not self.is_available():
            return {
                "status": "skipped",
                "message": "Coactive ingestion not configured",
                "total_assets": len(assets),
                "processed": 0,
            }

        start_time = time.time()
        results = {"success": [], "failed": [], "skipped": [], "errors": []}

        self.logger.info(
            f"Processing batch of {len(assets)} assets for Coactive ingestion"
        )

        for asset_data in assets:
            result = self.process_asset(asset_data)
            status = result.get("status")

            if status == "success":
                results["success"].append(result)
            elif status == "failed":
                results["failed"].append(result)
            elif status == "skipped":
                results["skipped"].append(result)
            else:
                results["errors"].append(result)

        total_time = time.time() - start_time

        summary = {
            "status": "completed",
            "total_assets": len(assets),
            "successful": len(results["success"]),
            "failed": len(results["failed"]),
            "skipped": len(results["skipped"]),
            "errors": len(results["errors"]),
            "processing_time": total_time,
            "results": results,
        }

        self.logger.info(
            f"Batch processing completed: {summary['successful']} successful, "
            f"{summary['failed']} failed, {summary['skipped']} skipped, "
            f"{summary['errors']} errors in {total_time:.2f}s"
        )

        return summary

    def handle_ingestion_callback(
        self, callback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle ingestion completion callback from Coactive.

        Args:
            callback_data: Callback data from Coactive

        Returns:
            Callback processing result
        """
        try:
            external_id = callback_data.get("external_id")  # MediaLake asset ID
            coactive_id = callback_data.get("id")
            status = callback_data.get("status")

            self.logger.info(
                f"Received Coactive callback for asset {external_id}: {status}"
            )

            # Update MediaLake asset with Coactive ingestion status
            # This could update a status table or trigger further processing

            return {
                "status": "processed",
                "asset_id": external_id,
                "coactive_id": coactive_id,
                "ingestion_status": status,
            }

        except Exception as e:
            self.logger.error(f"Error handling Coactive callback: {str(e)}")
            return {"status": "error", "message": str(e)}
