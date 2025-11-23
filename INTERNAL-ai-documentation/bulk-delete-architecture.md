# Bulk Delete Architecture Design

## Executive Summary

This document outlines the architecture for implementing bulk asset deletion in MediaLake, following the existing bulk download pattern with enhanced double-confirmation UX similar to pipeline deletion.

## Current State Analysis

### Existing Bulk Download Pattern

- **Selection Management**: `useAssetSelection` hook handles multi-page selection with localStorage persistence
- **Job Tracking**: Async job system with notification center polling (15-second intervals)
- **UX Flow**: Loading → Success modal → Job notification → Download link
- **Selection Scope**: Additive across pages, persisted in localStorage

### Current Delete Logic (Duplicated)

#### 1. API Delete Lambda (`lambdas/api/assets/rp_assets_id/del_assets/index.py`)

```
DELETE /api/assets/{id}
↓
1. Get asset from DynamoDB
2. Delete S3 objects (main + derived)
3. Delete DynamoDB record
4. Delete OpenSearch documents
5. Delete S3 vectors
6. Delete from external services (Coactive)
```

#### 2. Connector Delete Logic (`lambdas/ingest/s3/index.py`)

```
S3 Delete Event
↓
1. Query DynamoDB by S3 path
2. Delete associated S3 files
3. Delete DynamoDB record
4. Delete OpenSearch documents
5. Delete S3 vectors
6. Publish deletion event
```

**Problem**: Identical deletion logic exists in two places, violating DRY principle.

### Pipeline Delete Pattern

- **Confirmation**: Two-step with name typing requirement
- **UX**: Dialog → Type name → Confirm → Loading state
- **Component**: `PipelineDeleteDialog.tsx`

## Proposed Architecture

### 1. Centralized Delete Service

Create a shared asset deletion module that both API and connector can use:

```
lambdas/common_libraries/asset_deletion_service.py
```

**Core Deletion Chain**:

```python
class AssetDeletionService:
    def delete_asset(inventory_id: str, asset_data: dict = None):
        """
        Centralized asset deletion logic
        Returns: DeletionResult with success/failure details
        """
        1. Fetch asset (if not provided)
        2. Delete S3 objects
        3. Delete DynamoDB record
        4. Delete OpenSearch documents
        5. Delete S3 vectors
        6. Delete from external services
        7. Publish deletion event
        8. Return comprehensive result
```

**Benefits**:

- Single source of truth for deletion logic
- Consistent behavior across API and connector
- Easier to test and maintain
- Proper error handling and rollback capability

### 2. Bulk Delete API

Create new bulk delete endpoint following bulk download pattern:

```
POST /api/assets/bulk-delete
```

**Request Body**:

```json
{
  "assetIds": ["inventory-id-1", "inventory-id-2"],
  "confirmationToken": "bulk-delete-confirmation-text"
}
```

**Response** (Async Job):

```json
{
  "status": "success",
  "data": {
    "jobId": "delete-job-uuid",
    "status": "PENDING",
    "totalAssets": 50,
    "message": "Bulk delete job started"
  }
}
```

**Job Status Endpoint**:

```
GET /api/jobs/{jobId}
```

**Job Status Response**:

```json
{
  "jobId": "delete-job-uuid",
  "status": "IN_PROGRESS",
  "progress": {
    "total": 50,
    "completed": 25,
    "failed": 0
  },
  "results": {
    "successful": ["id1", "id2"],
    "failed": []
  }
}
```

### 3. Frontend Architecture

#### Component Structure

```
useAssetSelection (existing)
  ↓
  ├─ handleBatchDownload() ← existing
  └─ handleBatchDelete()    ← new
       ↓
BulkDeleteDialog (new)
  ├─ Asset count display
  ├─ Confirmation text input
  ├─ Warning messages
  └─ Submit → API call
       ↓
Job Tracking (existing)
  └─ Notification Center polls
```

#### New Component: BulkDeleteDialog

Based on `PipelineDeleteDialog.tsx` pattern:

```typescript
interface BulkDeleteDialogProps {
  open: boolean;
  assetCount: number;
  confirmationText: string; // "DELETE"
  selectedAssets: SelectedAsset[];
  onClose: () => void;
  onConfirm: () => void;
  onConfirmationTextChange: (text: string) => void;
  isDeleting: boolean;
}
```

**UX Flow**:

1. User selects assets (existing behavior)
2. Clicks "Delete Selected" button
3. Dialog opens with:
   - Count of selected assets
   - Warning: "This action cannot be undone"
   - Asset list preview (first 5, + N more)
   - Text field: "Type DELETE to confirm"
   - Disabled confirm button until text matches
4. User types "DELETE"
5. Confirm button enables
6. Click confirm → Loading state
7. Success → Close dialog + clear selection + show notification
8. Job notification appears in NotificationCenter

#### Modified useAssetSelection Hook

Add bulk delete capability:

```typescript
const handleBatchDelete = useCallback(async () => {
  if (selectedAssets.length === 0) {
    setModalState({
      open: true,
      status: "error",
      action: "Delete Failed",
      message: "No assets selected for deletion",
    });
    return;
  }

  setIsDeleteLoading(true);

  try {
    const assetIds = selectedAssets.map((a) => a.id);

    const response = await bulkDeleteMutation.mutateAsync({
      assetIds,
      confirmationToken: "DELETE",
    });

    if (response.data?.jobId) {
      handleClearSelection();

      setModalState({
        open: true,
        status: "success",
        action: "Delete Started",
        message: `Bulk delete started for ${selectedAssets.length} assets.`,
      });

      if (onDeleteSuccess) {
        onDeleteSuccess();
      }
    }
  } catch (error) {
    setModalState({
      open: true,
      status: "error",
      action: "Delete Failed",
      message: error.message,
    });
  } finally {
    setIsDeleteLoading(false);
  }
}, [selectedAssets, handleClearSelection, onDeleteSuccess]);
```

### 4. Backend Implementation

#### Bulk Delete Lambda Handler

```python
# lambdas/api/assets/bulk_delete/index.py

@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """
    Initiates async bulk delete job
    """
    body = json.loads(event['body'])
    asset_ids = body['assetIds']
    confirmation = body.get('confirmationToken')

    # Validate confirmation
    if confirmation != "DELETE":
        return error_response(400, "Invalid confirmation token")

    # Validate permissions for all assets
    for asset_id in asset_ids:
        if not has_delete_permission(user_id, asset_id):
            return error_response(403, f"No permission to delete {asset_id}")

    # Create job in DynamoDB
    job_id = str(uuid.uuid4())
    job_table.put_item(Item={
        'jobId': job_id,
        'userId': user_id,
        'type': 'BULK_DELETE',
        'status': 'PENDING',
        'assetIds': asset_ids,
        'totalAssets': len(asset_ids),
        'createdAt': datetime.utcnow().isoformat()
    })

    # Trigger async processing (Step Functions or SQS)
    invoke_bulk_delete_processor(job_id, asset_ids)

    return {
        'statusCode': 200,
        'body': json.dumps({
            'jobId': job_id,
            'status': 'PENDING',
            'totalAssets': len(asset_ids)
        })
    }
```

#### Bulk Delete Processor

```python
# lambdas/api/assets/bulk_delete_processor/index.py

def process_bulk_delete(job_id: str, asset_ids: list):
    """
    Process bulk delete asynchronously
    Uses centralized AssetDeletionService
    """
    deletion_service = AssetDeletionService()
    results = {
        'successful': [],
        'failed': []
    }

    for i, asset_id in enumerate(asset_ids):
        try:
            result = deletion_service.delete_asset(asset_id)
            if result.success:
                results['successful'].append(asset_id)
            else:
                results['failed'].append({
                    'assetId': asset_id,
                    'error': result.error
                })
        except Exception as e:
            results['failed'].append({
                'assetId': asset_id,
                'error': str(e)
            })

        # Update job progress
        update_job_progress(
            job_id,
            completed=i+1,
            total=len(asset_ids),
            results=results
        )

    # Mark job complete
    complete_job(job_id, results)

    # Send notification
    publish_job_completion(job_id, results)
```

### 5. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       Frontend (React)                       │
├─────────────────────────────────────────────────────────────┤
│  AssetExplorer                                               │
│    ↓                                                          │
│  useAssetSelection                                           │
│    ├─ Selection Management (localStorage)                    │
│    ├─ handleBatchDownload() ──→ [Existing]                  │
│    └─ handleBatchDelete() ──────→ [New]                     │
│         ↓                                                     │
│  BulkDeleteDialog (new)                                      │
│    ├─ Double confirmation                                    │
│    ├─ Type "DELETE" to confirm                              │
│    └─ Submit ─────────────────────────────────────┐         │
└──────────────────────────────────────────────────┼─────────┘
                                                    │
                                                    ↓
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway + Lambda                      │
├─────────────────────────────────────────────────────────────┤
│  POST /api/assets/bulk-delete                                │
│    ↓                                                          │
│  bulk_delete_handler.py                                      │
│    ├─ Validate permissions                                   │
│    ├─ Create job in DynamoDB                                │
│    └─ Trigger async processor ────────────┐                 │
│                                            │                 │
│  GET /api/jobs/{jobId}                    │                 │
│    └─ Return job status + progress         │                 │
│                                            ↓                 │
│  bulk_delete_processor.py                                    │
│    ├─ Process each asset                                     │
│    ├─ Update job progress                                    │
│    └─ Use: AssetDeletionService ─────────┐                  │
└──────────────────────────────────────────┼──────────────────┘
                                            │
                                            ↓
┌─────────────────────────────────────────────────────────────┐
│            Shared Deletion Service (NEW)                     │
├─────────────────────────────────────────────────────────────┤
│  lambdas/common_libraries/asset_deletion_service.py          │
│                                                              │
│  class AssetDeletionService:                                 │
│    def delete_asset(inventory_id, asset_data=None):          │
│      1. Fetch asset (if needed)                             │
│      2. Delete S3 objects ────────────→ S3                  │
│      3. Delete DynamoDB ──────────────→ DynamoDB            │
│      4. Delete OpenSearch docs ───────→ OpenSearch          │
│      5. Delete S3 vectors ────────────→ S3 Vectors          │
│      6. Delete external services ─────→ Coactive, etc.      │
│      7. Publish event ────────────────→ EventBridge         │
│      8. Return result                                        │
└─────────────────────────────────────────────────────────────┘
                    ↑                       ↑
                    │                       │
         ┌──────────┴──────────┐   ┌───────┴────────┐
         │                     │   │                │
    API Delete              Connector Delete
    (single asset)          (S3 event trigger)
    - Uses shared service   - Uses shared service
    - Immediate sync        - Async event-driven
```

### 6. Sequence Diagram: Bulk Delete Flow

```
User          Frontend       API Gateway      Bulk Delete      Deletion      DynamoDB     S3/OpenSearch
                                              Handler          Service
 │                │              │               │              │              │              │
 │ Select Assets  │              │               │              │              │              │
 │───────────────→│              │               │              │              │              │
 │                │              │               │              │              │              │
 │ Click Delete   │              │               │              │              │              │
 │───────────────→│              │               │              │              │              │
 │                │ Show Dialog  │               │              │              │              │
 │                │ Type "DELETE"│               │              │              │              │
 │←───────────────│              │               │              │              │              │
 │                │              │               │              │              │              │
 │ Confirm        │              │               │              │              │              │
 │───────────────→│              │               │              │              │              │
 │                │ POST /bulk-  │               │              │              │              │
 │                │   delete     │               │              │              │              │
 │                │─────────────→│               │              │              │              │
 │                │              │  Validate     │              │              │              │
 │                │              │  permissions  │              │              │              │
 │                │              │──────────────→│              │              │              │
 │                │              │               │  Create job  │              │              │
 │                │              │               │─────────────────────────────→│              │
 │                │              │               │              │              │              │
 │                │              │  Job created  │              │              │              │
 │                │              │  {jobId}      │              │              │              │
 │                │              │←──────────────│              │              │              │
 │                │  Success     │               │              │              │              │
 │                │  {jobId}     │               │  Trigger     │              │              │
 │                │←─────────────│               │  async       │              │              │
 │                │              │               │  processor   │              │              │
 │  Show success  │              │               │──────────────→              │              │
 │  notification  │              │               │              │              │              │
 │←───────────────│              │               │              │              │              │
 │                │              │               │              │ For each asset:             │
 │                │              │               │              │ delete_asset()              │
 │                │              │               │              │─────────────→│              │
 │                │              │               │              │              │ Delete S3    │
 │                │              │               │              │              │─────────────→│
 │                │              │               │              │              │ Delete DB    │
 │                │              │               │              │              │──────────────→
 │                │              │               │              │              │ Delete OpenSearch
 │                │              │               │              │              │─────────────→│
 │                │              │               │              │ Result       │              │
 │                │              │               │              │←─────────────│              │
 │                │              │               │              │ Update       │              │
 │                │              │               │              │ job progress │              │
 │                │              │               │              │─────────────────────────────→
 │                │              │               │              │              │              │
 │ Poll for job   │              │               │              │              │              │
 │ status (15s)   │              │               │              │              │              │
 │                │ GET /jobs/{id}               │              │              │              │
 │                │─────────────→│               │              │              │              │
 │                │ Job progress │               │              │              │              │
 │                │←─────────────│               │              │              │              │
 │                │              │               │              │              │              │
 │ Show progress  │              │               │  Complete    │              │              │
 │ notification   │              │               │  job         │              │              │
 │←───────────────│              │               │──────────────→              │              │
 │                │              │               │              │ Mark         │              │
 │                │              │               │              │ complete     │              │
 │                │              │               │              │─────────────────────────────→
```

## Implementation Plan

### Phase 1: Centralized Delete Service (Week 1)

1. Create `asset_deletion_service.py` in common_libraries
2. Extract deletion logic from API lambda
3. Extract deletion logic from connector lambda
4. Add comprehensive error handling and logging
5. Add unit tests for deletion service

### Phase 2: Bulk Delete Backend (Week 2)

1. Create bulk delete API endpoint
2. Create job management in DynamoDB
3. Implement async processor (Step Functions or Lambda)
4. Add progress tracking
5. Add job status endpoint
6. Integration tests

### Phase 3: Frontend Components (Week 2-3)

1. Create `BulkDeleteDialog` component
2. Extend `useAssetSelection` hook
3. Add delete button to asset selection panel
4. Wire up API calls
5. Add job tracking to NotificationCenter
6. UI/UX testing

### Phase 4: Refactor Existing (Week 3)

1. Update API delete lambda to use shared service
2. Update connector delete to use shared service
3. Deprecate duplicated code
4. End-to-end testing

## Security Considerations

1. **Permission Validation**: Check delete permissions for EACH asset before job creation
2. **Rate Limiting**: Limit bulk operations per user (e.g., max 1000 assets per job)
3. **Audit Logging**: Log all bulk delete operations with user ID, timestamp, asset IDs
4. **Soft Delete Option**: Consider adding soft delete capability for recovery
5. **Confirmation Token**: Require "DELETE" text confirmation to prevent accidental deletions

## Error Handling

1. **Partial Failures**: Track which assets succeeded/failed
2. **Job Rollback**: Consider implementing rollback for failed jobs
3. **User Notification**: Show detailed results (X succeeded, Y failed)
4. **Retry Logic**: Allow retry for failed deletions
5. **Cleanup**: Ensure orphaned resources are cleaned up

## Performance Considerations

1. **Batch Processing**: Process deletions in batches of 10-20
2. **Concurrency**: Use concurrent deletion where safe
3. **Timeout Handling**: Set appropriate timeouts for long-running jobs
4. **Progress Updates**: Update job status every N deletions (not per asset)
5. **Resource Limits**: Monitor Lambda concurrency and DynamoDB throughput

## Testing Strategy

1. **Unit Tests**: Test deletion service with mocked dependencies
2. **Integration Tests**: Test full deletion chain
3. **Load Tests**: Test bulk deletion with varying sizes (10, 100, 1000 assets)
4. **Failure Tests**: Test partial failures and rollback
5. **UI Tests**: Test confirmation flow and progress display

## Monitoring & Metrics

Track the following metrics:

- Bulk delete jobs initiated
- Average job completion time
- Success/failure rates
- Assets deleted per job (histogram)
- Errors by type
- API latency

## Future Enhancements

1. **Scheduled Deletion**: Allow scheduling bulk deletes for later
2. **Soft Delete**: Move to trash before permanent deletion
3. **Undo Capability**: 30-day recovery window
4. **Export Before Delete**: Option to export metadata before deletion
5. **Smart Selection**: "Select all matching search results"
