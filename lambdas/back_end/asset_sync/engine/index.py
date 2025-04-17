import os
import json
import boto3
import uuid
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

from common import AssetProcessor, JobStatus

logger = Logger()
tracer = Tracer()
metrics = Metrics()

class AssetSyncEngine:
    """Handles S3 asset synchronization using S3 Batch Operations"""
    
    def __init__(self, job_id: str, bucket_name: str, prefix: Optional[str] = None, max_concurrent_tasks: int = 500):
        self.job_id = job_id
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.max_concurrent_tasks = max_concurrent_tasks
        self.s3_client = boto3.client('s3')
        self.results_bucket = os.environ['RESULTS_BUCKET_NAME']

    def create_batch_operations_job(self) -> str:
        """Create and start an S3 Batch Operations job with manifest generation"""
        AssetProcessor.update_job_status(
            self.job_id,
            JobStatus.DISCOVERING,
            f"Initiating inventory generation for {self.bucket_name}"
        )

        try:
            s3control = boto3.client('s3control')
            account_id = boto3.client('sts').get_caller_identity()['Account']
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')

            inventory_prefix = f"jobs/{self.job_id}/inventory-{timestamp}"

            response = s3control.create_job(
                AccountId=account_id,
                ConfirmationRequired=False,
                Operation={
                    'LambdaInvoke': {
                        'FunctionArn': os.environ['PROCESSOR_FUNCTION_ARN'],
                        'InvocationSchemaVersion': '2.0',
                        'UserArguments': {
                            'jobId': self.job_id,
                            'timestamp': timestamp,
                            'environment': os.environ['ENVIRONMENT']
                        }
                    }
                },
                Report={
                    'Bucket': f"arn:aws:s3:::{os.environ['RESULTS_BUCKET_NAME']}",
                    'Prefix': f"jobs/{self.job_id}/reports",
                    'Format': 'Report_CSV_20180820',
                    'Enabled': True,
                    'ReportScope': 'AllTasks'
                },
                ManifestGenerator={
                    'S3JobManifestGenerator': {
                        'SourceBucket': f"arn:aws:s3:::{self.bucket_name}",
                        'EnableManifestOutput': True,
                        'Filter': {
                            # CORRECTED FILTER PARAMETERS
                            'CreatedAfter': '2000-01-01T00:00:00Z',
                            'ObjectSizeGreaterThanBytes': 0
                        },
                        'ManifestOutputLocation': {
                            'Bucket': f"arn:aws:s3:::{os.environ['RESULTS_BUCKET_NAME']}",
                            'ManifestPrefix': inventory_prefix,
                            'ManifestFormat': 'S3InventoryReport_CSV_20211130',
                            'ManifestEncryption': {
                                'SSES3': {}
                            }
                        }
                    }
                },
                Priority=int(os.environ.get('BATCH_JOB_PRIORITY', '50')),
                RoleArn=os.environ['BATCH_OPERATIONS_ROLE_ARN'],
                Description=f"MediaLake asset sync job {self.job_id}",
                ClientRequestToken=str(uuid.uuid4()),
                Tags=[
                    {
                        'Key': 'Environment',
                        'Value': os.environ['ENVIRONMENT']
                    },
                    {
                        'Key': 'ResourcePrefix',
                        'Value': os.environ['RESOURCE_PREFIX']
                    }
                ]
            )

            batch_job_id = response['JobId']
            logger.info(f"Created Batch Job: {batch_job_id}")

            AssetProcessor.update_job_metadata(self.job_id, {
                'batchJobId': batch_job_id,
                'inventoryPrefix': inventory_prefix,
                'maxConcurrentTasks': self.max_concurrent_tasks,
                'resultsBucket': os.environ['RESULTS_BUCKET_NAME']
            })

            s3control.update_job_status(
                AccountId=account_id,
                JobId=batch_job_id,
                RequestedJobStatus='Ready'
            )

            return batch_job_id

        except Exception as e:
            logger.error(f"Batch job creation failed: {str(e)}", exc_info=True)
            AssetProcessor.update_job_status(
                self.job_id,
                JobStatus.FAILED,
                f"Batch job creation failed: {str(e)}"
            )
            raise

    def process_inventory_manifest(self, inventory_prefix: str) -> str:
        """Process generated inventory manifest for chunking"""
        try:
            manifest_response = self.s3_client.list_objects_v2(
                Bucket=self.results_bucket,
                Prefix=f"{inventory_prefix}/manifest.json"
            )
            
            if not manifest_response.get('Contents'):
                raise ValueError(f"No inventory manifest found at {inventory_prefix}")

            manifest_key = manifest_response['Contents'][0]['Key']
            manifest = json.loads(self.s3_client.get_object(
                Bucket=self.results_bucket,
                Key=manifest_key
            )['Body'].read().decode('utf-8'))

            if not manifest.get('files'):
                raise ValueError("Inventory manifest contains no files")

            # Process first CSV file in manifest
            csv_file = manifest['files'][0]
            csv_key = csv_file['key']
            
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
        if 'detail' in event and event.get('source') == 'aws.s3control':
            batch_job_id = event['detail']['jobId']
            job_status = event['detail']['status']
            
            job = AssetProcessor.get_job_by_batch_id(batch_job_id)
            engine = AssetSyncEngine(job['jobId'], job['bucketName'])
            
            if job_status == 'Complete':
                try:
                    manifest_key = engine.process_inventory_manifest(
                        job['metadata']['inventoryPrefix']
                    )
                    return {
                        "status": "success",
                        "message": f"Processed manifest {manifest_key}"
                    }
                except Exception as e:
                    logger.error(f"Manifest processing failed: {str(e)}")
                    AssetProcessor.update_job_status(
                        job['jobId'],
                        JobStatus.FAILED,
                        f"Manifest processing failed: {str(e)}"
                    )
                    raise
            
            AssetProcessor.update_job_status(
                job['jobId'],
                JobStatus.FAILED if job_status == 'Failed' else JobStatus.CANCELLED,
                f"Batch job {job_status.lower()}"
            )
            return {"status": job_status.lower()}
        
        # Handle direct invocation
        if 'jobId' in event and 'bucketName' in event:
            engine = AssetSyncEngine(
                event['jobId'],
                event['bucketName'],
                event.get('prefix'),
                event.get('maxConcurrentTasks', 500)
            )
            
            batch_job_id = engine.create_batch_operations_job()
            return {
                "status": "started",
                "jobId": event['jobId'],
                "batchJobId": batch_job_id
            }
        
        raise ValueError("Unrecognized event format")

    except Exception as e:
        logger.error(f"Handler failed: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "jobId": event.get('jobId', 'unknown')
        }
