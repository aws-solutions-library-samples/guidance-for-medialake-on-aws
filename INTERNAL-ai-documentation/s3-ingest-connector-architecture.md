# S3 Ingest Connector - Architecture Overview

This document provides a comprehensive view of the S3 ingestion connector architecture, showing how assets flow through various AWS services.

## High-Level Architecture Diagram

b

## Detailed Component Interactions

### 1. Asset Upload & Event Generation

```mermaid
sequenceDiagram
    actor User
    participant S3 as S3 Bucket
    participant EventSrc as S3 Events/EventBridge
    participant SQS as SQS Queue

    User->>S3: Upload Asset (PUT/POST/COPY)
    S3->>S3: Store Object
    S3->>EventSrc: Emit Event (ObjectCreated:*)
    EventSrc->>SQS: Queue Event
    Note over SQS: Event buffered<br/>for processing
```

### 2. Lambda Processing Flow

```mermaid
sequenceDiagram
    participant SQS
    participant Lambda as S3 Ingest Lambda
    participant S3
    participant DDB as DynamoDB
    participant Tags as S3 Tags
    participant EB as EventBridge

    SQS->>Lambda: Trigger with S3 Event(s)
    Lambda->>Lambda: Parse Event(s)

    par Parallel S3 Operations
        Lambda->>S3: head_object (metadata)
        Lambda->>Tags: get_object_tagging
    end

    Lambda->>Lambda: Calculate MD5 Hash
    Lambda->>DDB: Query FileHashIndex

    alt New Asset
        Lambda->>DDB: put_item (Asset Record)
        Lambda->>Tags: put_object_tagging<br/>(InventoryID, AssetID, FileHash)
        Lambda->>EB: put_events (AssetCreated)
    else Duplicate Hash - Same Path
        Lambda->>DDB: update_item (lastModifiedDate)
        Lambda->>Tags: put_object_tagging
    else Duplicate Hash - Different Path (Moved)
        Lambda->>S3: delete_object (old location)
        Lambda->>DDB: update_item (new StoragePath)
        Lambda->>Tags: put_object_tagging
        Lambda->>EB: put_events (AssetCreated)
    else Asset Deleted
        Lambda->>DDB: Query S3PathIndex
        Lambda->>DDB: delete_item
        Lambda->>EB: put_events (AssetDeleted)
        Lambda->>Lambda: delete_opensearch_docs
        Lambda->>Lambda: delete_s3_vectors
    end
```

### 3. DynamoDB Stream to OpenSearch

```mermaid
sequenceDiagram
    participant DDB as DynamoDB Assets Table
    participant Stream as DynamoDB Stream
    participant Lambda as Stream Processing Lambda
    participant OS as OpenSearch

    DDB->>Stream: Change Record (INSERT/MODIFY/REMOVE)
    Stream->>Lambda: Trigger with Batch

    Lambda->>Lambda: Transform to OpenSearch Format

    alt INSERT or MODIFY
        Lambda->>OS: Index Document(s)
        OS->>OS: Update Search Index
    else REMOVE
        Lambda->>OS: Delete Document(s)
        OS->>OS: Remove from Index
    end
```

### 4. Event Distribution & Pipeline Processing

```mermaid
flowchart LR
    EB[EventBridge<br/>Event Bus]

    subgraph "Event Types"
        Created[AssetCreated Event<br/>- InventoryID<br/>- AssetID<br/>- Type<br/>- StorageInfo]
        Deleted[AssetDeleted Event<br/>- InventoryID<br/>- DeletedAt]
    end

    subgraph "Pipeline Subscribers"
        ImgPipe[Image Pipeline Lambda]
        VidPipe[Video Pipeline Lambda]
        AudPipe[Audio Pipeline Lambda]
        OtherSvc[Other Services/Lambdas]
    end

    EB --> Created
    EB --> Deleted

    Created -->|Type: Image| ImgPipe
    Created -->|Type: Video| VidPipe
    Created -->|Type: Audio| AudPipe
    Created --> OtherSvc

    ImgPipe -->|Generate Thumbnails<br/>Extract EXIF| Processing[Further Processing]
    VidPipe -->|Generate Previews<br/>Extract Frames| Processing
    AudPipe -->|Transcribe<br/>Extract Waveform| Processing

    style Created fill:#90EE90
    style Deleted fill:#FFB6C1
```

## Data Structures

### DynamoDB Asset Record

```json
{
  "InventoryID": "asset:uuid:{uuid}",
  "FileHash": "{md5-hash}",
  "StoragePath": "{bucket}:{key}",
  "DigitalSourceAsset": {
    "ID": "asset:{type-abbrev}:{uuid}",
    "Type": "Image|Video|Audio",
    "CreateDate": "ISO-8601",
    "IngestedAt": "ISO-8601",
    "originalIngestDate": "ISO-8601",
    "lastModifiedDate": "ISO-8601",
    "MainRepresentation": {
      "ID": "asset:rep:{uuid}:master",
      "Type": "Image|Video|Audio",
      "Format": "JPG|MP4|WAV|etc",
      "Purpose": "master",
      "StorageInfo": {
        "PrimaryLocation": {
          "StorageType": "s3",
          "Bucket": "{bucket-name}",
          "ObjectKey": {
            "Name": "{filename}",
            "Path": "{directory-path}",
            "FullPath": "{full-key}"
          },
          "Status": "active",
          "FileInfo": {
            "Size": 12345,
            "Hash": {
              "Algorithm": "SHA256",
              "Value": "{etag}",
              "MD5Hash": "{md5}"
            },
            "CreateDate": "ISO-8601"
          }
        }
      }
    }
  },
  "DerivedRepresentations": [],
  "Metadata": {
    "ObjectMetadata": {
      "ExtractedDate": "ISO-8601",
      "S3": {
        "Metadata": {},
        "ContentType": "image/jpeg",
        "LastModified": "ISO-8601"
      }
    }
  }
}
```

### S3 Object Tags

```
InventoryID: asset:uuid:{uuid}
AssetID: asset:{type}:{uuid}
FileHash: {md5-hash}
DuplicateHash: true|false (optional)
```

### EventBridge Events

**AssetCreated:**

```json
{
  "Source": "custom.asset.processor",
  "DetailType": "AssetCreated",
  "Detail": {
    "InventoryID": "asset:uuid:{uuid}",
    "FileHash": "{md5}",
    "DigitalSourceAsset": {
      "ID": "asset:{type}:{uuid}",
      "Type": "Image|Video|Audio",
      "CreateDate": "ISO-8601",
      "originalIngestDate": "ISO-8601",
      "lastModifiedDate": "ISO-8601",
      "MainRepresentation": {
        /* ... */
      }
    },
    "DerivedRepresentations": [],
    "Metadata": {
      /* ... */
    }
  }
}
```

**AssetDeleted:**

```json
{
  "Source": "custom.asset.processor",
  "DetailType": "AssetDeleted",
  "Detail": {
    "InventoryID": "asset:uuid:{uuid}",
    "DeletedAt": "ISO-8601"
  }
}
```

## Key AWS Services & Their Roles

### S3 Bucket

- **Purpose**: Primary storage for media assets
- **Configuration**: Event notifications enabled for ObjectCreated and ObjectRemoved events
- **Tags**: Lambda adds metadata tags (InventoryID, AssetID, FileHash)

### SQS Queue

- **Purpose**: Buffer S3 events for reliable processing
- **Benefit**: Decouples event generation from processing, provides retry capability
- **Configuration**: Dead Letter Queue for failed messages

### Lambda (S3 Ingest)

- **Runtime**: Python 3.x
- **Memory**: Configurable (recommend 1024MB+)
- **Timeout**: 15 minutes (for large file processing)
- **Concurrency**: Configurable based on load
- **Environment Variables**:
  - `ASSETS_TABLE`: DynamoDB table name
  - `EVENT_BUS_NAME`: EventBridge bus name
  - `DO_NOT_INGEST_DUPLICATES`: Boolean flag
  - `OPENSEARCH_ENDPOINT`: OpenSearch domain endpoint
  - `VECTOR_BUCKET_NAME`: S3 Vector Store bucket

### DynamoDB Assets Table

- **Primary Key**: `InventoryID` (String)
- **Global Secondary Indexes**:
  - `FileHashIndex`: Query by `FileHash` for duplicate detection
  - `S3PathIndex`: Query by `StoragePath` for deletions
- **Stream**: Enabled for real-time indexing to OpenSearch
- **On-Demand or Provisioned**: Based on workload

### EventBridge Event Bus

- **Purpose**: Distribute asset events to downstream services
- **Rules**: Filter events by DetailType, asset Type, etc.
- **Targets**: Pipeline Lambdas, SNS topics, Step Functions

### OpenSearch

- **Purpose**: Full-text search and analytics
- **Index**: `media` (configurable)
- **Population**: Via DynamoDB Stream Lambda
- **Deletion**: Direct from S3 Ingest Lambda

### S3 Vector Store

- **Purpose**: Store embeddings for semantic search
- **Population**: Via pipeline processing Lambdas
- **Deletion**: Direct from S3 Ingest Lambda
- **Index**: `media-vectors`

## Processing Metrics

The Lambda publishes CloudWatch metrics for monitoring:

### Operational Metrics

- `Invocations`: Lambda invocation count
- `RecordsProcessed`: Total S3 events processed
- `RecordsProcessedSuccessfully`: Successful processing count
- `RecordsSkipped`: Events skipped (unsupported types, etc.)
- `RecordsProcessedWithErrors`: Failed processing count

### Asset Metrics

- `ProcessedAssets`: New assets created
- `DeletedAssets`: Assets removed
- `UnsupportedAssetTypeSkipped`: Non-media files skipped
- `CreationEvents`: ObjectCreated event count

### Duplicate Detection

- `DuplicateCheckPerformed`: Hash checks executed
- `OldObjectsDeleted`: Old S3 objects deleted (moves/renames)
- `RecordsUpdatedWithNewPath`: Records updated for moved files

### Performance Metrics

- `EventProcessingTime`: Processing duration (seconds)
- `FailedEventProcessingTime`: Failed processing duration
- `MemoryUsedMB`: Lambda memory usage

### Data Operations

- `OpenSearchDocsDeleted`: OpenSearch documents deleted
- `VectorsDeleted`: S3 vector embeddings deleted
- `EventsPublished`: EventBridge events published
- `EventPublishErrors`: Failed event publications

## Error Handling

### Retry Strategy

1. **SQS Queue**: Failed Lambda invocations automatically retry
2. **Dead Letter Queue**: Messages that fail after max retries
3. **CloudWatch Logs**: Detailed error logging with context
4. **AWS X-Ray**: Distributed tracing for debugging

### Failure Scenarios

- **S3 Access Errors**: Logged and retried
- **DynamoDB Throttling**: Exponential backoff with adaptive retry mode
- **EventBridge Failures**: Logged for manual intervention
- **OpenSearch Errors**: Non-blocking (deletion continues)
- **S3 Vector Store Errors**: Non-blocking (deletion continues)

## Performance Considerations

### Optimization Techniques

1. **Parallel Processing**: ThreadPoolExecutor for concurrent S3 operations
2. **Global Client Reuse**: Clients initialized once per container
3. **LRU Caching**: Type mappings and determinations cached
4. **Batch Operations**: Multiple records processed per invocation
5. **Conditional Processing**: Early exit for unsupported types

### Scalability

- **Lambda Concurrency**: Auto-scales based on SQS queue depth
- **DynamoDB**: On-demand scaling or provisioned throughput
- **SQS**: Unlimited throughput
- **OpenSearch**: Configurable instance types and counts

## Security

### IAM Permissions Required

- **S3**: GetObject, PutObjectTagging, DeleteObject, HeadObject, GetObjectTagging
- **DynamoDB**: Query, GetItem, PutItem, UpdateItem, DeleteItem
- **EventBridge**: PutEvents
- **OpenSearch**: ESHttpPost, ESHttpDelete
- **S3 Vectors**: ListVectors, DeleteVectors
- **CloudWatch**: PutMetricData, CreateLogGroup, CreateLogStream, PutLogEvents
- **X-Ray**: PutTraceSegments, PutTelemetryRecords

### Data Security

- **Encryption at Rest**: S3, DynamoDB, OpenSearch all support encryption
- **Encryption in Transit**: All AWS service calls use TLS
- **VPC**: Lambda can run in VPC for network isolation
- **IAM Roles**: Least privilege access per service
