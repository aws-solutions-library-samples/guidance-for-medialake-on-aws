import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from common import AssetProcessor, JobStatus, get_optimized_client

logger = Logger()
tracer = Tracer()
metrics = Metrics()


class AssetSyncEngine:
    """Handles S3 asset synchronization using S3 Batch Operations"""

    def __init__(
        self,
        job_id: str,
        bucket_name: str,
        prefix: Optional[str] = None,
        max_concurrent_tasks: int = 500,
    ):
        self.job_id = job_id
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.max_concurrent_tasks = max_concurrent_tasks
        self.s3_client = boto3.client("s3")
        self.results_bucket = os.environ["RESULTS_BUCKET_NAME"]

    def lookup_connector_details(self) -> tuple[Optional[str], Optional[list]]:
        """
        Look up the SQS queue URL and prefixes for this bucket from the connector table

        Returns:
            Tuple of (SQS queue URL or None, list of prefixes or None)
        """
        try:
            # Get the connector table name from environment variables
            connector_table_name = os.environ.get("CONNECTOR_TABLE_NAME")
            if not connector_table_name:
                logger.warning(
                    "CONNECTOR_TABLE_NAME environment variable not set, cannot lookup connector by bucket"
                )
                return None, None

            # Get DynamoDB client
            dynamodb = get_optimized_client("dynamodb")

            logger.info(f"Looking up connector for bucket: {self.bucket_name}")

            # Scan the connector table to find a connector with matching storageIdentifier
            response = dynamodb.scan(
                TableName=connector_table_name,
                FilterExpression="storageIdentifier = :bucket_name AND #status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":bucket_name": {"S": self.bucket_name},
                    ":status": {"S": "active"},
                },
                ProjectionExpression="id, queueUrl, storageIdentifier, #status, objectPrefix",
            )

            # Check if we found any matching connectors
            items = response.get("Items", [])
            if not items:
                logger.warning(
                    f"No active connector found for bucket: {self.bucket_name}"
                )
                return None, None

            if len(items) > 1:
                logger.warning(
                    f"Multiple active connectors found for bucket {self.bucket_name}, using the first one"
                )

            # Extract the queue URL and prefixes from the first matching connector
            connector = items[0]
            queue_url = connector.get("queueUrl", {}).get("S")

            # Handle objectPrefix - stored as a List attribute in DynamoDB
            prefixes = None
            if "objectPrefix" in connector:
                object_prefix_value = connector["objectPrefix"]
                if "L" in object_prefix_value:
                    # List attribute - extract string values
                    prefixes = []
                    for item in object_prefix_value["L"]:
                        if "S" in item:
                            prefixes.append(item["S"])
                elif "S" in object_prefix_value:
                    # Single string prefix (fallback)
                    prefixes = [object_prefix_value["S"]]
                elif "SS" in object_prefix_value:
                    # String set (fallback)
                    prefixes = list(object_prefix_value["SS"])

            # Also check for legacy prefix fields (backward compatibility)
            if not prefixes:
                # Check for 'prefixes' field
                if "prefixes" in connector:
                    prefixes_value = connector["prefixes"]
                    if "L" in prefixes_value:
                        prefixes = []
                        for item in prefixes_value["L"]:
                            if "S" in item:
                                prefixes.append(item["S"])
                    elif "SS" in prefixes_value:
                        prefixes = list(prefixes_value["SS"])
                    elif "S" in prefixes_value:
                        prefixes = [prefixes_value["S"]]

                # Check for single 'prefix' field
                if not prefixes and "prefix" in connector:
                    prefix_value = connector["prefix"].get("S")
                    if prefix_value:
                        prefixes = [prefix_value]

            if queue_url:
                logger.info(
                    f"Found queue URL for bucket {self.bucket_name}: {queue_url}"
                )
            else:
                logger.warning(
                    f"Connector found for bucket {self.bucket_name} but no queueUrl field"
                )

            if prefixes:
                logger.info(f"Found prefixes for bucket {self.bucket_name}: {prefixes}")
            else:
                logger.info(f"No prefixes found for bucket {self.bucket_name}")

            return queue_url, prefixes

        except Exception as e:
            logger.error(
                f"Error looking up connector details for bucket {self.bucket_name}: {str(e)}",
                exc_info=True,
            )
            return None, None

    def create_batch_operations_job(self) -> str:
        """Create and start an S3 Batch Operations job with manifest generation"""
        AssetProcessor.update_job_status(
            self.job_id,
            JobStatus.DISCOVERING,
            f"Initiating inventory generation for {self.bucket_name}",
        )

        try:
            # Look up the ingest queue URL and prefixes for this bucket/connector
            ingest_queue_url, prefixes = self.lookup_connector_details()

            if prefixes and len(prefixes) > 1:
                # Create separate batch jobs for each prefix
                logger.info(f"Multiple prefixes found: {prefixes}")
                logger.info(
                    f"Creating {len(prefixes)} separate batch jobs for complete coverage"
                )
                return self._create_multiple_prefix_jobs(ingest_queue_url, prefixes)
            else:
                # Single prefix or no prefix - create one job
                single_prefix = prefixes[0] if prefixes else None
                return self._create_single_batch_job(ingest_queue_url, single_prefix)

        except Exception as e:
            logger.error(f"Batch job creation failed: {str(e)}", exc_info=True)
            AssetProcessor.update_job_status(
                self.job_id, JobStatus.FAILED, f"Batch job creation failed: {str(e)}"
            )
            raise

    def _create_multiple_prefix_jobs(
        self, ingest_queue_url: Optional[str], prefixes: list
    ) -> str:
        """Create separate batch jobs for each prefix"""
        batch_job_ids = []
        failed_prefixes = []

        for i, prefix in enumerate(prefixes):
            logger.info(
                f"Creating batch job {i+1}/{len(prefixes)} for prefix: {prefix}"
            )

            try:
                batch_job_id = self._create_single_batch_job(
                    ingest_queue_url,
                    prefix,
                    job_suffix=f"-prefix-{i+1}",
                    description_suffix=f" (prefix {i+1}/{len(prefixes)}: {prefix})",
                )
                batch_job_ids.append(batch_job_id)
                logger.info(f"Created batch job {batch_job_id} for prefix: {prefix}")

            except Exception as e:
                logger.error(
                    f"Failed to create batch job for prefix {prefix}: {str(e)}"
                )
                failed_prefixes.append(prefix)
                continue

        if not batch_job_ids:
            raise Exception(
                f"Failed to create any batch jobs for prefixes: {failed_prefixes}"
            )

        if failed_prefixes:
            logger.warning(
                f"Some batch jobs failed to create for prefixes: {failed_prefixes}"
            )

        # Store metadata for all batch jobs
        metadata = {
            "batchJobIds": batch_job_ids,  # List of all batch job IDs
            "primaryBatchJobId": batch_job_ids[0],  # Primary job ID for compatibility
            "prefixes": prefixes,
            "maxConcurrentTasks": self.max_concurrent_tasks,
            "resultsBucket": os.environ["RESULTS_BUCKET_NAME"],
            "multipleJobs": True,
            "totalJobs": len(batch_job_ids),
            "completedJobs": 0,
        }

        if ingest_queue_url:
            metadata["ingestQueueUrl"] = ingest_queue_url
            logger.info(f"Added ingest queue URL to job metadata: {ingest_queue_url}")

        if failed_prefixes:
            metadata["failedPrefixes"] = failed_prefixes

        AssetProcessor.update_job_metadata(self.job_id, metadata)

        logger.info(
            f"Successfully created {len(batch_job_ids)} batch jobs: {batch_job_ids}"
        )
        return batch_job_ids[0]  # Return first job ID for compatibility

    def _create_single_batch_job(
        self,
        ingest_queue_url: Optional[str],
        prefix: Optional[str] = None,
        job_suffix: str = "",
        description_suffix: str = "",
    ) -> str:
        """Create a single S3 Batch Operations job"""
        s3control = boto3.client("s3control")
        account_id = boto3.client("sts").get_caller_identity()["Account"]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

        inventory_prefix = f"jobs/{self.job_id}/inventory-{timestamp}{job_suffix}"

        # Build the manifest generator filter
        manifest_filter = {
            "CreatedAfter": "2000-01-01T00:00:00Z",
            "ObjectSizeGreaterThanBytes": 0,
        }

        # Add prefix filtering if a prefix is provided
        if prefix:
            logger.info(f"Applying prefix filter: {prefix}")
            manifest_filter["KeyNameConstraint"] = {
                "MatchAnyPrefix": [prefix]  # Must be exactly 1 element
            }

        # Build the complete job parameters for logging
        job_params = {
            "AccountId": account_id,
            "ConfirmationRequired": False,
            "Operation": {
                "LambdaInvoke": {
                    "FunctionArn": os.environ["PROCESSOR_FUNCTION_ARN"],
                    "InvocationSchemaVersion": "2.0",
                    "UserArguments": {
                        "jobId": self.job_id,
                        "timestamp": timestamp,
                        "environment": os.environ["ENVIRONMENT"],
                    },
                }
            },
            "Report": {
                "Bucket": f"arn:aws:s3:::{os.environ['RESULTS_BUCKET_NAME']}",
                "Prefix": f"jobs/{self.job_id}/reports{job_suffix}",
                "Format": "Report_CSV_20180820",
                "Enabled": True,
                "ReportScope": "AllTasks",
            },
            "ManifestGenerator": {
                "S3JobManifestGenerator": {
                    "SourceBucket": f"arn:aws:s3:::{self.bucket_name}",
                    "EnableManifestOutput": True,
                    "Filter": manifest_filter,
                    "ManifestOutputLocation": {
                        "Bucket": f"arn:aws:s3:::{os.environ['RESULTS_BUCKET_NAME']}",
                        "ManifestPrefix": inventory_prefix,
                        "ManifestFormat": "S3InventoryReport_CSV_20211130",
                        "ManifestEncryption": {"SSES3": {}},
                    },
                }
            },
            "Priority": int(os.environ.get("BATCH_JOB_PRIORITY", "50")),
            "RoleArn": os.environ["BATCH_OPERATIONS_ROLE_ARN"],
            "Description": f"MediaLake asset sync job {self.job_id}{description_suffix}",
            "ClientRequestToken": str(uuid.uuid4()),
            "Tags": [
                {"Key": "Environment", "Value": os.environ["ENVIRONMENT"]},
                {"Key": "ResourcePrefix", "Value": os.environ["RESOURCE_PREFIX"]},
            ],
        }

        # Log the exact job creation parameters
        logger.info(
            f"S3 Batch Operations create_job parameters: {json.dumps(job_params, indent=2, default=str)}"
        )

        response = s3control.create_job(**job_params)

        batch_job_id = response["JobId"]
        logger.info(f"Created Batch Job: {batch_job_id}")

        # For single jobs, also update metadata (multiple jobs handle this separately)
        if not job_suffix:  # This is a single job, not part of multiple
            metadata = {
                "batchJobId": batch_job_id,
                "inventoryPrefix": inventory_prefix,
                "maxConcurrentTasks": self.max_concurrent_tasks,
                "resultsBucket": os.environ["RESULTS_BUCKET_NAME"],
            }

            if ingest_queue_url:
                metadata["ingestQueueUrl"] = ingest_queue_url
                logger.info(
                    f"Added ingest queue URL to job metadata: {ingest_queue_url}"
                )
            else:
                logger.warning(
                    f"No ingest queue URL found for bucket {self.bucket_name}, processor will use fallback"
                )

            if prefix:
                metadata["prefixes"] = [prefix]
                logger.info(f"Added prefix to job metadata: {prefix}")

            AssetProcessor.update_job_metadata(self.job_id, metadata)

        return batch_job_id

    def _handle_single_job_completion(
        self, batch_job_id: str, job_status: str, metadata: dict
    ) -> dict:
        """Handle completion of a single batch job"""
        if job_status == "Complete":
            try:
                inventory_prefix = metadata.get("inventoryPrefix")
                if inventory_prefix:
                    manifest_key = self.process_inventory_manifest(inventory_prefix)
                    AssetProcessor.update_job_status(
                        self.job_id,
                        JobStatus.COMPLETED,
                        f"Successfully processed manifest {manifest_key}",
                    )
                    return {
                        "status": "success",
                        "message": f"Processed manifest {manifest_key}",
                        "batchJobId": batch_job_id,
                    }
                else:
                    AssetProcessor.update_job_status(
                        self.job_id,
                        JobStatus.COMPLETED,
                        "Batch job completed successfully",
                    )
                    return {
                        "status": "success",
                        "message": "Batch job completed",
                        "batchJobId": batch_job_id,
                    }
            except Exception as e:
                logger.error(f"Manifest processing failed: {str(e)}")
                AssetProcessor.update_job_status(
                    self.job_id,
                    JobStatus.FAILED,
                    f"Manifest processing failed: {str(e)}",
                )
                return {
                    "status": "error",
                    "message": str(e),
                    "batchJobId": batch_job_id,
                }

        # Handle failed or cancelled jobs
        status = JobStatus.FAILED if job_status == "Failed" else JobStatus.CANCELLED
        AssetProcessor.update_job_status(
            self.job_id, status, f"Batch job {job_status.lower()}"
        )
        return {"status": job_status.lower(), "batchJobId": batch_job_id}

    def _handle_multi_job_completion(
        self, batch_job_id: str, job_status: str, metadata: dict
    ) -> dict:
        """Handle completion of one job in a multi-job setup"""
        batch_job_ids = metadata.get("batchJobIds", [])
        total_jobs = metadata.get("totalJobs", len(batch_job_ids))
        completed_jobs = metadata.get("completedJobs", 0)

        logger.info(f"Multi-job completion: {batch_job_id} status={job_status}")
        logger.info(f"Progress: {completed_jobs + 1}/{total_jobs} jobs completed")

        # Increment completed jobs count
        completed_jobs += 1

        # Update metadata with completion progress
        updated_metadata = metadata.copy()
        updated_metadata["completedJobs"] = completed_jobs

        # Track failed jobs
        if job_status != "Complete":
            failed_jobs = updated_metadata.get("failedBatchJobs", [])
            failed_jobs.append(batch_job_id)
            updated_metadata["failedBatchJobs"] = failed_jobs

        AssetProcessor.update_job_metadata(self.job_id, updated_metadata)

        # Check if all jobs are completed
        if completed_jobs >= total_jobs:
            failed_jobs = updated_metadata.get("failedBatchJobs", [])
            successful_jobs = total_jobs - len(failed_jobs)

            if failed_jobs:
                AssetProcessor.update_job_status(
                    self.job_id,
                    JobStatus.COMPLETED if successful_jobs > 0 else JobStatus.FAILED,
                    f"Completed: {successful_jobs}/{total_jobs} prefix jobs succeeded, {len(failed_jobs)} failed",
                )
            else:
                AssetProcessor.update_job_status(
                    self.job_id,
                    JobStatus.COMPLETED,
                    f"All {total_jobs} prefix jobs completed successfully",
                )

            return {
                "status": "all_jobs_completed",
                "totalJobs": total_jobs,
                "successfulJobs": successful_jobs,
                "failedJobs": len(failed_jobs),
                "message": f"Multi-prefix job completed: {successful_jobs}/{total_jobs} successful",
            }
        else:
            # Still waiting for more jobs to complete
            return {
                "status": "partial_completion",
                "completedJobs": completed_jobs,
                "totalJobs": total_jobs,
                "currentBatchJobId": batch_job_id,
                "currentJobStatus": job_status,
                "message": f"Job {completed_jobs}/{total_jobs} completed",
            }

    def process_inventory_manifest(self, inventory_prefix: str) -> str:
        """Process generated inventory manifest for chunking"""
        try:
            manifest_response = self.s3_client.list_objects_v2(
                Bucket=self.results_bucket, Prefix=f"{inventory_prefix}/manifest.json"
            )

            if not manifest_response.get("Contents"):
                raise ValueError(f"No inventory manifest found at {inventory_prefix}")

            manifest_key = manifest_response["Contents"][0]["Key"]
            manifest = json.loads(
                self.s3_client.get_object(Bucket=self.results_bucket, Key=manifest_key)[
                    "Body"
                ]
                .read()
                .decode("utf-8")
            )

            if not manifest.get("files"):
                raise ValueError("Inventory manifest contains no files")

            # Process first CSV file in manifest
            csv_file = manifest["files"][0]
            csv_key = csv_file["key"]

            return csv_key

        except Exception as e:
            logger.error(f"Inventory processing failed: {str(e)}")
            raise


@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event, context):
    logger.info(f"Processing event: {json.dumps(event)}")

    try:
        # Handle Batch Job completion event
        if "detail" in event and event.get("source") == "aws.s3control":
            batch_job_id = event["detail"]["jobId"]
            job_status = event["detail"]["status"]

            job = AssetProcessor.get_job_by_batch_id(batch_job_id)
            if not job:
                logger.warning(f"No job found for batch job ID: {batch_job_id}")
                return {"status": "job_not_found", "batchJobId": batch_job_id}

            engine = AssetSyncEngine(job["jobId"], job["bucketName"])

            # Check if this is part of a multi-job setup
            metadata = job.get("metadata", {})
            is_multi_job = metadata.get("multipleJobs", False)

            if is_multi_job:
                return engine._handle_multi_job_completion(
                    batch_job_id, job_status, metadata
                )
            else:
                return engine._handle_single_job_completion(
                    batch_job_id, job_status, metadata
                )

        # Handle direct invocation
        if "jobId" in event and "bucketName" in event:
            engine = AssetSyncEngine(
                event["jobId"],
                event["bucketName"],
                event.get("prefix"),
                event.get("maxConcurrentTasks", 500),
            )

            batch_job_id = engine.create_batch_operations_job()
            return {
                "status": "started",
                "jobId": event["jobId"],
                "batchJobId": batch_job_id,
            }

        # Log unrecognized event and return gracefully instead of raising an error
        logger.warning(f"Unrecognized event format: {json.dumps(event)}")
        return {"status": "skipped", "message": "Unrecognized event format"}

    except Exception as e:
        logger.error(f"Handler failed: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "jobId": event.get("jobId", "unknown"),
        }
