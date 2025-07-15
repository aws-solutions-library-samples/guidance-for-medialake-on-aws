# Create S3 Vector Index Lambda Function

This Lambda function creates S3 Vector buckets and indexes using the private boto3 SDK for S3 Vectors.

## Overview

This function is adapted from the `create_os_index` function but uses S3 Vector APIs instead of OpenSearch. It:

1. Creates an S3 Vector bucket if it doesn't exist
2. Creates one or more vector indexes within that bucket
3. Handles retry logic with exponential backoff
4. Supports index recreation (deletes existing index before creating new one)

## Environment Variables

- `VECTOR_BUCKET_NAME`: Name of the S3 Vector bucket to create
- `INDEX_NAMES`: Comma-separated list of index names to create
- `REGION`: AWS region for the S3 Vector service
- `VECTOR_DIMENSION`: Dimension of the vectors (default: 1024, max: 4096)

## Dependencies

This function requires the `CustomBoto3Layer` from `medialake_constructs/shared_constructs/lambda_layers.py` which contains the private boto3 SDK with S3 Vector support.

## Key Differences from OpenSearch Version

1. **Service Client**: Uses `s3vectors` client instead of direct HTTP requests
2. **Bucket Creation**: Creates S3 Vector bucket before creating indexes
3. **API Calls**: Uses boto3 SDK methods instead of REST API calls
4. **Error Handling**: Adapted for S3 Vector specific exceptions
5. **Configuration**: Simplified configuration without complex mappings

## S3 Vector API Usage

- `CreateVectorBucket`: Creates the vector bucket with encryption
- `GetVectorBucket`: Checks if bucket exists
- `CreateIndex`: Creates vector index with specified dimension
- `GetIndex`: Checks if index exists
- `DeleteIndex`: Deletes existing index

## Usage in CDK

When deploying this Lambda function, ensure you:

1. Include the `CustomBoto3Layer` in the Lambda function layers
2. Set appropriate environment variables
3. Grant necessary IAM permissions for S3 Vector operations

Example CDK usage:
```python
from medialake_constructs.shared_constructs.lambda_layers import CustomBoto3Layer

# Create the custom boto3 layer
custom_boto3_layer = CustomBoto3Layer(self, "CustomBoto3Layer")

# Create Lambda function with the layer
lambda_function = lambda_.Function(
    self,
    "CreateS3VectorIndex",
    runtime=lambda_.Runtime.PYTHON_3_12,
    handler="index.handler",
