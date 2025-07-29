# Creating New Nodes in MediaLake

This guide explains how to create new processing nodes in the MediaLake system, using the video splitter node as an example.

## Overview

MediaLake nodes are modular processing units that can be connected together to form pipelines. Each node performs a specific operation on media assets and can pass data to subsequent nodes in the pipeline.

## Node Components

A complete node consists of three main components:

1. **Node Template (YAML)** - Defines the node's metadata, configuration, and interface
2. **Lambda Implementation** - Contains the actual processing logic
3. **CDK Deployment Configuration** - Registers the node in the infrastructure stack

## Step-by-Step Guide

### 1. Create the Node Template (YAML)

Node templates are stored in [`s3_bucket_assets/pipeline_nodes/node_templates/`](../../s3_bucket_assets/pipeline_nodes/node_templates/) and organized by category:

- `utility/` - General processing nodes
- `integration/` - Third-party service integrations
- `trigger/` - Event-triggered nodes
- `flow/` - Control flow nodes

**Example: [`video_splitter.yaml`](../../s3_bucket_assets/pipeline_nodes/node_templates/utility/video_splitter.yaml)**

```yaml
spec: v1.0.0
node:
  id: video_splitter # Unique identifier
  title: Video Splitter # Display name
  description: Splits video files into MP4 chunks of configurable duration
  version: 1.0.0
  type: utility # Category: utility, integration, trigger, flow
  integration:
    config:
      lambda:
        handler: utility/VideoSplitterLambdaDeployment # References CDK deployment
        runtime: python3.12
        layers: # Required Lambda layers
          - FFmpeg
        iam_policy: # IAM permissions
          statements:
            - effect: Allow
              actions:
                - s3:ListBucket
                - s3:GetObject
                - s3:PutObject
              resources:
                - arn:aws:s3:::${MEDIA_ASSETS_BUCKET_NAME}/*
                - arn:aws:s3:::${MEDIA_ASSETS_BUCKET_NAME}
            - effect: Allow
              actions:
                - kms:Decrypt
              resources:
                - ${MEDIA_ASSETS_BUCKET_ARN_KMS_KEY}
            - effect: Allow
              actions:
                - kms:GenerateDataKey
              resources:
                - "*"

actions:
  split: # Action identifier
    summary: Video Splitter
    description: Splits video files into MP4 chunks of configurable duration
    operationId: videoSplitter
    parameters: # User-configurable parameters
      - in: body
        name: Chunk Duration
        required: true
        default: 7200 # 2 hours in seconds
        schema:
          type: number
    connections: # Data flow specifications
      incoming:
        type: [video] # Accepts video inputs
      outgoing:
        type: [video] # Outputs video data
```

#### Key YAML Sections:

- **`node.id`**: Must be unique across all nodes
- **`integration.config.lambda.handler`**: Must match the CDK deployment name
- **`integration.config.lambda.layers`**: Specify required Lambda layers (FFmpeg, PyMediaInfo, etc.)
- **`iam_policy`**: Define minimum required permissions
- **`actions`**: Define the operations this node can perform
- **`parameters`**: User-configurable settings with defaults
- **`connections`**: Specify input/output data types (audio, video, image, text)

### 2. Create the Lambda Implementation

Lambda implementations are stored in [`lambdas/nodes/`](../../lambdas/nodes/) with each node having its own directory.

**Directory Structure:**

```
lambdas/nodes/video_splitter/
├── index.py           # Main Lambda handler
└── requirements.txt   # Python dependencies (if needed)
```

**Example: [`index.py`](../../lambdas/nodes/video_splitter/index.py)**

```python
"""
Video Splitter Lambda
────────────────────
• Splits an input video file into MP4 chunks of configurable duration
• Uploads each chunk to S3 and returns their metadata.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Tracer
from lambda_middleware import lambda_middleware

# Powertools setup
logger = Logger()
tracer = Tracer()
s3_client = boto3.client("s3")

@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context) -> Any:
    try:
        logger.info("Incoming event", extra={"event": event})

        # Extract payload data
        payload = event.get("payload", {})
        data = payload.get("data", {})
        assets = payload.get("assets", [])

        # Process the media asset
        # ... implementation logic ...

        # Return processed results
        return processed_chunks

    except Exception as exc:
        logger.exception("Unhandled exception")
        return {"statusCode": 500, "body": json.dumps({"error": str(exc)})}
```

#### Lambda Implementation Guidelines:

1. **Use Powertools**: Always include `@logger.inject_lambda_context` and `@tracer.capture_lambda_handler`
2. **Use Middleware**: Apply `@lambda_middleware` for event bus integration
3. **Error Handling**: Wrap main logic in try/catch with proper error responses
4. **Logging**: Use structured logging with the Logger instance
5. **Input Validation**: Validate all input parameters and provide meaningful error messages
6. **Output Format**: Return data in the expected format for downstream nodes

#### Common Patterns:

**Extracting Asset Information:**

```python
try:
    inventory_id = assets[0]["InventoryID"]
    asset_id = assets[0]["DigitalSourceAsset"]["ID"]
except Exception:
    return _bad_request("Could not locate InventoryID or DigitalSourceAsset ID")
```

**Handling Parameters:**

```python
raw = os.getenv("CHUNK_DURATION") or str(data.get("chunkDuration", "7200"))
try:
    chunk_duration = int(raw)
except ValueError:
    chunk_duration = 7200
    logger.warning("Invalid CHUNK_DURATION – defaulting to 7200 s")
```

**S3 Operations:**

```python
# Download
s3_client.download_file(source_bucket, source_key, local_path)

# Upload
s3_client.upload_file(local_path, upload_bucket, upload_key)
```

### 3. Register in CDK Stack

Add the Lambda deployment to [`medialake_stacks/nodes_stack.py`](../../medialake_stacks/nodes_stack.py):

```python
self.video_splitter_lambda_deployment = LambdaDeployment(
    self,
    "VideoSplitterLambdaDeployment",        # Must match YAML handler name
    destination_bucket=props.iac_bucket.bucket,
    parent_folder="nodes/utility",
    code_path=["lambdas", "nodes", "video_splitter"],  # Path to implementation
)
```

#### CDK Registration Guidelines:

1. **Naming**: The construct ID must match the `handler` field in the YAML template
2. **Parent Folder**: Should match the node category (`nodes/utility`, `nodes/integration`, etc.)
3. **Code Path**: Array pointing to the Lambda implementation directory
4. **Placement**: Add in alphabetical order with other similar deployments

### 4. Dependencies and Layers

#### Available Lambda Layers:

The following Lambda layers are available in MediaLake for use in your nodes (defined in [`medialake_constructs/shared_constructs/lambda_layers.py`](../../medialake_constructs/shared_constructs/lambda_layers.py)):

##### Media Processing Layers:

- **`FFmpeg`**: Complete FFmpeg binary for video/audio processing and conversion
- **`FFProbe`**: FFprobe binary for media metadata extraction and analysis
- **`PyMediaInfo`**: Python library for extracting media file metadata
- **`ResvgCliLayer`**: SVG to PNG conversion using the resvg CLI tool

##### Utility Layers:

- **`PowertoolsLayer`**: AWS Lambda Powertools for Python (logging, tracing, metrics)
- **`CommonLibrariesLayer`**: Shared utility libraries and helper functions for MediaLake (automatically added to all nodes)
- **`ShortuuidLayer`**: Short UUID generation library
- **`PyamlLayer`**: YAML processing and parsing library
- **`ZipmergeLayer`**: Static zipmerge binary for ZIP file operations

##### Integration Layers:

- **`JinjaLambdaLayer`**: Jinja2 templating engine
- **`OpenSearchPyLayer`**: OpenSearch Python client library
- **`PynamoDbLambdaLayer`**: PynamoDB library for DynamoDB operations
- **`SearchLayer`**: Search functionality and utilities
- **`IngestMediaProcessorLayer`**: Media container analysis and processing utilities

##### CommonLibraries Layer (Automatically Included):

The `CommonLibrariesLayer` is automatically added to all MediaLake nodes and contains shared utility modules from [`lambdas/common_libraries/`](../../lambdas/common_libraries/):

- **`lambda_error_handler.py`**: Comprehensive error handling utilities with custom exception classes, response validation, and standardized error formatting
- **`lambda_middleware.py`**: Event normalization middleware that standardizes incoming events into consistent `{metadata, payload}` format and handles S3 payload offloading
- **`lambda_utils.py`**: Common Lambda utilities including decorators for tracing/metrics, input validation, CORS handling, and business metrics
- **`nodes_utils.py`**: Node-specific utilities for time formatting (SMPTE timecode conversion, duration formatting)

These utilities are available in all node implementations without needing to specify them in the layers configuration.

##### Usage in Node Templates:

To use additional layers in your node template, specify them in the `layers` section:

```yaml
integration:
  config:
    lambda:
      handler: utility/YourNodeLambdaDeployment
      runtime: python3.12
      layers:
        - FFmpeg # For video/audio processing
        - PyMediaInfo # For metadata extraction
        # CommonLibraries is automatically included - don't specify it
```

**Note**:

- Layer names in YAML should match the class names without the "Layer" suffix (e.g., `FFmpeg` not `FFmpegLayer`)
- `CommonLibraries` is automatically added to all nodes and should NOT be specified in the layers list

### Creating New Lambda Layers

If you need to create a new Lambda layer for additional dependencies or tools:

#### 1. Create Layer Directory Structure

Create a new directory under [`lambdas/layers/`](../../lambdas/layers/):

```
lambdas/layers/your_layer_name/
├── requirements.txt    # Python dependencies
└── README.md          # Layer documentation
```

#### 2. Define Layer Class

Add a new layer class in [`medialake_constructs/shared_constructs/lambda_layers.py`](../../medialake_constructs/shared_constructs/lambda_layers.py):

```python
class YourLayerNameLayer(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the Lambda layer
        self.layer = LambdaLayer(
            self,
            "YourLayerNameLayer",
            config=LambdaLayerConfig(
                entry="lambdas/layers/your_layer_name",
                description="A Lambda layer with your custom libraries",
            ),
        )
```

#### 3. Register Layer in Nodes Stack

Add the layer to [`medialake_stacks/nodes_stack.py`](../../medialake_stacks/nodes_stack.py):

```python
# Create Lambda Layers
self.your_layer_name_layer = YourLayerNameLayer(self, "YourLayerNameLayer")

# Add to environment variables for automatic attachment
environment_variables={
    # ... other variables ...
    "YOUR_LAYER_NAME_LAYER_ARN": self.your_layer_name_layer.layer.layer_version_arn,
}
```

#### 4. Use in Node Templates

Reference the new layer in your node YAML:

```yaml
integration:
  config:
    lambda:
      layers:
        - YourLayerName
```

#### Layer Types:

- **Python Package Layers**: Use `LambdaLayer` with `requirements.txt`
- **Binary Layers**: Use custom `lambda_.LayerVersion` with Docker bundling
- **Pre-built Layers**: Reference existing AWS or third-party layer ARNs

#### Requirements File:

Create [`requirements.txt`](../../lambdas/nodes/video_splitter/requirements.txt) for additional Python dependencies:

```txt
requests
aws-lambda-powertools
aws-xray-sdk
```

**Note**: Common dependencies like `boto3`, `aws-lambda-powertools` are often available in layers.

## Testing Your Node

### 1. Deploy the Infrastructure

```bash
cdk deploy MediaLakeNodesStack
```

### 2. Test Event Structure

Nodes receive events in this format:

```json
{
  "payload": {
    "data": {
      "chunkDuration": 7200,
      "presignedUrl": "https://...",
      "bucket": "media-bucket",
      "key": "path/to/video.mp4"
    },
    "assets": [
      {
        "InventoryID": "asset-123",
        "DigitalSourceAsset": {
          "ID": "source-456"
        },
        "DerivedRepresentations": [...]
      }
    ]
  }
}
```

### 3. Expected Output Format

Nodes should return data that can be consumed by downstream nodes:

```json
[
  {
    "bucket": "media-bucket",
    "key": "chunks/source-456/video_segment_001.mp4",
    "url": "s3://media-bucket/chunks/source-456/video_segment_001.mp4",
    "index": 1,
    "start_time": 0,
    "end_time": 7200,
    "duration": 7200,
    "mediaType": "Video",
    "asset_id": "source-456",
    "inventory_id": "asset-123"
  }
]
```

## Best Practices

### 1. Error Handling

- Always validate input parameters
- Provide meaningful error messages
- Use appropriate HTTP status codes
- Log errors with sufficient context

### 2. Performance

- Use temporary directories (`/tmp/`) for processing
- Clean up temporary files when possible
- Consider memory and timeout limits
- Use streaming for large files when possible

### 3. Security

- Request minimal IAM permissions
- Validate all inputs
- Don't log sensitive information
- Use environment variables for configuration

### 4. Maintainability

- Follow consistent naming conventions
- Document complex logic
- Use type hints in Python
- Keep functions focused and testable

### 5. Integration

- Follow the established event/payload structure
- Return data in expected formats
- Use the middleware for event bus integration
- Leverage existing utility functions

## Common Node Types

### Utility Nodes

- **Purpose**: General media processing (splitting, conversion, metadata extraction)
- **Location**: `utility/`
- **Examples**: `audio_splitter`, `video_proxy_and_thumbnail`, `image_metadata_extractor`

### Integration Nodes

- **Purpose**: Third-party service integration
- **Location**: `integration/`
- **Examples**: `bedrock`, `twelve_labs`, `audioshake`

### Trigger Nodes

- **Purpose**: Event-driven pipeline initiation
- **Location**: `trigger/`
- **Examples**: `trigger_ingest_completed`, `trigger_video_processing_completed`

### Flow Control Nodes

- **Purpose**: Pipeline logic and control flow
- **Location**: `flow/`
- **Examples**: `choice`, `parallel`, `map`

## Troubleshooting

### Common Issues

1. **Handler Not Found**: Ensure the YAML `handler` field matches the CDK deployment name
2. **Permission Denied**: Check IAM policies in the YAML template
3. **Layer Not Found**: Verify layer names match available layers in the stack
4. **Import Errors**: Check `requirements.txt` and available layers
5. **Timeout**: Adjust Lambda timeout for long-running operations

### Debugging Tips

1. **Check CloudWatch Logs**: Lambda execution logs contain detailed error information
2. **Test Locally**: Use SAM CLI or similar tools for local testing
3. **Validate YAML**: Ensure YAML syntax is correct
4. **Check Dependencies**: Verify all required layers and packages are available

## Conclusion

Creating new nodes in MediaLake involves:

1. Defining the node interface and configuration in YAML
2. Implementing the processing logic in Python
3. Registering the deployment in the CDK stack
4. Testing and validating the implementation

Follow the patterns established by existing nodes and refer to this guide for consistency and best practices.
