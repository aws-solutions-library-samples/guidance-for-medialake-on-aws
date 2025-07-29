---
title: S3 Asset Processor - Modular Architecture Design
task_id: lambda-refactoring-analysis
date: 2025-07-24
last_updated: 2025-07-24
status: DRAFT
owner: Architect
---

# S3 Asset Processor - Modular Architecture Design

## Architecture Overview

This document presents a modular architecture design that decomposes the monolithic [`lambdas/ingest/s3/index.py`](lambdas/ingest/s3/index.py:1) into focused, testable, and maintainable components following SOLID principles and clean architecture patterns.

## Design Principles Applied

### 1. Single Responsibility Principle (SRP)

Each component has one reason to change and one primary responsibility.

### 2. Dependency Inversion Principle (DIP)

High-level modules depend on abstractions, not concrete implementations.

### 3. Interface Segregation Principle (ISP)

Clients depend only on interfaces they use.

### 4. Command Query Separation (CQS)

Clear separation between operations that change state and those that query state.

### 5. Hexagonal Architecture

Business logic isolated from external concerns through ports and adapters.

## Core Architecture Components

### 1. Domain Layer (Business Logic)

#### Asset Domain Model

```python
# domain/models/asset.py
@dataclass
class Asset:
    inventory_id: str
    asset_id: str
    asset_type: AssetType
    storage_info: StorageInfo
    metadata: AssetMetadata
    created_at: datetime
    modified_at: datetime

    def is_duplicate_of(self, other: 'Asset') -> bool:
        """Business rule for duplicate detection"""

    def should_process_deletion(self, version_id: Optional[str]) -> bool:
        """Business rule for deletion processing"""
```

#### Asset Processing Commands

```python
# domain/commands/asset_commands.py
@dataclass
class ProcessAssetCommand:
    bucket: str
    key: str
    event_type: str
    version_id: Optional[str] = None

@dataclass
class DeleteAssetCommand:
    bucket: str
    key: str
    version_id: Optional[str] = None
    is_delete_event: bool = True
```

#### Domain Services

```python
# domain/services/asset_service.py
class AssetDomainService:
    def determine_asset_type(self, content_type: str, file_extension: str) -> AssetType:
        """Pure business logic for asset type determination"""

    def should_skip_duplicate(self, existing: Asset, new: Asset, config: DuplicateConfig) -> bool:
        """Business rules for duplicate handling"""

    def calculate_asset_id(self, asset_type: AssetType) -> str:
        """Generate consistent asset identifiers"""
```

### 2. Application Layer (Use Cases)

#### Command Handlers

```python
# application/handlers/process_asset_handler.py
class ProcessAssetHandler:
    def __init__(
        self,
        asset_repository: AssetRepository,
        storage_service: StorageService,
        metadata_extractor: MetadataExtractor,
        event_publisher: EventPublisher,
        duplicate_detector: DuplicateDetector
    ):
        self._asset_repository = asset_repository
        self._storage_service = storage_service
        self._metadata_extractor = metadata_extractor
        self._event_publisher = event_publisher
        self._duplicate_detector = duplicate_detector

    async def handle(self, command: ProcessAssetCommand) -> ProcessAssetResult:
        """Orchestrate asset processing workflow"""
        # 1. Extract metadata
        # 2. Check for duplicates
        # 3. Create asset record
        # 4. Store in repository
        # 5. Publish events
```

```python
# application/handlers/delete_asset_handler.py
class DeleteAssetHandler:
    def __init__(
        self,
        asset_repository: AssetRepository,
        storage_service: StorageService,
        search_service: SearchService,
        vector_service: VectorService,
        event_publisher: EventPublisher
    ):
        # Dependencies injected

    async def handle(self, command: DeleteAssetCommand) -> DeleteAssetResult:
        """Orchestrate asset deletion workflow"""
        # 1. Validate deletion should proceed
        # 2. Find asset by storage path
        # 3. Delete from all services
        # 4. Publish deletion events
```

#### Query Handlers

```python
# application/handlers/asset_query_handler.py
class AssetQueryHandler:
    def __init__(self, asset_repository: AssetRepository):
        self._asset_repository = asset_repository

    async def find_by_hash(self, file_hash: str) -> Optional[Asset]:
        """Query for existing assets by hash"""

    async def find_by_storage_path(self, storage_path: str) -> Optional[Asset]:
        """Query for assets by S3 storage path"""
```

### 3. Infrastructure Layer (External Services)

#### Repository Implementations

```python
# infrastructure/repositories/dynamodb_asset_repository.py
class DynamoDBAssetRepository(AssetRepository):
    def __init__(self, dynamodb_client: DynamoDBClient, table_name: str):
        self._dynamodb = dynamodb_client
        self._table_name = table_name

    async def save(self, asset: Asset) -> None:
        """Save asset to DynamoDB"""

    async def find_by_hash(self, file_hash: str) -> Optional[Asset]:
        """Query by FileHashIndex"""

    async def find_by_storage_path(self, storage_path: str) -> Optional[Asset]:
        """Query by S3PathIndex"""

    async def delete(self, inventory_id: str) -> None:
        """Delete asset record"""
```

#### Service Implementations

```python
# infrastructure/services/s3_storage_service.py
class S3StorageService(StorageService):
    def __init__(self, s3_client: S3Client):
        self._s3 = s3_client

    async def get_object_metadata(self, bucket: str, key: str) -> ObjectMetadata:
        """Get S3 object metadata and tags"""

    async def tag_object(self, bucket: str, key: str, tags: Dict[str, str]) -> None:
        """Apply tags to S3 object"""

    async def check_object_exists(self, bucket: str, key: str) -> bool:
        """Verify object existence"""
```

```python
# infrastructure/services/eventbridge_publisher.py
class EventBridgePublisher(EventPublisher):
    def __init__(self, eventbridge_client: EventBridgeClient, bus_name: str):
        self._eventbridge = eventbridge_client
        self._bus_name = bus_name

    async def publish_asset_created(self, asset: Asset) -> None:
        """Publish AssetCreated event"""

    async def publish_asset_deleted(self, inventory_id: str) -> None:
        """Publish AssetDeleted event"""
```

#### External Service Adapters

```python
# infrastructure/services/opensearch_service.py
class OpenSearchService(SearchService):
    def __init__(self, opensearch_client: OpenSearchClient, index_name: str):
        self._client = opensearch_client
        self._index = index_name

    async def delete_documents(self, asset_id: str) -> int:
        """Delete all documents for asset"""
```

```python
# infrastructure/services/s3_vector_service.py
class S3VectorService(VectorService):
    def __init__(self, s3_vector_client: S3VectorClient, bucket_name: str, index_name: str):
        self._client = s3_vector_client
        self._bucket = bucket_name
        self._index = index_name

    async def delete_vectors(self, inventory_id: str) -> int:
        """Delete vectors by inventory ID"""
```

### 4. Presentation Layer (Event Processing)

#### Event Processors

```python
# presentation/processors/s3_event_processor.py
class S3EventProcessor:
    def __init__(
        self,
        process_handler: ProcessAssetHandler,
        delete_handler: DeleteAssetHandler,
        event_parser: EventParser
    ):
        self._process_handler = process_handler
        self._delete_handler = delete_handler
        self._event_parser = event_parser

    async def process_event(self, raw_event: Dict) -> ProcessingResult:
        """Process single S3 event"""
        parsed_event = self._event_parser.parse(raw_event)

        if parsed_event.is_deletion():
            command = DeleteAssetCommand(
                bucket=parsed_event.bucket,
                key=parsed_event.key,
                version_id=parsed_event.version_id,
                is_delete_event=True
            )
            return await self._delete_handler.handle(command)
        else:
            command = ProcessAssetCommand(
                bucket=parsed_event.bucket,
                key=parsed_event.key,
                event_type=parsed_event.event_type,
                version_id=parsed_event.version_id
            )
            return await self._process_handler.handle(command)
```

#### Lambda Handler

```python
# presentation/lambda_handler.py
class LambdaHandler:
    def __init__(self, event_processor: S3EventProcessor):
        self._processor = event_processor

    async def handle(self, event: Dict, context: LambdaContext) -> Dict:
        """Main Lambda entry point"""
        events = self._extract_events(event)

        # Process events in parallel
        tasks = [self._processor.process_event(evt) for evt in events]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return self._format_response(results)
```

## Component Interfaces (Ports)

### Repository Interfaces

```python
# domain/repositories/asset_repository.py
class AssetRepository(ABC):
    @abstractmethod
    async def save(self, asset: Asset) -> None:
        pass

    @abstractmethod
    async def find_by_hash(self, file_hash: str) -> Optional[Asset]:
        pass

    @abstractmethod
    async def find_by_storage_path(self, storage_path: str) -> Optional[Asset]:
        pass

    @abstractmethod
    async def delete(self, inventory_id: str) -> None:
        pass
```

### Service Interfaces

```python
# domain/services/storage_service.py
class StorageService(ABC):
    @abstractmethod
    async def get_object_metadata(self, bucket: str, key: str) -> ObjectMetadata:
        pass

    @abstractmethod
    async def tag_object(self, bucket: str, key: str, tags: Dict[str, str]) -> None:
        pass

    @abstractmethod
    async def check_object_exists(self, bucket: str, key: str) -> bool:
        pass
```

```python
# domain/services/event_publisher.py
class EventPublisher(ABC):
    @abstractmethod
    async def publish_asset_created(self, asset: Asset) -> None:
        pass

    @abstractmethod
    async def publish_asset_deleted(self, inventory_id: str) -> None:
        pass
```

## Dependency Injection Container

```python
# infrastructure/container.py
class DIContainer:
    def __init__(self, config: Config):
        self._config = config
        self._instances = {}

    def get_asset_repository(self) -> AssetRepository:
        if 'asset_repository' not in self._instances:
            self._instances['asset_repository'] = DynamoDBAssetRepository(
                dynamodb_client=self.get_dynamodb_client(),
                table_name=self._config.assets_table
            )
        return self._instances['asset_repository']

    def get_process_asset_handler(self) -> ProcessAssetHandler:
        return ProcessAssetHandler(
            asset_repository=self.get_asset_repository(),
            storage_service=self.get_storage_service(),
            metadata_extractor=self.get_metadata_extractor(),
            event_publisher=self.get_event_publisher(),
            duplicate_detector=self.get_duplicate_detector()
        )
```

## File Structure

```
lambdas/ingest/s3/
├── domain/
│   ├── models/
│   │   ├── asset.py
│   │   ├── storage_info.py
│   │   └── metadata.py
│   ├── services/
│   │   ├── asset_service.py
│   │   └── duplicate_service.py
│   ├── repositories/
│   │   └── asset_repository.py
│   └── commands/
│       └── asset_commands.py
├── application/
│   ├── handlers/
│   │   ├── process_asset_handler.py
│   │   ├── delete_asset_handler.py
│   │   └── asset_query_handler.py
│   └── services/
│       ├── metadata_extractor.py
│       └── duplicate_detector.py
├── infrastructure/
│   ├── repositories/
│   │   └── dynamodb_asset_repository.py
│   ├── services/
│   │   ├── s3_storage_service.py
│   │   ├── eventbridge_publisher.py
│   │   ├── opensearch_service.py
│   │   └── s3_vector_service.py
│   └── container.py
├── presentation/
│   ├── processors/
│   │   └── s3_event_processor.py
│   ├── parsers/
│   │   └── event_parser.py
│   └── lambda_handler.py
├── shared/
│   ├── types.py
│   ├── exceptions.py
│   └── config.py
└── main.py  # Lambda entry point
```

## Benefits of Modular Design

### 1. Testability

- Each component can be unit tested in isolation
- Dependencies can be mocked easily
- Clear test boundaries

### 2. Maintainability

- Changes to one concern don't affect others
- Clear responsibility boundaries
- Easier to understand and modify

### 3. Extensibility

- New asset types can be added without modifying existing code
- New storage backends can be plugged in
- Event sources can be extended

### 4. Performance

- Async/await support for concurrent operations
- Lazy loading of dependencies
- Optimized for Lambda cold starts

### 5. Monitoring & Observability

- Clear component boundaries for metrics
- Structured logging with context
- Distributed tracing support

## Migration Strategy

The modular design supports incremental migration:

1. **Phase 1**: Extract domain models and interfaces
2. **Phase 2**: Implement command handlers
3. **Phase 3**: Replace infrastructure services
4. **Phase 4**: Refactor event processing
5. **Phase 5**: Complete dependency injection

This approach allows for gradual refactoring while maintaining functionality throughout the process.
