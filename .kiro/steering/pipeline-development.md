---
inclusion: fileMatch
fileMatchPattern: "**/pipeline*"
---

# Pipeline Development Guidelines for MediaLake

## Pipeline Architecture Overview

MediaLake pipelines are event-driven workflows that process media assets through customizable processing steps. Pipelines use AWS Step Functions for orchestration, Lambda functions for processing nodes, and EventBridge for event routing.

## Pipeline Design Principles

### Event-Driven Processing

- Use EventBridge for decoupled event routing between pipeline stages
- Implement idempotent processing to handle duplicate events
- Design for eventual consistency across distributed components
- Use FIFO SQS queues for ordered processing when sequence matters

### Modular Node Architecture

- Each processing node should be a self-contained Lambda function
- Nodes should have single responsibility (metadata extraction, transcoding, etc.)
- Use standardized input/output formats between nodes
- Implement proper error handling and retry logic in each node

### Scalable Processing

- Design nodes to handle variable workloads
- Use appropriate Lambda memory and timeout configurations
- Implement parallel processing where possible
- Consider batch processing for efficiency

## Pipeline Node Development

### Node Structure

Pipeline nodes are located in `lambdas/nodes/` and follow this structure:

```
lambdas/nodes/{node_name}/
├── index.py          # Main Lambda handler
├── requirements.txt  # Python dependencies
├── utils.py         # Node-specific utilities (optional)
└── README.md        # Node documentation
```

### Node Implementation Pattern

```python
# Standard node implementation pattern
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Standard pipeline node handler

    Args:
        event: Pipeline event containing asset information
        context: Lambda context

    Returns:
        Processed event with node results
    """
    try:
        # Extract asset information
        asset_id = event.get('asset_id')
        input_data = event.get('input', {})

        # Process the asset
        result = process_asset(asset_id, input_data)

        # Return standardized response
        return {
            'asset_id': asset_id,
            'node_name': 'your_node_name',
            'status': 'completed',
            'output': result,
            'metadata': {
                'processing_time': context.get_remaining_time_in_millis(),
                'memory_used': context.memory_limit_in_mb
            }
        }

    except Exception as e:
        logger.error(f"Node processing failed: {str(e)}")
        return {
            'asset_id': event.get('asset_id'),
            'node_name': 'your_node_name',
            'status': 'failed',
            'error': str(e)
        }
```

### Node Configuration

- Use environment variables for configuration
- Store node templates in `s3_bucket_assets/pipeline_nodes/node_templates/`
- Include OpenAPI specifications in `s3_bucket_assets/pipeline_nodes/open_api_specs/`
- Document node capabilities and requirements

## Pipeline Templates

### Template Structure

Pipeline templates are JSON files stored in `pipeline_library/` that define:

- Processing steps and their sequence
- Node configurations and parameters
- Error handling and retry policies
- Output specifications

### Default Pipeline Templates

MediaLake includes several default pipeline templates:

- **Default Audio Pipeline.json** - Audio processing workflow
- **Default Image Pipeline.json** - Image processing workflow
- **Default Video Pipeline.json** - Video processing workflow
- **Audio Transcription.json** - Audio transcription workflow
- **Video Transcription.json** - Video transcription workflow

### Custom Pipeline Development

```json
{
  "name": "Custom Processing Pipeline",
  "description": "Custom media processing workflow",
  "version": "1.0",
  "steps": [
    {
      "name": "metadata_extraction",
      "node_type": "metadata_extractor",
      "configuration": {
        "extract_technical": true,
        "extract_descriptive": true
      },
      "retry_policy": {
        "max_attempts": 3,
        "backoff_rate": 2.0
      }
    },
    {
      "name": "thumbnail_generation",
      "node_type": "thumbnail_generator",
      "depends_on": ["metadata_extraction"],
      "configuration": {
        "sizes": ["150x150", "300x300"],
        "format": "jpeg"
      }
    }
  ]
}
```

## Step Functions Integration

### State Machine Design

- Use Express Workflows for high-volume, short-duration processing
- Implement proper error handling with Catch and Retry states
- Use Parallel states for independent processing steps
- Include Choice states for conditional processing logic

### Error Handling Patterns

```json
{
  "ProcessMedia": {
    "Type": "Task",
    "Resource": "arn:aws:lambda:region:account:function:process-media",
    "Retry": [
      {
        "ErrorEquals": ["Lambda.ServiceException", "Lambda.AWSLambdaException"],
        "IntervalSeconds": 2,
        "MaxAttempts": 3,
        "BackoffRate": 2.0
      }
    ],
    "Catch": [
      {
        "ErrorEquals": ["States.ALL"],
        "Next": "HandleError",
        "ResultPath": "$.error"
      }
    ]
  }
}
```

## Media Processing Best Practices

### File Format Support

Support the media formats defined in constants.py:

- **Images**: JPG, PNG, GIF, TIFF, BMP, WEBP, PSD, SVG
- **Video**: MP4, MOV, AVI, MKV, WEBM, FLV, MXF
- **Audio**: MP3, WAV, AAC, OGG, FLAC, M4A, AIFF, PCM

### Processing Optimization

- Use appropriate Lambda memory allocation based on file sizes
- Implement streaming processing for large files
- Use temporary storage efficiently (Lambda /tmp directory)
- Clean up temporary files after processing

### Metadata Extraction

- Extract technical metadata (resolution, duration, codec, etc.)
- Extract descriptive metadata (title, description, tags, etc.)
- Store metadata in standardized formats
- Index metadata in OpenSearch for searchability

## Integration with External Services

### AWS Native Services

- **MediaConvert** - Video transcoding and format conversion
- **Transcribe** - Audio transcription services
- **Rekognition** - Image and video analysis
- **Textract** - Document text extraction

### Third-Party Integrations

- **TwelveLabs** - AI-powered video understanding
- Implement proper API key management using Secrets Manager
- Handle rate limiting and quota management
- Implement proper error handling for external service failures

### Integration Patterns

```python
# Example external service integration
import boto3
from botocore.exceptions import ClientError

def call_external_service(asset_data):
    """Call external service with proper error handling"""
    try:
        # Get API credentials from Secrets Manager
        secrets_client = boto3.client('secretsmanager')
        secret = secrets_client.get_secret_value(SecretId='external-service-api-key')
        api_key = secret['SecretString']

        # Make API call with retry logic
        response = make_api_call(asset_data, api_key)
        return response

    except ClientError as e:
        logger.error(f"Failed to retrieve API credentials: {e}")
        raise
    except Exception as e:
        logger.error(f"External service call failed: {e}")
        raise
```

## Pipeline Monitoring and Observability

### Logging Standards

- Use structured logging with correlation IDs
- Log pipeline start, progress, and completion events
- Include processing metrics (duration, file size, etc.)
- Log errors with sufficient context for debugging

### Metrics and Alarms

- Monitor pipeline execution success/failure rates
- Track processing duration and throughput
- Monitor Lambda function performance metrics
- Set up alarms for critical pipeline failures

### Tracing

- Use X-Ray for distributed tracing across pipeline steps
- Include custom segments for external service calls
- Track end-to-end pipeline execution times
- Monitor cold start impacts on processing

## Testing Pipeline Components

### Unit Testing

- Test individual node logic in isolation
- Mock AWS services and external APIs
- Test error handling and edge cases
- Validate output formats and schemas

### Integration Testing

- Test complete pipeline workflows
- Use test media files of various formats
- Validate Step Functions state machine execution
- Test error recovery and retry mechanisms

### Performance Testing

- Test with realistic file sizes and volumes
- Validate processing times meet requirements
- Test concurrent pipeline execution
- Monitor resource utilization during testing

## Pipeline Deployment and Versioning

### Version Management

- Use semantic versioning for pipeline templates
- Maintain backward compatibility when possible
- Document breaking changes and migration paths
- Test pipeline upgrades in staging environments

### Deployment Strategies

- Use blue-green deployments for critical pipelines
- Implement gradual rollout for new pipeline versions
- Maintain rollback procedures for failed deployments
- Test deployments in lower environments first

### Configuration Management

- Store pipeline configurations in version control
- Use environment-specific parameter files
- Implement configuration validation
- Document configuration options and defaults
