# Asset Sync Worker Lambda

This Lambda function processes SQS messages for asset synchronization, handling existing asset IDs and creating DynamoDB entries with technical metadata.

## Features

- Processes batches of assets from SQS messages
- Handles existing AssetID and InventoryID tags:
  - If both exist: Uses existing IDs
  - If only AssetID exists: Creates new InventoryID
  - If only InventoryID exists: Creates new AssetID
  - If neither exists: Creates both new IDs
- Extracts technical metadata from file headers without downloading entire files:
  - Images: dimensions, format, color mode
  - Videos: dimensions, codec, duration, frame rate, bitrate
  - Audio: duration, bitrate, channels, sample rate
- Calculates MD5 hash for file identification
- Creates DynamoDB entries with metadata
- Tags S3 objects with IDs
- Publishes events to EventBridge with technical metadata
- Uses AWS Lambda Powertools V3 for observability

## AWS Lambda Powertools V3 Features

- **Event Source Data Classes**: Automatic parsing of SQS events
- **Structured Logging**: Consistent, searchable logs with context
- **Tracing**: X-Ray integration with custom annotations and metadata
- **Metrics**: Custom CloudWatch metrics for monitoring
- **Error Handling**: Robust error handling with proper context

## Dependencies

The Lambda requires the following dependencies:

- `aws-lambda-powertools>=3.0.0`: For logging, tracing, metrics, and event parsing
- `boto3>=1.26.0`: For AWS service interactions
- `python-magic>=0.4.27`: For file type detection
- `Pillow>=9.4.0`: For image metadata extraction
- `ffmpeg-python>=0.2.0`: For video metadata extraction
- `mutagen>=1.46.0`: For audio metadata extraction

## Environment Variables

- `ASSETS_TABLE_NAME`: DynamoDB table name for asset storage
- `JOBS_TABLE_NAME`: DynamoDB table name for job tracking
- `EVENT_BUS_NAME`: EventBridge bus name for publishing events
- `POWERTOOLS_SERVICE_NAME`: Service name for Powertools (default: "asset-sync-worker")
- `POWERTOOLS_METRICS_NAMESPACE`: Metrics namespace (default: "AssetSync")

## Usage

The Lambda is triggered by SQS messages with the following structure:

```json
{
  "jobId": "job-123",
  "bucketName": "my-bucket",
  "objects": [
    {
      "key": "path/to/object.jpg",
      "assetId": "asset:img:123",  // Optional
      "inventoryId": "asset:uuid:456"  // Optional
    }
  ],
  "batchNumber": 1,
  "totalBatches": 10
}
```

The Lambda processes each object, checking for existing tags, extracting technical metadata, and creating DynamoDB entries accordingly.

## Metadata Extraction

The Lambda extracts metadata by reading only the file headers, which is more efficient than downloading entire files:

1. For all files:
   - Reads the first 8KB to detect file type using python-magic
   - Extracts basic metadata like MIME type and file extension

2. For images:
   - Uses Pillow to extract dimensions, format, and color mode

3. For videos:
   - Uses ffmpeg to extract dimensions, codec, duration, frame rate, and bitrate
   - Also extracts audio stream information if available

4. For audio:
   - Uses mutagen to extract duration, bitrate, channels, and sample rate
   - Also extracts audio tags if available

If metadata extraction fails with the initial 8KB, the Lambda will attempt to read the first 1MB for more complete metadata. 