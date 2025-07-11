# Vector Processing Scripts

This directory contains two scripts for processing embedding vectors from S3 JSON files and pushing them to OpenSearch for semantic search capabilities.

## Scripts Overview

### 1. Python Script (`process_vectors_from_s3.py`)
A comprehensive Python script that provides robust error handling, logging, and AWS SDK integration.

### 2. Bash Script (`process_vectors_s3.sh`)
A lightweight bash script using AWS CLI and jq for basic JSON processing.

## Data Model

The scripts expect a JSON file with the following structure:

```json
[
  {
    "key": "video_name_start-end_embedding_option",
    "vector": [0.1, 0.2, 0.3, ...],
    "metadata": {
      "video_path": "/path/to/video.mp4",
      "start_time": 10.5,
      "end_time": 20.0,
      "embeddingOption": "default"
    }
  }
]
```

## Usage

### Python Script

#### Prerequisites
```bash
pip install -r requirements.txt
```

#### Basic Usage
```bash
python process_vectors_from_s3.py \
  --bucket my-bucket \
  --key embeddings/video1.json \
  --video-name video1 \
  --video-path /path/to/video1.mp4 \
  --opensearch-endpoint https://search-domain.us-east-1.es.amazonaws.com
```

#### Full Options
```bash
python process_vectors_from_s3.py \
  --bucket my-bucket \
  --key embeddings/video1.json \
  --video-name video1 \
  --video-path /path/to/video1.mp4 \
  --opensearch-endpoint https://search-domain.us-east-1.es.amazonaws.com \
  --index-name media \
  --aws-region us-east-1
```

### Bash Script

#### Prerequisites
- AWS CLI v2
- jq (JSON processor)
- curl
- bc (basic calculator)

#### Installation on macOS
```bash
brew install awscli jq curl bc
```

#### Installation on Ubuntu/Debian
```bash
sudo apt-get install awscli jq curl bc
```

#### Basic Usage
```bash
./process_vectors_s3.sh \
  my-bucket \
  embeddings/video1.json \
  video1 \
  /path/to/video1.mp4 \
  https://search-domain.us-east-1.es.amazonaws.com
```

#### Full Options
```bash
./process_vectors_s3.sh \
  my-bucket \
  embeddings/video1.json \
  video1 \
  /path/to/video1.mp4 \
  https://search-domain.us-east-1.es.amazonaws.com \
  media \
  us-east-1
```

## AWS Configuration

Both scripts require AWS credentials to be configured. You can set them up using:

```bash
aws configure
```

Or by setting environment variables:
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

## OpenSearch Document Structure

The scripts create OpenSearch documents with the following structure:

```json
{
  "type": "video",
  "document_id": "video_name_start-end_embedding_option",
  "embedding": [0.1, 0.2, 0.3, ...],
  "embedding_scope": "clip",
  "embedding_option": "default",
  "start_timecode": "00:00:10:15",
  "end_timecode": "00:00:20:00",
  "timestamp": "2024-01-01T12:00:00.000Z",
  "DigitalSourceAsset": {
    "ID": "asset:vid:video_name",
    "Type": "video"
  },
  "video_path": "/path/to/video.mp4",
  "start_time_sec": 10.5,
  "end_time_sec": 20.0
}
```

## Error Handling

### Python Script
- Comprehensive logging with AWS Lambda Powertools
- Graceful error handling for individual records
- Detailed progress reporting
- Returns exit codes based on success/failure

### Bash Script
- Basic error checking and validation
- Progress updates every 100 records
- Cleanup of temporary files
- Exit codes for automation integration

## Performance Considerations

- **Python Script**: Better for large datasets due to efficient boto3 SDK
- **Bash Script**: Lighter weight but may be slower for very large files
- Both scripts process records sequentially to avoid overwhelming OpenSearch

## Troubleshooting

### Common Issues

1. **AWS Credentials**: Ensure AWS credentials are properly configured
2. **OpenSearch Permissions**: Verify IAM permissions for OpenSearch access
3. **Network Connectivity**: Check VPC/security group settings if using VPC
4. **Index Existence**: Ensure the target OpenSearch index exists

### Debugging

For the Python script, set log level to DEBUG:
```bash
export AWS_LAMBDA_LOG_LEVEL=DEBUG
```

For the bash script, add debugging:
```bash
set -x  # Add at the top of the script for verbose output
```

## Integration with MediaLake

These scripts are designed to work with the MediaLake architecture:
- Follow MediaLake's vector storage patterns
- Use compatible document schemas
- Support MediaLake's SMPTE timecode format
- Integrate with existing OpenSearch indexes

## License

This project follows the same license as the MediaLake project. 