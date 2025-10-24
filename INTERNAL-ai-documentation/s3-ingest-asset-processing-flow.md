# S3 Ingest Lambda - Asset Processing Flow

This diagram shows the complete flow of asset processing in the S3 ingest Lambda, including all checks for duplicates, hashes, and asset identification.

```mermaid
flowchart TD
    Start([S3 Event Received]) --> DecodeKey[Decode S3 Key]
    DecodeKey --> ParallelFetch[Parallel Fetch:<br/>1. head_object metadata<br/>2. get_object_tagging]

    ParallelFetch --> DetermineType[Determine Asset Type<br/>content_type + file_ext]
    DetermineType --> CheckType{Asset Type in<br/>Image/Video/Audio?}

    CheckType -->|No| SkipUnsupported[Skip Processing<br/>Log: Unsupported type]
    CheckType -->|Yes| CheckTags{Has both<br/>InventoryID & AssetID<br/>tags?}

    CheckTags -->|Yes| CheckDBRecord{Record exists<br/>in DynamoDB?}

    CheckDBRecord -->|Yes| UpdateModDate[Update lastModifiedDate<br/>in DynamoDB]
    UpdateModDate --> ReturnNull1[Return None<br/>Already processed]

    CheckDBRecord -->|No| RecreateRecord[Recreate DynamoDB Record<br/>using existing IDs from tags]
    RecreateRecord --> PublishEvent1[Publish AssetCreated Event]
    PublishEvent1 --> ReturnItem1[Return recreated item]

    CheckTags -->|No| CalcMD5[Calculate MD5 Hash<br/>_calculate_md5]
    CalcMD5 --> QueryHash[Query DynamoDB<br/>FileHashIndex]

    QueryHash --> ExistingFile{Existing file<br/>with same hash?}

    ExistingFile -->|No| ProcessNew[Process New Unique File]
    ProcessNew --> CheckInventoryTag{Has InventoryID<br/>tag but no AssetID?}

    CheckInventoryTag -->|Yes| UseExistingInv[Use existing InventoryID]
    CheckInventoryTag -->|No| CreateNewInv[Create new InventoryID]

    UseExistingInv --> CreateDynamo1[create_dynamo_entry]
    CreateNewInv --> CreateDynamo1

    CreateDynamo1 --> TagS3[Tag S3 Object:<br/>InventoryID, AssetID, FileHash]
    TagS3 --> PublishEvent2[publish_event:<br/>AssetCreated]
    PublishEvent2 --> ReturnEntry[Return DynamoDB entry]

    ExistingFile -->|Yes| SameKey{Same object key<br/>as existing?}

    SameKey -->|Yes| AlwaysSkip[ALWAYS SKIP<br/>Same hash + same key]
    AlwaysSkip --> TagExisting[Tag with existing IDs]
    TagExisting --> UpdateModDate2[Update lastModifiedDate]
    UpdateModDate2 --> ReturnNull2[Return None]

    SameKey -->|No| CheckDupSetting{DO_NOT_INGEST<br/>_DUPLICATES?}

    CheckDupSetting -->|False| ProcessNew

    CheckDupSetting -->|True| HasPartialTags{Has InventoryID<br/>but no AssetID?}

    HasPartialTags -->|Yes| GenNewAsset[Generate new AssetID<br/>under existing InventoryID]
    GenNewAsset --> TagNewAsset[Tag S3 with:<br/>existing InventoryID<br/>new AssetID<br/>FileHash]
    TagNewAsset --> CreateMetadata1[Create asset metadata]
    CreateMetadata1 --> CreateDynamo2[create_dynamo_entry<br/>with existing InventoryID]
    CreateDynamo2 --> PublishEvent3[publish_event]
    PublishEvent3 --> ReturnEntry2[Return DynamoDB entry]

    HasPartialTags -->|No| HasNoTags{Has NO tags<br/>at all?}

    HasNoTags -->|Yes| CheckStoragePath{Same storage path<br/>as existing record?}

    CheckStoragePath -->|Yes| TagDuplicate[Tag with existing IDs<br/>+ DuplicateHash tag]
    TagDuplicate --> UpdateModDate3[Update lastModifiedDate]
    UpdateModDate3 --> ReturnNull3[Return None]

    CheckStoragePath -->|No| HandleMove[File Moved/Renamed:<br/>Delete old S3 object]
    HandleMove --> UpdateRecord[Update DynamoDB:<br/>- New StoragePath<br/>- New StorageInfo<br/>- New Metadata<br/>- lastModifiedDate]
    UpdateRecord --> TagNewLocation[Tag new S3 object<br/>with existing IDs]
    TagNewLocation --> PublishMoveEvent[Publish AssetCreated event<br/>for location change]
    PublishMoveEvent --> ReturnNull5[Return None]

    HasNoTags -->|No| TagSameInv[Tag with:<br/>same InventoryID<br/>new AssetID<br/>DuplicateHash tag]
    TagSameInv --> ReturnNull4[Return None<br/>Tagged only]

    SkipUnsupported --> End([End])
    ReturnNull1 --> End
    ReturnItem1 --> End
    ReturnEntry --> End
    ReturnNull2 --> End
    ReturnEntry2 --> End
    ReturnNull3 --> End
    ReturnNull4 --> End
    ReturnNull5 --> End

    style Start fill:#e1f5e1
    style End fill:#ffe1e1
    style CheckType fill:#fff4e1
    style CheckTags fill:#fff4e1
    style CheckDBRecord fill:#fff4e1
    style ExistingFile fill:#fff4e1
    style SameKey fill:#fff4e1
    style CheckDupSetting fill:#fff4e1
    style HasPartialTags fill:#fff4e1
    style HasNoTags fill:#fff4e1
    style CheckInventoryTag fill:#fff4e1
    style CheckStoragePath fill:#fff4e1
    style SkipUnsupported fill:#ffcccc
    style AlwaysSkip fill:#ffffcc
    style ProcessNew fill:#ccffcc
    style HandleMove fill:#cce5ff
```

## Key Decision Points

### 1. Asset Type Check

- **Location**: Lines 674-698
- **Purpose**: Only process Image, Video, or Audio assets
- **Action**: Skip processing for "Other" types

### 2. Existing Tags Check

- **Location**: Lines 703-866
- **Purpose**: Fast path for already-processed assets
- **Actions**:
  - If DB record exists: Update `lastModifiedDate` only
  - If DB record missing: Recreate record with existing IDs

### 3. Duplicate Hash Detection

- **Location**: Lines 869-1067
- **Purpose**: Detect files with same content (MD5 hash)
- **Key Logic**:
  - Same hash + same key = ALWAYS skip (regardless of settings)
  - Same hash + different key = Depends on `DO_NOT_INGEST_DUPLICATES`

### 4. DO_NOT_INGEST_DUPLICATES Setting

- **Location**: Lines 47-49, 938-1067
- **Purpose**: Control duplicate asset handling
- **Behaviors**:
  - `True`: Apply duplicate prevention logic (tag only, share InventoryID)
  - `False`: Create separate assets even with same hash

### 5. Inventory ID Handling

- **Location**: Lines 943-992, 1073-1084
- **Purpose**: Support grouping assets under same inventory
- **Logic**: If object has `InventoryID` tag but no `AssetID`, generate new AssetID under existing inventory

## Function Call Hierarchy

```mermaid
flowchart LR
    handler --> process_records_in_parallel
    process_records_in_parallel --> process_s3_event
    process_s3_event --> process_asset
    process_s3_event --> delete_asset

    process_asset --> _decode_s3_event_key
    process_asset --> _extract_file_extension
    process_asset --> determine_asset_type
    process_asset --> _calculate_md5
    process_asset --> _check_existing_file
    process_asset --> _create_asset_metadata
    process_asset --> create_dynamo_entry
    process_asset --> publish_event

    delete_asset --> _should_process_deletion
    delete_asset --> _delete_associated_s3_files
    delete_asset --> delete_opensearch_docs
    delete_asset --> delete_s3_vectors
    delete_asset --> publish_deletion_event

    create_dynamo_entry --> get_type_abbreviation
    create_dynamo_entry --> determine_asset_type

    style handler fill:#e1e1ff
    style process_asset fill:#ffe1e1
    style delete_asset fill:#ffe1e1
```

## Configuration Impact

### DO_NOT_INGEST_DUPLICATES = True (Default)

- Same content uploaded to different paths gets same `InventoryID`
- New `AssetID` generated for each unique path
- Tagged with `DuplicateHash` flag
- **Use case**: Prevent duplicate processing pipelines

### DO_NOT_INGEST_DUPLICATES = False

- Each upload creates completely separate asset
- Different `InventoryID` and `AssetID`
- Full processing for each copy
- **Use case**: Track each file instance independently

## Special Cases

### Same Hash + Same Key

- **Always skipped** regardless of `DO_NOT_INGEST_DUPLICATES`
- Only updates `lastModifiedDate`
- Represents exact same file (no change)

### Tagged Object Missing from DB

- **Recreates** DynamoDB record using existing tags
- Preserves original IDs for consistency
- Publishes `AssetCreated` event for downstream systems

### Object with Partial Tags

- InventoryID exists, AssetID missing
- Generates new AssetID under existing inventory
- Creates full asset entry with metadata

### File Moved/Renamed (New in this update)

- **Trigger**: Same hash, no tags, but different storage path from DB record
- **Actions**:
  1. Deletes old S3 object at previous location
  2. Updates DynamoDB record with new storage path and metadata
  3. Tags new S3 object with existing InventoryID and AssetID
  4. Publishes `AssetCreated` event to notify about location change
- **Use case**: Handles files that have been moved or renamed in S3
- **Metrics**: `OldObjectsDeleted`, `RecordsUpdatedWithNewPath`
- **Location**: Lines 994-1129 in `process_asset` method
