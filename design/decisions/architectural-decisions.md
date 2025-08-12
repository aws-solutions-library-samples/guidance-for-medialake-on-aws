---
title: S3 Asset Processor - Architectural Decision Records
task_id: lambda-refactoring-analysis
date: 2025-07-24
last_updated: 2025-07-24
status: DRAFT
owner: Architect
---

# S3 Asset Processor - Architectural Decision Records (ADRs)

## Overview

This document captures the key architectural decisions made during the analysis and design of the refactored S3 Asset Processor Lambda. Each decision is documented with context, options considered, rationale, and consequences.

## ADR Template

Each decision follows this structure:

- **Status**: Proposed | Accepted | Deprecated | Superseded
- **Context**: The situation requiring a decision
- **Decision**: What was decided
- **Rationale**: Why this decision was made
- **Consequences**: Positive and negative outcomes
- **Alternatives Considered**: Other options evaluated

---

## ADR-001: Adopt Hexagonal Architecture Pattern

**Status**: Accepted
**Date**: 2025-07-24

### Context

The current [`lambdas/ingest/s3/index.py`](lambdas/ingest/s3/index.py:1) is a 2,334-line monolithic function with tightly coupled business logic and infrastructure concerns. This creates maintenance challenges, testing difficulties, and limits extensibility.

### Decision

Adopt Hexagonal Architecture (Ports and Adapters) pattern with clear separation between:

- **Domain Layer**: Pure business logic and models
- **Application Layer**: Use case orchestration
- **Infrastructure Layer**: External service adapters
- **Presentation Layer**: Event processing and Lambda interface

### Rationale

1. **Separation of Concerns**: Business logic isolated from infrastructure
2. **Testability**: Each layer can be tested independently
3. **Flexibility**: Easy to swap implementations (e.g., different databases)
4. **Maintainability**: Clear boundaries reduce cognitive load
5. **AWS Lambda Best Practices**: Aligns with serverless architecture principles

### Consequences

**Positive**:

- Improved testability with >90% coverage achievable
- Reduced coupling between components
- Enhanced maintainability and readability
- Easier to add new features and integrations
- Better error handling and observability

**Negative**:

- Initial development overhead for setting up layers
- Slightly increased complexity for simple operations
- Need for dependency injection container

### Alternatives Considered

1. **Microservices**: Too complex for single Lambda function
2. **Layered Architecture**: Less flexible than hexagonal
3. **Event Sourcing**: Overkill for current requirements
4. **Keep Monolithic**: Maintains technical debt and complexity issues

---

## ADR-002: Use Command Query Responsibility Segregation (CQRS)

**Status**: Accepted
**Date**: 2025-07-24

### Context

The current system mixes read and write operations within the same methods, making it difficult to optimize for different access patterns and complicating the business logic flow.

### Decision

Implement CQRS pattern with separate command and query handlers:

- **Commands**: [`ProcessAssetCommand`](domain/commands/asset_commands.py:1), [`DeleteAssetCommand`](domain/commands/asset_commands.py:1)
- **Queries**: Asset lookups by hash, storage path, inventory ID
- **Handlers**: Dedicated handlers for each command/query type

### Rationale

1. **Clear Intent**: Commands change state, queries retrieve data
2. **Optimization**: Different optimization strategies for reads vs writes
3. **Scalability**: Can scale read and write operations independently
4. **Maintainability**: Focused handlers with single responsibility
5. **Testing**: Easier to test individual operations

### Consequences

**Positive**:

- Clear separation between read and write operations
- Optimized performance for different access patterns
- Simplified testing and debugging
- Better error handling for specific operations

**Negative**:

- Additional complexity in handler management
- Need for command/query routing logic

### Alternatives Considered

1. **Active Record Pattern**: Mixes data and behavior, less testable
2. **Repository Pattern Only**: Doesn't separate read/write concerns
3. **Direct Database Access**: Maintains current coupling issues

---

## ADR-003: Implement Dependency Injection Container

**Status**: Accepted
**Date**: 2025-07-24

### Context

The current code uses global variables for AWS clients and has hard-coded dependencies, making testing difficult and creating hidden coupling between components.

### Decision

Implement a dependency injection container ([`infrastructure/container.py`](infrastructure/container.py:1)) that:

- Manages service lifecycles
- Provides configured instances
- Supports testing with mock implementations
- Handles AWS client initialization

### Rationale

1. **Testability**: Easy to inject mock dependencies for testing
2. **Configuration**: Centralized service configuration
3. **Lifecycle Management**: Proper initialization and cleanup
4. **Loose Coupling**: Components depend on abstractions, not implementations
5. **Lambda Optimization**: Reuse connections across invocations

### Consequences

**Positive**:

- Dramatically improved testability
- Centralized configuration management
- Better resource management
- Easier to swap implementations

**Negative**:

- Additional complexity in service setup
- Learning curve for team members
- Potential over-engineering for simple cases

### Alternatives Considered

1. **Manual Dependency Injection**: More error-prone, harder to maintain
2. **Service Locator Pattern**: Creates hidden dependencies
3. **Global Variables**: Current approach, creates testing issues
4. **Factory Pattern**: Less flexible than full DI container

---

## ADR-004: Adopt Async/Await for Concurrent Operations

**Status**: Accepted
**Date**: 2025-07-24

### Context

The current implementation uses [`concurrent.futures.ThreadPoolExecutor`](lambdas/ingest/s3/index.py:1701) for parallel processing, but lacks consistent async patterns throughout the codebase.

### Decision

Implement async/await pattern throughout the new architecture:

- All handlers are async
- Repository operations are async
- External service calls use async clients
- Event processing supports concurrent execution

### Rationale

1. **Performance**: Better resource utilization in Lambda environment
2. **Scalability**: Handle multiple operations concurrently
3. **Modern Python**: Align with current Python best practices
4. **AWS SDK**: Native async support in boto3/aioboto3
5. **Error Handling**: Better exception propagation in async context

### Consequences

**Positive**:

- Improved performance for I/O-bound operations
- Better resource utilization
- Modern, maintainable code patterns
- Consistent async patterns throughout

**Negative**:

- Learning curve for team members unfamiliar with async
- Potential complexity in error handling
- Need for async-compatible libraries

### Alternatives Considered

1. **Keep ThreadPoolExecutor**: Less efficient, harder to manage
2. **Synchronous Only**: Simpler but less performant
3. **Mixed Sync/Async**: Inconsistent and confusing

---

## ADR-005: Use Repository Pattern for Data Access

**Status**: Accepted
**Date**: 2025-07-24

### Context

The current code directly accesses DynamoDB throughout the [`AssetProcessor`](lambdas/ingest/s3/index.py:307) class, creating tight coupling and making testing difficult.

### Decision

Implement Repository pattern with:

- Abstract [`AssetRepository`](domain/repositories/asset_repository.py:1) interface
- Concrete [`DynamoDBAssetRepository`](infrastructure/repositories/dynamodb_asset_repository.py:1) implementation
- Clear data access methods (save, find_by_hash, find_by_storage_path, delete)

### Rationale

1. **Abstraction**: Business logic independent of storage implementation
2. **Testability**: Easy to create in-memory implementations for testing
3. **Flexibility**: Can swap storage backends without changing business logic
4. **Optimization**: Repository can implement caching, batching, etc.
5. **Single Responsibility**: Data access logic separated from business logic

### Consequences

**Positive**:

- Improved testability with mock repositories
- Flexibility to change storage backends
- Centralized data access optimization
- Clear data access patterns

**Negative**:

- Additional abstraction layer
- Potential performance overhead if not optimized
- Need to maintain interface contracts

### Alternatives Considered

1. **Active Record**: Mixes data and behavior
2. **Data Access Object (DAO)**: Similar but less domain-focused
3. **Direct Database Access**: Current approach, creates coupling
4. **ORM**: Overkill for DynamoDB access patterns

---

## ADR-006: Implement Event-Driven Architecture with Domain Events

**Status**: Accepted
**Date**: 2025-07-24

### Context

The current system publishes events directly within business logic methods, creating coupling between business operations and event publishing infrastructure.

### Decision

Implement domain events pattern:

- Domain operations emit events
- Event publisher abstraction ([`EventPublisher`](domain/services/event_publisher.py:1))
- Concrete EventBridge implementation
- Async event publishing with error handling

### Rationale

1. **Decoupling**: Business logic independent of event infrastructure
2. **Reliability**: Proper error handling and retry logic
3. **Testability**: Can verify events without external dependencies
4. **Extensibility**: Easy to add new event types and handlers
5. **Observability**: Clear event flow for monitoring

### Consequences

**Positive**:

- Improved separation of concerns
- Better error handling for event publishing
- Enhanced testability
- Clear audit trail of business operations

**Negative**:

- Additional complexity in event management
- Need for event schema management
- Potential eventual consistency issues

### Alternatives Considered

1. **Direct EventBridge Calls**: Current approach, creates coupling
2. **Message Queue**: More complex than needed for current use case
3. **Database Events**: Requires additional infrastructure
4. **Synchronous Events**: Less resilient than async approach

---

## ADR-007: Use Feature Flags for Gradual Migration

**Status**: Accepted
**Date**: 2025-07-24

### Context

Migrating from a 2,334-line monolithic function to modular architecture carries significant risk. Need to ensure zero downtime and ability to rollback quickly.

### Decision

Implement feature flags using environment variables:

- `USE_NEW_PROCESS_HANDLER`: Toggle new asset processing
- `USE_NEW_DELETE_HANDLER`: Toggle new deletion logic
- `USE_NEW_EVENT_PARSER`: Toggle new event parsing
- Gradual rollout with monitoring

### Rationale

1. **Risk Mitigation**: Ability to rollback instantly
2. **Gradual Rollout**: Test with subset of traffic
3. **A/B Testing**: Compare performance between old and new
4. **Confidence Building**: Validate each component independently
5. **Zero Downtime**: No service interruption during migration

### Consequences

**Positive**:

- Reduced deployment risk
- Ability to validate each component
- Quick rollback capability
- Gradual team confidence building

**Negative**:

- Temporary code complexity with dual paths
- Need to maintain both implementations during migration
- Additional configuration management

### Alternatives Considered

1. **Big Bang Migration**: Too risky for critical system
2. **Blue-Green Deployment**: More complex infrastructure changes
3. **Canary Deployment**: Less granular control than feature flags
4. **Branch by Abstraction**: Similar but less flexible

---

## ADR-008: Adopt Strangler Fig Pattern for Migration

**Status**: Accepted
**Date**: 2025-07-24

### Context

The monolithic Lambda function is critical to the system and cannot be replaced all at once without significant risk.

### Decision

Use Strangler Fig pattern for migration:

- New components run alongside existing code
- Gradually replace functionality piece by piece
- Maintain existing interfaces during transition
- Remove old code only after new code is proven

### Rationale

1. **Risk Reduction**: Minimize impact of changes
2. **Incremental Value**: Deliver improvements gradually
3. **Learning**: Validate architectural decisions with real usage
4. **Team Confidence**: Build confidence through successful increments
5. **Business Continuity**: No disruption to existing functionality

### Consequences

**Positive**:

- Reduced risk of system failure
- Continuous delivery of improvements
- Ability to learn and adjust approach
- Maintained system stability

**Negative**:

- Longer migration timeline
- Temporary code complexity
- Need to maintain dual implementations

### Alternatives Considered

1. **Complete Rewrite**: Too risky for critical system
2. **Fork and Replace**: Harder to maintain consistency
3. **Service Extraction**: More complex for single Lambda
4. **Database-First Migration**: Doesn't address code complexity

---

## ADR-009: Use Type Hints and Pydantic for Data Validation

**Status**: Accepted
**Date**: 2025-07-24

### Context

The current code uses TypedDict classes but lacks runtime validation and comprehensive type checking, leading to potential runtime errors.

### Decision

Implement comprehensive typing strategy:

- Full type hints for all new code
- Pydantic models for data validation
- mypy integration in CI pipeline
- Runtime validation at system boundaries

### Rationale

1. **Reliability**: Catch errors at development time
2. **Documentation**: Types serve as living documentation
3. **IDE Support**: Better autocomplete and refactoring
4. **Runtime Safety**: Validate data at boundaries
5. **Team Productivity**: Reduce debugging time

### Consequences

**Positive**:

- Fewer runtime errors
- Better developer experience
- Self-documenting code
- Easier refactoring

**Negative**:

- Initial overhead in adding types
- Learning curve for team members
- Potential performance overhead for validation

### Alternatives Considered

1. **No Type Hints**: Current approach, error-prone
2. **Type Hints Only**: No runtime validation
3. **dataclasses**: Less validation than Pydantic
4. **Custom Validation**: More work than Pydantic

---

## ADR-010: Implement Comprehensive Error Handling Strategy

**Status**: Accepted
**Date**: 2025-07-24

### Context

The current code has inconsistent error handling with multiple try/catch blocks and unclear error propagation patterns.

### Decision

Implement structured error handling:

- Custom exception hierarchy ([`shared/exceptions.py`](shared/exceptions.py:1))
- Error handling at layer boundaries
- Structured error logging with context
- Proper error propagation to Lambda runtime

### Rationale

1. **Reliability**: Consistent error handling across components
2. **Observability**: Clear error context for debugging
3. **User Experience**: Appropriate error responses
4. **Monitoring**: Structured errors for alerting
5. **Debugging**: Clear error propagation paths

### Consequences

**Positive**:

- Improved system reliability
- Better debugging experience
- Consistent error responses
- Enhanced monitoring capabilities

**Negative**:

- Additional complexity in error handling code
- Need to define comprehensive exception hierarchy
- Potential performance overhead

### Alternatives Considered

1. **Current Approach**: Inconsistent and hard to debug
2. **Generic Exceptions**: Less specific error information
3. **Error Codes**: Less Pythonic than exceptions
4. **Result Pattern**: More complex than needed

---

## Cross-Cutting Decisions

### Logging and Observability

**Decision**: Use AWS Lambda Powertools for structured logging, metrics, and tracing
**Rationale**:

- Consistent with AWS best practices
- Built-in Lambda optimizations
- Structured logging for better searchability
- Integrated tracing for performance analysis

### Testing Strategy

**Decision**: Implement comprehensive testing pyramid
**Rationale**:

- Unit tests for domain logic (>95% coverage)
- Integration tests for infrastructure components
- Contract tests for external service interactions
- End-to-end tests for critical workflows

### Performance Optimization

**Decision**: Optimize for Lambda cold start and execution time
**Rationale**:

- Connection pooling for external services
- Lazy loading of dependencies
- Async operations for I/O-bound tasks
- Memory-efficient data structures

### Security Considerations

**Decision**: Implement defense-in-depth security
**Rationale**:

- Input validation at all boundaries
- Least privilege IAM permissions
- Secure handling of sensitive data
- Audit logging for compliance

## Decision Impact Matrix

| Decision               | Testability | Maintainability | Performance | Complexity | Risk |
| ---------------------- | ----------- | --------------- | ----------- | ---------- | ---- |
| Hexagonal Architecture | +++++       | +++++           | +++         | ++         | +    |
| CQRS                   | ++++        | ++++            | ++++        | ++         | +    |
| Dependency Injection   | +++++       | ++++            | +++         | ++         | +    |
| Async/Await            | +++         | +++             | +++++       | ++         | ++   |
| Repository Pattern     | +++++       | ++++            | +++         | ++         | +    |
| Event-Driven           | ++++        | ++++            | +++         | ++         | ++   |
| Feature Flags          | +++         | ++              | +           | ++         | +    |
| Strangler Fig          | ++          | +++             | ++          | ++         | +    |
| Type Hints             | ++++        | +++++           | ++          | +          | +    |
| Error Handling         | +++         | ++++            | ++          | ++         | +    |

**Legend**: + (Low) to +++++ (Very High)

## Implementation Priorities

### Phase 1 (Immediate)

1. **ADR-001**: Hexagonal Architecture - Foundation for all other decisions
2. **ADR-009**: Type Hints - Improves development experience immediately
3. **ADR-010**: Error Handling - Critical for system reliability

### Phase 2 (Short Term)

4. **ADR-003**: Dependency Injection - Enables testability
5. **ADR-005**: Repository Pattern - Improves data access
6. **ADR-002**: CQRS - Clarifies business operations

### Phase 3 (Medium Term)

7. **ADR-007**: Feature Flags - Enables safe migration
8. **ADR-008**: Strangler Fig - Migration strategy
9. **ADR-004**: Async/Await - Performance improvements

### Phase 4 (Long Term)

10. **ADR-006**: Event-Driven - Enhanced decoupling

## Monitoring and Review

These architectural decisions will be reviewed quarterly to ensure they continue to serve the system's needs. Key metrics for evaluation:

- **Code Quality**: Cyclomatic complexity, test coverage, type safety
- **Performance**: Lambda execution time, cold start duration, error rates
- **Maintainability**: Time to implement new features, bug fix duration
- **Team Productivity**: Developer satisfaction, onboarding time

## Conclusion

These architectural decisions provide a comprehensive framework for refactoring the S3 Asset Processor Lambda from a monolithic structure to a maintainable, testable, and scalable architecture. Each decision is grounded in software engineering best practices and addresses specific problems identified in the current implementation.

The decisions work together to create a cohesive architecture that:

- Separates concerns clearly
- Enables comprehensive testing
- Supports gradual migration
- Maintains system reliability
- Improves developer productivity

Regular review and adjustment of these decisions will ensure the architecture continues to evolve with changing requirements and best practices.
