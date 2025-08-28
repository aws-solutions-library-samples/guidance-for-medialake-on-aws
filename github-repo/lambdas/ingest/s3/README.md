# S3 Asset Processor Lambda

This Lambda function processes assets uploaded to S3, extracts metadata, and creates entries in DynamoDB.

## Features

- Detects file type from file headers without downloading the entire file
- Extracts technical metadata for different file types:
  - Images: dimensions, format, color mode
  - Videos: dimensions, codec, duration, frame rate, bitrate
  - Audio: duration, bitrate, channels, sample rate
- Creates DynamoDB entries with extracted metadata
- Publishes events to EventBridge for downstream processing
- Handles duplicate file detection
- Uses AWS Lambda Powertools V3 for observability and best practices

## AWS Lambda Powertools V3 Features

- **Event Source Data Classes**: Automatic parsing and validation of S3 events
- **Schema Validation**: JSON Schema validation for incoming events
- **Structured Logging**: Consistent, searchable logs with context
- **Tracing**: X-Ray integration with custom annotations and metadata
- **Metrics**: Custom CloudWatch metrics for monitoring
- **Error Handling**: Robust error handling with proper context

## Dependencies

The Lambda requires the following dependencies:

- `aws-lambda-powertools>=3.0.0`: For logging, tracing, metrics, and event parsing
- `python-magic`: For file type detection
- `Pillow`: For image metadata extraction
- `ffmpeg-python`: For video metadata extraction
- `mutagen`: For audio metadata extraction

## Environment Variables

- `DYNAMODB_TABLE`: DynamoDB table name for asset storage
- `EVENT_BUS_NAME`: EventBridge bus name for publishing events
- `POWERTOOLS_SERVICE_NAME`: Service name for Powertools (default: "asset-processor")
- `POWERTOOLS_METRICS_NAMESPACE`: Metrics namespace (default: "AssetProcessing")

## Deployment

This Lambda should be deployed with a Lambda Layer containing the dependencies listed in `requirements.txt`.

For the `python-magic` library to work correctly, the Lambda Layer should also include the libmagic shared libraries.

## Usage

The Lambda is triggered by S3 events (ObjectCreated, ObjectRemoved) and processes the files accordingly.

For file uploads, it:

1. Extracts metadata from file headers
2. Checks for duplicates
3. Creates DynamoDB entries
4. Tags S3 objects
5. Publishes events

For file deletions, it:

1. Removes DynamoDB entries
2. Publishes deletion events
