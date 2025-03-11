# Implementation Plan: Fix Delete Pipeline Freezing Issue

## Problem Description

When clicking the delete icon in the pipelines table, the UI freezes immediately and does not recover. This happens with all pipelines and no console errors are observed. The issue is likely in the `handleDirectDelete` function in PipelinesPage.tsx, which is triggered when clicking the delete button in the table.

## Root Cause Analysis

After examining the code, I've identified several potential causes for the UI freezing:

1. **Synchronous State Updates**: The `handleDirectDelete` function makes multiple synchronous state updates that could block the UI thread.

2. **Modal Rendering**: The `ApiStatusModal` is shown immediately when the delete operation starts, which could cause rendering issues.

3. **React State Update Batching**: Multiple state updates in rapid succession might not be properly batched by React, causing excessive re-renders.

4. **Event Handler Blocking**: The click event handler might be blocking the main thread while waiting for the API call to complete.

5. **Missing Async/Await Pattern**: The function might not be properly implementing the async/await pattern, causing the UI thread to block.

## Implementation Plan

### 1. Refactor the handleDirectDelete Function

The current implementation of `handleDirectDelete` has several issues that could cause UI freezing. We need to refactor it to ensure it doesn't block the UI thread:

```typescript
// Current problematic implementation
const handleDirectDelete = useCallback(async (id, name) => {
    // If deletion is already in progress, do nothing
    if (isDeletingInProgress) {
        return;
    }
    
    // Set deletion in progress
    setIsDeletingInProgress(true);
    
    // Show loading modal
    setApiStatus({
        open: true,
        status: 'loading',
        action: `Deleting pipeline "${name}"...`,
        message: ''
    });
    
    try {
        // Call the deletePipeline function
        await deletePipeline(id);
        
        // Show success modal
        setApiStatus({
            open: true,
            status: 'success',
            action: 'Pipeline deleted successfully',
            message: `The pipeline "${name}" has been deleted.`
        });
        
        // Auto-close the success modal after 2 seconds
        setTimeout(() => {
            setApiStatus(prev => ({ ...prev, open: false }));
        }, 2000);
        
    } catch (error) {
        console.error(`Error deleting pipeline ${id}:`, error);
        
        // Show error modal
        setApiStatus({
            open: true,
            status: 'error',
            action: 'Error deleting pipeline',
            message: error instanceof Error ? error.message : 'An unknown error occurred'
        });
    } finally {
        // Reset deletion in progress
        setIsDeletingInProgress(false);
    }
}, [deletePipeline, isDeletingInProgress]);
```

### 2. Implement a Non-Blocking Approach

We'll refactor the `handleDirectDelete` function to use a non-blocking approach:

```typescript
// Improved implementation
const handleDirectDelete = useCallback(async (id, name) => {
    // If deletion is already in progress, do nothing
    if (isDeletingInProgress) {
        return;
    }
    
    // Use requestAnimationFrame to ensure UI updates before proceeding
    requestAnimationFrame(() => {
        // Set deletion in progress in the next frame
        setIsDeletingInProgress(true);
        
        // Show loading modal in the next frame
        setTimeout(() => {
            setApiStatus({
                open: true,
                status: 'loading',
                action: `Deleting pipeline "${name}"...`,
                message: ''
            });
        }, 0);
        
        // Use Promise to handle the deletion asynchronously
        Promise.resolve()
            .then(() => deletePipeline(id))
            .then(() => {
                // Show success modal
                setApiStatus({
                    open: true,
                    status: 'success',
                    action: 'Pipeline deleted successfully',
                    message: `The pipeline "${name}" has been deleted.`
                });
                
                // Auto-close the success modal after 2 seconds
                setTimeout(() => {
                    setApiStatus(prev => ({ ...prev, open: false }));
                }, 2000);
            })
            .catch(error => {
                console.error(`Error deleting pipeline ${id}:`, error);
                
                // Show error modal
                setApiStatus({
                    open: true,
                    status: 'error',
                    action: 'Error deleting pipeline',
                    message: error instanceof Error ? error.message : 'An unknown error occurred'
                });
            })
            .finally(() => {
                // Reset deletion in progress
                setIsDeletingInProgress(false);
            });
    });
}, [deletePipeline, isDeletingInProgress]);
```

### 3. Use React's State Batching More Effectively

React 18 introduced automatic batching of state updates, but we can make it more explicit:

```typescript
// Using React's batched updates more effectively
const handleDirectDelete = useCallback(async (id, name) => {
    // If deletion is already in progress, do nothing
    if (isDeletingInProgress) {
        return;
    }
    
    // Set deletion in progress without blocking
    setIsDeletingInProgress(true);
    
    // Defer showing the modal to the next tick to allow UI to update
    setTimeout(() => {
        setApiStatus({
            open: true,
            status: 'loading',
            action: `Deleting pipeline "${name}"...`,
            message: ''
        });
        
        // Perform deletion in a separate tick
        setTimeout(async () => {
            try {
                await deletePipeline(id);
                
                // Batch these updates together
                setApiStatus({
                    open: true,
                    status: 'success',
                    action: 'Pipeline deleted successfully',
                    message: `The pipeline "${name}" has been deleted.`
                });
                
                // Auto-close the success modal after 2 seconds
                setTimeout(() => {
                    setApiStatus(prev => ({ ...prev, open: false }));
                }, 2000);
            } catch (error) {
                console.error(`Error deleting pipeline ${id}:`, error);
                
                setApiStatus({
                    open: true,
                    status: 'error',
                    action: 'Error deleting pipeline',
                    message: error instanceof Error ? error.message : 'An unknown error occurred'
                });
            } finally {
                setIsDeletingInProgress(false);
            }
        }, 0);
    }, 0);
}, [deletePipeline, isDeletingInProgress]);
```

### 4. Add a Timeout Mechanism

Add a timeout mechanism to ensure the UI doesn't freeze indefinitely:

```typescript
// Add a timeout mechanism
const handleDirectDelete = useCallback(async (id, name) => {
    // If deletion is already in progress, do nothing
    if (isDeletingInProgress) {
        return;
    }
    
    // Set deletion in progress
    setIsDeletingInProgress(true);
    
    // Show loading modal with a slight delay to allow UI to update
    setTimeout(() => {
        setApiStatus({
            open: true,
            status: 'loading',
            action: `Deleting pipeline "${name}"...`,
            message: ''
        });
    }, 10);
    
    // Set a timeout to force reset if the operation takes too long
    const timeoutId = setTimeout(() => {
        console.warn(`Delete operation for pipeline ${id} timed out after 30 seconds`);
        setIsDeletingInProgress(false);
        setApiStatus({
            open: true,
            status: 'error',
            action: 'Error deleting pipeline',
            message: 'The operation timed out. Please try again.'
        });
    }, 30000);
    
    try {
        // Perform the deletion in a non-blocking way
        await new Promise(resolve => setTimeout(resolve, 0));
        await deletePipeline(id);
        
        // Clear the timeout since the operation completed
        clearTimeout(timeoutId);
        
        // Show success modal
        setApiStatus({
            open: true,
            status: 'success',
            action: 'Pipeline deleted successfully',
            message: `The pipeline "${name}" has been deleted.`
        });
        
        // Auto-close the success modal after 2 seconds
        setTimeout(() => {
            setApiStatus(prev => ({ ...prev, open: false }));
        }, 2000);
    } catch (error) {
        // Clear the timeout since the operation completed (with an error)
        clearTimeout(timeoutId);
        
        console.error(`Error deleting pipeline ${id}:`, error);
        
        // Show error modal
        setApiStatus({
            open: true,
            status: 'error',
            action: 'Error deleting pipeline',
            message: error instanceof Error ? error.message : 'An unknown error occurred'
        });
    } finally {
        // Reset deletion in progress
        setIsDeletingInProgress(false);
    }
}, [deletePipeline, isDeletingInProgress]);
```

### 5. Final Optimized Implementation

Combining the best practices from the above approaches:

```typescript
// Final optimized implementation
const handleDirectDelete = useCallback(async (id, name) => {
    // If deletion is already in progress, do nothing
    if (isDeletingInProgress) {
        return;
    }
    
    // Set deletion in progress
    setIsDeletingInProgress(true);
    
    // Use a microtask to allow the UI to update before showing the modal
    queueMicrotask(() => {
        // Show loading modal
        setApiStatus({
            open: true,
            status: 'loading',
            action: `Deleting pipeline "${name}"...`,
            message: ''
        });
    });
    
    // Set a timeout to force reset if the operation takes too long
    const timeoutId = setTimeout(() => {
        console.warn(`Delete operation for pipeline ${id} timed out after 30 seconds`);
        setIsDeletingInProgress(false);
        setApiStatus({
            open: true,
            status: 'error',
            action: 'Error deleting pipeline',
            message: 'The operation timed out. Please try again.'
        });
    }, 30000);
    
    try {
        // Use a separate microtask for the deletion to ensure UI responsiveness
        await new Promise(resolve => setTimeout(resolve, 0));
        await deletePipeline(id);
        
        // Clear the timeout since the operation completed
        clearTimeout(timeoutId);
        
        // Show success modal
        setApiStatus({
            open: true,
            status: 'success',
            action: 'Pipeline deleted successfully',
            message: `The pipeline "${name}" has been deleted.`
        });
        
        // Auto-close the success modal after 2 seconds
        setTimeout(() => {
            setApiStatus(prev => ({ ...prev, open: false }));
        }, 2000);
    } catch (error) {
        // Clear the timeout since the operation completed (with an error)
        clearTimeout(timeoutId);
        
        console.error(`Error deleting pipeline ${id}:`, error);
        
        // Show error modal
        setApiStatus({
            open: true,
            status: 'error',
            action: 'Error deleting pipeline',
            message: error instanceof Error ? error.message : 'An unknown error occurred'
        });
    } finally {
        // Reset deletion in progress
        setIsDeletingInProgress(false);
    }
}, [deletePipeline, isDeletingInProgress]);
```

## Implementation Steps

1. Switch to Code mode to implement these changes
2. Replace the current `handleDirectDelete` function with the optimized version
3. Test the solution by clicking the delete icon in the pipelines table
4. Verify that the UI remains responsive during the deletion process
5. Ensure that the success/error modals are displayed correctly
6. Verify that the deletion operation completes successfully

## Expected Outcome

After implementing these changes, the page should no longer freeze when clicking the delete icon in the pipelines table. The optimizations will:

1. Ensure the UI thread remains responsive during the deletion process
2. Prevent multiple delete operations from being triggered simultaneously
3. Provide clear feedback to the user about the operation status
4. Handle errors and timeouts gracefully
5. Improve overall performance and stability

## Flow Diagram

```mermaid
sequenceDiagram
    participant User
    participant UI
    participant React
    participant API
    
    User->>UI: Click Delete Button
    UI->>React: Call handleDirectDelete
    React->>React: Check if deletion in progress
    React->>React: Set isDeletingInProgress = true
    React->>UI: Update UI (non-blocking)
    React->>UI: Show loading modal (microtask)
    React->>API: Call deletePipeline (async)
    React->>React: Start timeout (30s)
    
    alt Successful deletion
        API->>React: Return success
        React->>React: Clear timeout
        React->>UI: Show success modal
        React->>UI: Auto-close modal after 2s
    else API Error
        API->>React: Return error
        React->>React: Clear timeout
        React->>UI: Show error modal
    else Timeout
        React->>React: Timeout triggers
        React->>UI: Show timeout error
    end
    
    React->>React: Set isDeletingInProgress = false
    React->>UI: Update UI