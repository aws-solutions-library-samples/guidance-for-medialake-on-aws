# Title Embeddings Lambda

This Lambda function processes JSON files from an S3 bucket, generates embeddings using Amazon Bedrock's Titan model, and stores them in OpenSearch.

## Setup Requirements

1. Environment Variables:
   - OPENSEARCH_ENDPOINT: Your OpenSearch domain endpoint
   - AWS_REGION: AWS region (defaults to us-east-1)

2. IAM Permissions:
   - s3:GetObject for the wbd-title-poc bucket
   - bedrock:InvokeModel for the Titan embedding model
   - es:ESHttp* for OpenSearch access

3. Dependencies:
   - See requirements.txt for Python package dependencies

## Deployment

1. Create a Lambda layer with the requirements:
```bash
pip install -r requirements.txt -t python/
zip -r layer.zip python/
```

2. Create the Lambda function with:
   - Runtime: Python 3.9+
   - Handler: index.lambda_handler
   - Memory: 256MB (minimum)
   - Timeout: 30 seconds
   - Layer: Upload and attach the created layer

3. Configure S3 trigger:
   - Bucket: wbd-title-poc
   - Event type: All object create events

## Input JSON Format

The Lambda expects JSON files with at least a 'text' field:
```json
{
    "text": "Content to embed",
    "metadata": {
        // Optional additional metadata
    }
}
```

## Output

The function stores documents in OpenSearch with the following structure:
```json
{
    "text": "Original text content",
    "embedding": [...], // Vector embedding from Bedrock
    "source_file": "s3_key.json",
    "metadata": {
        // Any additional metadata from source file
    }
}
