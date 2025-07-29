# High-Throughput Asset Sync System: S3 Batch Operations Architecture

## Overview

The Asset Sync System enables efficient synchronization between S3 buckets and an Asset Management System. It uses S3 Batch Operations to process large numbers of objects (millions+) in a scalable, reliable way. The system automatically determines if objects need ingestion into the Asset Management system and tags them accordingly.

## Key Components

### 1. API Entry Point

- **Storage Sync Post Lambda**: Handles incoming API requests to start synchronization
  - Validates inputs, maps connector IDs to bucket names
  - Creates job records in DynamoDB and triggers the Engine Lambda
  - Supports optional prefix filtering for targeted synchronization

### 2. Core Processing Lambdas

- **Asset Sync Engine Lambda**: Orchestrates the entire process
  - Creates S3 Batch Operations jobs
  - Generates CSV manifests of bucket objects
  - Monitors job progress via EventBridge
  - Splits large manifests into manageable chunks
  - Enqueues chunks for parallel processing
  - Recovers stuck jobs via scheduled checks

- **Asset Sync Processor Lambda**: Performs object processing
  - Handles S3 Batch Operations invocations
  - Processes manifest chunks from SQS
  - Checks if objects exist in Asset Management system
  - Updates object tags and performs S3 copy operations to trigger ingestion
  - Sends events to the ingest event bus

### 3. Infrastructure Components

- **DynamoDB Tables**:
  - Job Table: Tracks overall job status and metadata
  - Chunk Table: Tracks processing of manifest chunks
  - Error Table: Records detailed error information

- **S3 Buckets**:
  - Results Bucket: Stores manifests, chunks, and reports
  - Target Buckets: The S3 buckets being synchronized

- **SQS Queues**:
  - Processor Queue: Holds chunk processing messages
  - Dead Letter Queue: Captures failed processing attempts

- **SNS Topics**:
  - Status Topic: Publishes job status changes

- **IAM Roles**:
  - Batch Operations Role: Permissions for S3 to invoke Lambda
  - Lambda Execution Roles: Permissions for Lambdas to access resources

## Workflow

### Job Initialization:

- API request received with connector ID and optional prefix or prefixes
- System maps connector ID to bucket name
- Job record created in DynamoDB with INITIALIZING status
- Engine Lambda invoked with job details

### Manifest Generation:

- Engine Lambda lists objects from bucket/prefix
- Creates CSV manifest file in results bucket
- Updates job status to DISCOVERING

### S3 Batch Operations:

- Engine Lambda creates S3 Batch Operations job using manifest
- Batch job executes across potentially millions of objects
- EventBridge monitors batch job status changes
- When complete, manifest is split into chunks

### Chunk Processing:

- Chunks are enqueued to SQS for parallel processing
- Processor Lambda reads chunks and processes objects
- Updates job status to PROCESSING
- Checks if objects need to be processed:
  - If asset ID exists in system: Skip
  - If inventory ID exists but asset ID doesn't: COPY action
  - If neither exists: PUT action

### Object Processing:

- Updates object tags (AssetID, InventoryID, etc.)
- Performs S3 copy operation to trigger event-based ingestion
- Sends events to ingest event bus for further processing
- Updates job counters for processed objects

### Job Completion:

- When all chunks processed, job status updated to COMPLETED
- Final statistics recorded in job record

## Error Handling

- Comprehensive exception handling in all Lambdas
- Detailed error logging to CloudWatch Logs
- Error records stored in Error Table with:
  - Error type classification
  - Error messages and stack traces
  - Object keys and job IDs for correlation
- Dead Letter Queue for failed SQS messages
- Automatic recovery of stuck jobs via scheduled checks

## Key Optimizations

### S3 Batch Operations:

- Uses AWS's managed batch processing for listing and handling objects
- Highly scalable and reliable for millions of objects
- Native retries and error handling

### Chunking Strategy:

- Large manifests split into manageable chunks
- Allows parallel processing across multiple Lambda invocations
- Improves reliability through smaller work units

### Dynamic Batch Sizing:

- Adjusts batch sizes based on object sizes and counts
- Optimizes Lambda execution time and memory usage

### Retry Logic:

- Exponential backoff for transient errors
- Detailed failure tracking for debugging

### State Management:

- Uses DynamoDB for reliable state tracking
- Supports job recovery and progress monitoring

## Implementation Details

### Critical Fields and Parameters

- **User Arguments in S3 Batch Operations**:
  - Must be string-to-string map format
  - Contains job ID and timestamp for correlation

- **Manifest Format**:
  - CSV with bucket, key, size, lastModified
  - Required specific format for S3 Batch Operations

- **S3 Batch Response Format**:
  - Must include invocationSchemaVersion, treatMissingKeysAs, and results
  - Each result needs taskId, resultCode, and resultString

### Environment Variables

- `JOB_TABLE_NAME`: DynamoDB table for job records
- `CHUNK_TABLE_NAME`: DynamoDB table for chunk tracking
- `ERROR_TABLE_NAME`: DynamoDB table for error records
- `ASSETS_TABLE_NAME`: DynamoDB table for asset management
- `RESULTS_BUCKET_NAME`: S3 bucket for manifests and reports
- `PROCESSOR_QUEUE_URL`: SQS queue URL for chunk processing
- `PROCESSOR_FUNCTION_ARN`: ARN of processor Lambda
- `ENGINE_FUNCTION_ARN`: ARN of engine Lambda
- `BATCH_OPERATIONS_ROLE_ARN`: ARN of S3 batch operations role
- `STATUS_TOPIC_ARN`: SNS topic ARN for status notifications
- `INGEST_EVENT_BUS_NAME`: EventBridge bus for ingest events

## Monitoring and Troubleshooting

### CloudWatch Logs:

- Detailed logging at each processing step
- Structured log format with Lambda context

### CloudWatch Metrics:

- Custom metrics for object counts, processing rates, errors
- Alarm configuration for error thresholds

### S3 Batch Operations Console:

- Monitor batch job status
- Review completion reports

### DynamoDB Tables:

- Check job status and metadata
- Review error records for troubleshooting

### Common Issues:

- **Permissions**: Check IAM roles for S3, Lambda, DynamoDB access
- **Timeouts**: Adjust Lambda timeouts for large operations
- **Memory**: Increase Lambda memory for faster processing

## Scaling Considerations

System handles millions of objects through:

- S3 Batch Operations for initial processing
- Chunked parallel processing for detailed work
- SQS queues for load leveling
- DynamoDB for scalable state storage

### Concurrency Management:

- Lambda concurrency limits control parallel processing
- SQS visibility timeout prevents duplicate processing
- S3 Batch Operations handles its own concurrency optimization

This architecture provides a highly scalable, reliable solution for synchronizing S3 objects with an asset management system while efficiently handling large-scale operations.
