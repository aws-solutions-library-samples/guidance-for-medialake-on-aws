---
title: S3 Asset Processor - Component Interaction Diagrams
task_id: lambda-refactoring-analysis
date: 2025-07-24
last_updated: 2025-07-24
status: DRAFT
owner: Architect
---

# S3 Asset Processor - Component Interaction Diagrams

## Overview

This document provides visual representations of component interactions in the proposed modular architecture, showing how different layers communicate and maintain clear separation of concerns.

## System Context Diagram

```mermaid
graph TB
    subgraph "External Systems"
        S3[S3 Bucket]
        DDB[DynamoDB]
        EB[EventBridge]
        OS[OpenSearch]
        S3V[S3 Vector Store]
        SQS[SQS Queue]
    end

    subgraph "S3 Asset Processor Lambda"
        LAM[Lambda Handler]
    end

    S3 -->|S3 Events| SQS
    SQS -->|Batched Events| LAM
    LAM -->|Read/Write| DDB
    LAM -->|Publish Events| EB
    LAM -->|Delete Docs| OS
    LAM -->|Delete Vectors| S3V
    LAM -->|Tag Objects| S3
```

## Container Diagram - Layered Architecture

```mermaid
graph TB
    subgraph "Presentation Layer"
        LH[Lambda Handler]
        EP[S3 Event Processor]
        EVP[Event Parser]
    end

    subgraph "Application Layer"
        PAH[Process Asset Handler]
        DAH[Delete Asset Handler]
        AQH[Asset Query Handler]
        ME[Metadata Extractor]
        DD[Duplicate Detector]
    end

    subgraph "Domain Layer"
        AS[Asset Service]
        DS[Duplicate Service]
        AM[Asset Model]
        CMD[Commands]
    end

    subgraph "Infrastructure Layer"
        AR[Asset Repository]
        SS[Storage Service]
        EBP[EventBridge Publisher]
        OSS[OpenSearch Service]
        S3VS[S3 Vector Service]
    end

    LH --> EP
    EP --> EVP
    EP --> PAH
    EP --> DAH
    PAH --> ME
    PAH --> DD
    PAH --> AS
    PAH --> AR
    PAH --> SS
    PAH --> EBP
    DAH --> AQH
    DAH --> AR
    DAH --> OSS
    DAH --> S3VS
    DAH --> EBP
    AS --> AM
    DS --> AM
    ME --> AS
    DD --> DS
```

## Component Diagram - Process Asset Flow

```mermaid
sequenceDiagram
    participant LH as Lambda Handler
    participant EP as Event Processor
    participant PAH as Process Asset Handler
    participant SS as Storage Service
    participant ME as Metadata Extractor
    participant DD as Duplicate Detector
    participant AS as Asset Service
    participant AR as Asset Repository
    participant EBP as Event Publisher

    LH->>EP: process_event(raw_event)
    EP->>EP: parse_event()
    EP->>PAH: handle(ProcessAssetCommand)

    PAH->>SS: get_object_metadata(bucket, key)
    SS-->>PAH: ObjectMetadata

    PAH->>ME: extract_metadata(metadata)
    ME->>AS: determine_asset_type(content_type, ext)
    AS-->>ME: AssetType
    ME-->>PAH: ExtractedMetadata

    PAH->>DD: check_for_duplicates(file_hash)
    DD->>AR: find_by_hash(file_hash)
    AR-->>DD: Optional[Asset]
    DD->>AS: should_skip_duplicate(existing, new, config)
    AS-->>DD: boolean
    DD-->>PAH: DuplicateCheckResult

    alt No Duplicate or Allow Duplicates
        PAH->>AS: create_asset(metadata)
        AS-->>PAH: Asset

        PAH->>AR: save(asset)
        AR-->>PAH: success

        PAH->>SS: tag_object(bucket, key, tags)
        SS-->>PAH: success

        PAH->>EBP: publish_asset_created(asset)
        EBP-->>PAH: success
    end

    PAH-->>EP: ProcessAssetResult
    EP-->>LH: ProcessingResult
```

## Component Diagram - Delete Asset Flow

```mermaid
sequenceDiagram
    participant LH as Lambda Handler
    participant EP as Event Processor
    participant DAH as Delete Asset Handler
    participant AQH as Asset Query Handler
    participant AR as Asset Repository
    participant SS as Storage Service
    participant OSS as OpenSearch Service
    participant S3VS as S3 Vector Service
    participant EBP as Event Publisher

    LH->>EP: process_event(raw_event)
    EP->>EP: parse_event()
    EP->>DAH: handle(DeleteAssetCommand)

    DAH->>AQH: find_by_storage_path(storage_path)
    AQH->>AR: find_by_storage_path(storage_path)
    AR-->>AQH: Optional[Asset]
    AQH-->>DAH: Optional[Asset]

    alt Asset Found
        DAH->>SS: delete_associated_files(asset)
        SS-->>DAH: success

        DAH->>AR: delete(inventory_id)
        AR-->>DAH: success

        par Delete from External Services
            DAH->>OSS: delete_documents(asset_id)
            OSS-->>DAH: deleted_count
        and
            DAH->>S3VS: delete_vectors(inventory_id)
            S3VS-->>DAH: deleted_count
        end

        DAH->>EBP: publish_asset_deleted(inventory_id)
        EBP-->>DAH: success
    end

    DAH-->>EP: DeleteAssetResult
    EP-->>LH: ProcessingResult
```

## Dependency Injection Flow

```mermaid
graph TB
    subgraph "DI Container"
        DIC[DIContainer]
    end

    subgraph "Configuration"
        CFG[Config]
        ENV[Environment Variables]
    end

    subgraph "AWS Clients"
        S3C[S3 Client]
        DDBC[DynamoDB Client]
        EBC[EventBridge Client]
        OSC[OpenSearch Client]
        S3VC[S3 Vector Client]
    end

    subgraph "Services"
        SS[Storage Service]
        EBP[EventBridge Publisher]
        OSS[OpenSearch Service]
        S3VS[S3 Vector Service]
        AR[Asset Repository]
    end

    subgraph "Handlers"
        PAH[Process Asset Handler]
        DAH[Delete Asset Handler]
        AQH[Asset Query Handler]
    end

    ENV --> CFG
    CFG --> DIC

    DIC --> S3C
    DIC --> DDBC
    DIC --> EBC
    DIC --> OSC
    DIC --> S3VC

    S3C --> SS
    DDBC --> AR
    EBC --> EBP
    OSC --> OSS
    S3VC --> S3VS

    DIC --> SS
    DIC --> AR
    DIC --> EBP
    DIC --> OSS
    DIC --> S3VS

    SS --> PAH
    AR --> PAH
    EBP --> PAH
    AR --> DAH
    OSS --> DAH
    S3VS --> DAH
    EBP --> DAH
    AR --> AQH
```

## Error Handling Flow

```mermaid
graph TB
    subgraph "Error Boundaries"
        LH[Lambda Handler]
        EP[Event Processor]
        PAH[Process Asset Handler]
        DAH[Delete Asset Handler]
    end

    subgraph "Error Types"
        SE[Service Errors]
        VE[Validation Errors]
        NF[Not Found Errors]
        DE[Duplicate Errors]
    end

    subgraph "Error Handling"
        EH[Error Handler]
        LOG[Logger]
        MET[Metrics]
        RET[Retry Logic]
    end

    PAH --> SE
    PAH --> VE
    DAH --> NF
    PAH --> DE

    SE --> EH
    VE --> EH
    NF --> EH
    DE --> EH

    EH --> LOG
    EH --> MET
    EH --> RET

    RET --> PAH
    RET --> DAH

    EH --> EP
    EP --> LH
```

## Data Flow Diagram

```mermaid
graph LR
    subgraph "Input"
        S3E[S3 Event]
        SQS[SQS Message]
        EB[EventBridge Event]
    end

    subgraph "Processing"
        EP[Event Parser]
        CMD[Command]
        HDL[Handler]
    end

    subgraph "Business Logic"
        DOM[Domain Service]
        VAL[Validation]
        BIZ[Business Rules]
    end

    subgraph "Data Storage"
        DDB[DynamoDB]
        S3T[S3 Tags]
    end

    subgraph "Output"
        EVT[Events]
        LOG[Logs]
        MET[Metrics]
    end

    S3E --> EP
    SQS --> EP
    EB --> EP

    EP --> CMD
    CMD --> HDL

    HDL --> DOM
    DOM --> VAL
    VAL --> BIZ

    BIZ --> DDB
    BIZ --> S3T

    HDL --> EVT
    HDL --> LOG
    HDL --> MET
```

## Testing Architecture

```mermaid
graph TB
    subgraph "Test Types"
        UT[Unit Tests]
        IT[Integration Tests]
        CT[Contract Tests]
        E2E[End-to-End Tests]
    end

    subgraph "Test Doubles"
        MOCK[Mocks]
        STUB[Stubs]
        FAKE[Fakes]
        SPY[Spies]
    end

    subgraph "Components Under Test"
        DOM[Domain Services]
        APP[Application Handlers]
        INF[Infrastructure Services]
        PRES[Presentation Layer]
    end

    UT --> DOM
    UT --> APP
    UT --> MOCK
    UT --> STUB

    IT --> APP
    IT --> INF
    IT --> FAKE

    CT --> INF
    CT --> SPY

    E2E --> PRES
    E2E --> FAKE
```

## Monitoring & Observability

```mermaid
graph TB
    subgraph "Application"
        LH[Lambda Handler]
        PAH[Process Asset Handler]
        DAH[Delete Asset Handler]
    end

    subgraph "Observability"
        LOG[Structured Logging]
        MET[Custom Metrics]
        TRC[Distributed Tracing]
        ALR[Alerts]
    end

    subgraph "AWS Services"
        CW[CloudWatch]
        XR[X-Ray]
        SNS[SNS]
    end

    LH --> LOG
    PAH --> LOG
    DAH --> LOG

    LH --> MET
    PAH --> MET
    DAH --> MET

    LH --> TRC
    PAH --> TRC
    DAH --> TRC

    LOG --> CW
    MET --> CW
    TRC --> XR

    CW --> ALR
    ALR --> SNS
```

## Key Architectural Benefits

### 1. Clear Separation of Concerns

- Each layer has distinct responsibilities
- Dependencies flow inward (Dependency Inversion)
- Business logic isolated from infrastructure

### 2. Testability

- Each component can be tested in isolation
- Dependencies can be easily mocked
- Clear test boundaries at each layer

### 3. Maintainability

- Changes to one layer don't affect others
- New features can be added without modifying existing code
- Clear component boundaries

### 4. Scalability

- Components can be optimized independently
- Async processing support
- Parallel execution capabilities

### 5. Observability

- Structured logging at each layer
- Metrics collection at component boundaries
- Distributed tracing through the entire flow

## Component Interaction Patterns

### 1. Command Pattern

- Commands encapsulate requests
- Handlers process commands
- Clear separation between request and processing

### 2. Repository Pattern

- Abstract data access
- Domain objects independent of storage
- Easy to swap implementations

### 3. Service Layer Pattern

- Business logic encapsulated in services
- Reusable across different handlers
- Clear API boundaries

### 4. Dependency Injection Pattern

- Loose coupling between components
- Easy testing and configuration
- Runtime flexibility

This modular architecture provides a solid foundation for maintaining and extending the S3 Asset Processor Lambda while ensuring high code quality, testability, and maintainability.
