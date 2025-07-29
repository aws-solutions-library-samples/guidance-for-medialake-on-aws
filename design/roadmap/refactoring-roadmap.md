---
title: S3 Asset Processor - Refactoring Roadmap
task_id: lambda-refactoring-analysis
date: 2025-07-24
last_updated: 2025-07-24
status: DRAFT
owner: Architect
---

# S3 Asset Processor - Refactoring Roadmap

## Executive Summary

This roadmap provides a structured approach to refactoring the monolithic [`lambdas/ingest/s3/index.py`](lambdas/ingest/s3/index.py:1) into a modular, maintainable architecture. The approach prioritizes risk mitigation, functionality preservation, and incremental delivery.

## Refactoring Strategy

### Approach: Strangler Fig Pattern

- **Gradual Migration**: Replace functionality piece by piece
- **Parallel Implementation**: New components run alongside existing code
- **Feature Toggles**: Control migration with configuration flags
- **Rollback Capability**: Maintain ability to revert at any phase

### Risk Mitigation

- **Comprehensive Testing**: Unit, integration, and contract tests
- **Monitoring**: Enhanced observability during migration
- **Canary Deployments**: Gradual rollout with traffic splitting
- **Backward Compatibility**: Maintain existing interfaces during transition

## Phase Overview

| Phase   | Duration  | Risk Level | Business Impact | Dependencies |
| ------- | --------- | ---------- | --------------- | ------------ |
| Phase 1 | 2-3 weeks | Low        | None            | None         |
| Phase 2 | 3-4 weeks | Medium     | Minimal         | Phase 1      |
| Phase 3 | 4-5 weeks | Medium     | Low             | Phase 2      |
| Phase 4 | 3-4 weeks | High       | Medium          | Phase 3      |
| Phase 5 | 2-3 weeks | Low        | None            | Phase 4      |

**Total Estimated Duration**: 14-19 weeks

## Phase 1: Foundation & Domain Modeling

### Objective

Establish the foundation for modular architecture without disrupting existing functionality.

### Priority: HIGH

**Rationale**: Creates the structural foundation for all subsequent phases.

### Tasks

#### 1.1 Domain Models & Types (Week 1)

**Effort**: 3-5 days
**Risk**: Low

**Deliverables**:

- [`domain/models/asset.py`](domain/models/asset.py:1) - Core Asset domain model
- [`domain/models/storage_info.py`](domain/models/storage_info.py:1) - Storage information structures
- [`domain/models/metadata.py`](domain/models/metadata.py:1) - Metadata models
- [`shared/types.py`](shared/types.py:1) - Common type definitions
- [`shared/exceptions.py`](shared/exceptions.py:1) - Custom exception hierarchy

**Implementation Strategy**:

```python
# Extract existing TypedDict classes into proper domain models
# Convert from current approach:
class FileHash(TypedDict):
    Algorithm: str
    Value: str
    MD5Hash: str

# To domain model:
@dataclass
class FileHash:
    algorithm: str
    value: str
    md5_hash: str

    def __post_init__(self):
        # Add validation logic
        pass
```

#### 1.2 Domain Services (Week 1-2)

**Effort**: 5-7 days
**Risk**: Low

**Deliverables**:

- [`domain/services/asset_service.py`](domain/services/asset_service.py:1) - Pure business logic
- [`domain/services/duplicate_service.py`](domain/services/duplicate_service.py:1) - Duplicate detection rules

**Implementation Strategy**:

```python
# Extract business logic from current AssetProcessor
# From lines 145-221 in current code:
def determine_asset_type(content_type: str, file_extension: str) -> str:
    # Move to domain service with proper typing and validation
```

#### 1.3 Command & Query Models (Week 2)

**Effort**: 2-3 days
**Risk**: Low

**Deliverables**:

- [`domain/commands/asset_commands.py`](domain/commands/asset_commands.py:1) - Command definitions
- [`domain/queries/asset_queries.py`](domain/queries/asset_queries.py:1) - Query definitions

#### 1.4 Repository Interfaces (Week 2-3)

**Effort**: 3-4 days
**Risk**: Low

**Deliverables**:

- [`domain/repositories/asset_repository.py`](domain/repositories/asset_repository.py:1) - Repository contracts
- [`domain/services/storage_service.py`](domain/services/storage_service.py:1) - Service interfaces

### Success Criteria

- [ ] All domain models have comprehensive unit tests (>95% coverage)
- [ ] Domain services are pure functions with no external dependencies
- [ ] Repository interfaces define clear contracts
- [ ] No breaking changes to existing functionality

### Testing Strategy

- **Unit Tests**: All domain logic isolated and tested
- **Property-Based Tests**: For business rule validation
- **Contract Tests**: For repository interfaces

---

## Phase 2: Application Layer & Command Handlers

### Objective

Implement the application layer with command/query handlers while maintaining existing functionality.

### Priority: HIGH

**Rationale**: Establishes the orchestration layer for business operations.

### Tasks

#### 2.1 Command Handlers (Week 1-2)

**Effort**: 7-10 days
**Risk**: Medium

**Deliverables**:

- [`application/handlers/process_asset_handler.py`](application/handlers/process_asset_handler.py:1)
- [`application/handlers/delete_asset_handler.py`](application/handlers/delete_asset_handler.py:1)
- [`application/handlers/asset_query_handler.py`](application/handlers/asset_query_handler.py:1)

**Implementation Strategy**:

```python
# Extract orchestration logic from current process_asset() method
# Break down 477-line method into focused handler:
class ProcessAssetHandler:
    async def handle(self, command: ProcessAssetCommand) -> ProcessAssetResult:
        # 1. Validate command
        # 2. Extract metadata
        # 3. Check duplicates
        # 4. Create asset
        # 5. Store asset
        # 6. Publish events
```

#### 2.2 Application Services (Week 2-3)

**Effort**: 5-7 days
**Risk**: Medium

**Deliverables**:

- [`application/services/metadata_extractor.py`](application/services/metadata_extractor.py:1)
- [`application/services/duplicate_detector.py`](application/services/duplicate_detector.py:1)
- [`application/services/event_orchestrator.py`](application/services/event_orchestrator.py:1)

#### 2.3 Feature Toggle Integration (Week 3)

**Effort**: 3-4 days
**Risk**: Low

**Deliverables**:

- [`shared/config.py`](shared/config.py:1) - Configuration management
- Feature flags for gradual handler adoption

**Implementation Strategy**:

```python
# Add feature toggles to existing code
if config.use_new_process_handler:
    result = await new_process_handler.handle(command)
else:
    result = legacy_process_asset(bucket, key)
```

#### 2.4 Integration Testing (Week 3-4)

**Effort**: 5-6 days
**Risk**: Medium

**Deliverables**:

- Integration test suite for handlers
- Performance benchmarks
- Error handling validation

### Success Criteria

- [ ] All handlers have >90% test coverage
- [ ] Performance matches or exceeds current implementation
- [ ] Feature toggles allow seamless switching
- [ ] Error handling maintains existing behavior

### Risk Mitigation

- **Parallel Execution**: Run new handlers alongside existing code
- **Metrics Comparison**: Monitor performance and error rates
- **Gradual Rollout**: Use feature flags for controlled adoption

---

## Phase 3: Infrastructure Layer Implementation

### Objective

Replace infrastructure concerns with focused, testable services.

### Priority: MEDIUM

**Rationale**: Improves maintainability and testability without changing core business logic.

### Tasks

#### 3.1 Repository Implementations (Week 1-2)

**Effort**: 8-10 days
**Risk**: Medium

**Deliverables**:

- [`infrastructure/repositories/dynamodb_asset_repository.py`](infrastructure/repositories/dynamodb_asset_repository.py:1)
- Repository performance optimization
- Connection pooling and retry logic

**Implementation Strategy**:

```python
# Replace direct DynamoDB calls from current AssetProcessor
# From current lines 1257-1328 (create_dynamo_entry):
class DynamoDBAssetRepository:
    async def save(self, asset: Asset) -> None:
        # Optimized batch operations
        # Proper error handling
        # Metrics collection
```

#### 3.2 External Service Adapters (Week 2-3)

**Effort**: 10-12 days
**Risk**: Medium-High

**Deliverables**:

- [`infrastructure/services/s3_storage_service.py`](infrastructure/services/s3_storage_service.py:1)
- [`infrastructure/services/eventbridge_publisher.py`](infrastructure/services/eventbridge_publisher.py:1)
- [`infrastructure/services/opensearch_service.py`](infrastructure/services/opensearch_service.py:1)
- [`infrastructure/services/s3_vector_service.py`](infrastructure/services/s3_vector_service.py:1)

#### 3.3 Dependency Injection Container (Week 3-4)

**Effort**: 5-7 days
**Risk**: Low

**Deliverables**:

- [`infrastructure/container.py`](infrastructure/container.py:1) - DI container
- Service lifecycle management
- Configuration injection

#### 3.4 Migration Testing (Week 4-5)

**Effort**: 7-8 days
**Risk**: High

**Deliverables**:

- End-to-end test suite
- Load testing scenarios
- Data consistency validation

### Success Criteria

- [ ] All external service calls go through adapters
- [ ] Repository operations maintain ACID properties
- [ ] Performance benchmarks meet SLA requirements
- [ ] Error rates remain within acceptable thresholds

### Risk Mitigation

- **Shadow Mode**: Run new services alongside existing ones
- **Data Validation**: Compare outputs between old and new implementations
- **Circuit Breakers**: Automatic fallback to legacy code on errors

---

## Phase 4: Event Processing Refactoring

### Objective

Modernize event processing with clean separation and async support.

### Priority: HIGH

**Rationale**: Addresses the most complex part of the current system.

### Tasks

#### 4.1 Event Parser Extraction (Week 1)

**Effort**: 5-6 days
**Risk**: Medium

**Deliverables**:

- [`presentation/parsers/event_parser.py`](presentation/parsers/event_parser.py:1)
- Support for all current event formats (S3, SQS, EventBridge)
- Comprehensive event validation

**Implementation Strategy**:

```python
# Extract complex parsing logic from current handler() function
# From lines 1835-2064 (handler function):
class EventParser:
    def parse(self, raw_event: Dict) -> List[ParsedEvent]:
        # Handle S3 direct events
        # Handle SQS wrapped events
        # Handle EventBridge events
        # Unified parsing with validation
```

#### 4.2 Async Event Processor (Week 1-2)

**Effort**: 7-8 days
**Risk**: High

**Deliverables**:

- [`presentation/processors/s3_event_processor.py`](presentation/processors/s3_event_processor.py:1)
- Async/await support for concurrent processing
- Improved error handling and retry logic

#### 4.3 Lambda Handler Modernization (Week 2-3)

**Effort**: 5-7 days
**Risk**: High

**Deliverables**:

- [`presentation/lambda_handler.py`](presentation/lambda_handler.py:1)
- Clean separation of concerns
- Enhanced observability

#### 4.4 Parallel Processing Optimization (Week 3-4)

**Effort**: 6-8 days
**Risk**: Medium

**Deliverables**:

- Optimized concurrent processing
- Resource management improvements
- Performance monitoring

### Success Criteria

- [ ] Event processing latency reduced by >20%
- [ ] Error handling covers all edge cases
- [ ] Concurrent processing scales efficiently
- [ ] Memory usage optimized for Lambda limits

### Risk Mitigation

- **Gradual Migration**: Process events through both old and new paths
- **Performance Monitoring**: Real-time metrics comparison
- **Rollback Plan**: Immediate revert capability on performance degradation

---

## Phase 5: Cleanup & Optimization

### Objective

Remove legacy code, optimize performance, and finalize documentation.

### Priority: MEDIUM

**Rationale**: Completes the migration and optimizes the new architecture.

### Tasks

#### 5.1 Legacy Code Removal (Week 1)

**Effort**: 3-4 days
**Risk**: Low

**Deliverables**:

- Remove original monolithic [`AssetProcessor`](lambdas/ingest/s3/index.py:307) class
- Clean up global state management
- Remove unused imports and functions

#### 5.2 Performance Optimization (Week 1-2)

**Effort**: 5-6 days
**Risk**: Low

**Deliverables**:

- Cold start optimization
- Memory usage improvements
- Connection pooling enhancements

#### 5.3 Documentation & Training (Week 2-3)

**Effort**: 4-5 days
**Risk**: Low

**Deliverables**:

- Updated README and architecture documentation
- Developer onboarding guide
- Troubleshooting runbook

#### 5.4 Final Validation (Week 3)

**Effort**: 2-3 days
**Risk**: Low

**Deliverables**:

- Complete test suite execution
- Performance benchmark validation
- Security review completion

### Success Criteria

- [ ] All legacy code removed
- [ ] Performance improvements documented
- [ ] Team trained on new architecture
- [ ] Documentation complete and accurate

---

## Implementation Guidelines

### Development Practices

#### 1. Test-Driven Development

- Write tests before implementing new components
- Maintain >90% code coverage throughout migration
- Use property-based testing for business rules

#### 2. Continuous Integration

- Automated testing on every commit
- Performance regression detection
- Security scanning integration

#### 3. Monitoring & Observability

- Enhanced logging during migration
- Custom metrics for new components
- Distributed tracing implementation

### Code Quality Standards

#### 1. Type Safety

- Full type annotations for all new code
- mypy validation in CI pipeline
- Pydantic for data validation

#### 2. Error Handling

- Structured exception hierarchy
- Proper error propagation
- Comprehensive error logging

#### 3. Performance

- Async/await for I/O operations
- Connection pooling for external services
- Memory-efficient data structures

## Risk Assessment & Mitigation

### High-Risk Areas

#### 1. Event Processing Migration (Phase 4)

**Risk**: Complex event parsing logic may introduce bugs
**Mitigation**:

- Comprehensive test coverage for all event formats
- Shadow mode testing with production traffic
- Gradual rollout with immediate rollback capability

#### 2. Database Operations (Phase 3)

**Risk**: Data consistency issues during repository migration
**Mitigation**:

- Transaction-based operations
- Data validation between old and new implementations
- Backup and recovery procedures

#### 3. Performance Regression

**Risk**: New architecture may impact Lambda performance
**Mitigation**:

- Continuous performance monitoring
- Load testing at each phase
- Performance budgets and alerts

### Rollback Procedures

#### Immediate Rollback (< 5 minutes)

- Feature flag toggle to disable new components
- Automatic fallback to legacy code paths
- Alert-based rollback triggers

#### Phase Rollback (< 30 minutes)

- Revert to previous deployment
- Database migration rollback if needed
- Communication to stakeholders

## Success Metrics

### Technical Metrics

- **Code Complexity**: Reduce cyclomatic complexity by >60%
- **Test Coverage**: Maintain >90% coverage throughout migration
- **Performance**: Maintain or improve current latency (p95 < 2s)
- **Error Rate**: Keep error rate < 0.1%

### Business Metrics

- **Deployment Frequency**: Enable daily deployments
- **Lead Time**: Reduce feature development time by >40%
- **MTTR**: Reduce mean time to recovery by >50%
- **Developer Satisfaction**: Improve team velocity and satisfaction

## Conclusion

This refactoring roadmap provides a structured approach to modernizing the S3 Asset Processor Lambda while minimizing risk and maintaining business continuity. The phased approach ensures that each step builds upon the previous one, with clear success criteria and rollback procedures.

The investment in this refactoring will pay dividends in:

- **Reduced Maintenance Costs**: Easier to understand and modify code
- **Improved Developer Productivity**: Clear architecture and separation of concerns
- **Enhanced Reliability**: Better error handling and testing
- **Future Extensibility**: Easy to add new features and integrations

**Recommended Start Date**: Immediate
**Estimated Completion**: 14-19 weeks
**Resource Requirements**: 1-2 senior developers, 1 architect (part-time)
