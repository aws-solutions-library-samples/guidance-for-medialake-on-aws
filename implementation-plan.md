# Implementation Plan: Fix PipelinesPage Freezing Issue

## Problem Description

When clicking the Pipeline sidebar ListItemButton twice after the pipeline table is loaded with data, the page freezes indefinitely. This issue:
- Only affects the Pipelines page
- Only happens after data is loaded
- Causes an indefinite freeze without errors
- Happens consistently every time

## Root Cause Analysis

The issue is likely related to how the PipelinesPage component handles re-rendering when navigating to the same route after data is loaded. Potential causes include:

1. Inefficient React Query configuration causing unnecessary refetching
2. Excessive re-renders due to lack of memoization
3. Issues with the virtualization library when re-rendering with data already loaded
4. Performance bottlenecks in data processing or rendering

## Implementation Plan

### 1. Optimize React Query Configuration

Modify `pipelinesController.ts` to prevent unnecessary refetching:

```typescript
export const useGetPipelines = (
    options?: Omit<UseQueryOptions<PipelinesResponse, PipelineError>, 'queryKey' | 'queryFn'>
) => {
    return useQuery({
        queryKey: PIPELINES_QUERY_KEYS.list(),
        queryFn: () => PipelinesService.getPipelines(),
        // Add these optimizations:
        staleTime: 5 * 60 * 1000, // 5 minutes
        cacheTime: 10 * 60 * 1000, // 10 minutes
        refetchOnWindowFocus: false,
        refetchOnMount: false,
        ...options
    });
};
```

### 2. Optimize PipelinesPage Component

Update `PipelinesPage.tsx` to add memoization and prevent unnecessary re-renders:

```typescript
// 1. Memoize the tableActions object
const tableActions: TableActions = useMemo(() => ({
    setPagination: (pagination) => setTableState(prev => ({ ...prev, pagination })),
    setGlobalFilter: (filter) => setTableState(prev => ({ ...prev, globalFilter: filter })),
    setColumnFilters: (filters) => setTableState(prev => ({ ...prev, columnFilters: filters })),
    setColumnVisibility: (visibility) => setTableState(prev => ({ ...prev, columnVisibility: visibility })),
    handleCloseSnackbar: () => setTableState(prev => ({ ...prev, snackbar: { ...prev.snackbar, open: false } })),
    handleEdit: useCallback(async (id) => {
        // Existing code...
    }, [navigate, setApiStatus, t]),
    openDeleteDialog: useCallback((id, name) => {
        // Existing code...
    }, []),
    closeDeleteDialog: useCallback(() => setTableState(prev => ({
        ...prev,
        deleteDialog: { ...prev.deleteDialog, open: false },
    })), []),
    handleColumnMenuOpen: useCallback((event) => setTableState(prev => ({
        ...prev,
        columnMenuAnchor: event.currentTarget,
    })), []),
    handleColumnMenuClose: useCallback(() => setTableState(prev => ({
        ...prev,
        columnMenuAnchor: null,
    })), []),
    handleFilterMenuOpen: useCallback((event, columnId) => setTableState(prev => ({
        ...prev,
        filterMenuAnchor: event.currentTarget,
        activeFilterColumn: columnId,
    })), []),
    handleFilterMenuClose: useCallback(() => setTableState(prev => ({
        ...prev,
        filterMenuAnchor: null,
        activeFilterColumn: null,
    })), []),
    setDeleteDialogInput: useCallback((input) => setTableState(prev => ({
        ...prev,
        deleteDialog: { ...prev.deleteDialog, userInput: input },
    })), []),
}), [navigate, setApiStatus, t]);

// 2. Memoize the handleDeletePipeline function
const handleDeletePipeline = useCallback(async (id: string) => {
    // Existing code...
}, [deletePipeline, t]);
```

### 3. Optimize PipelineTable Component

Wrap the PipelineTable component with React.memo to prevent unnecessary re-renders:

```typescript
// In PipelineTable.tsx
export const PipelineTable: React.FC<PipelineTableProps> = React.memo(({
    data,
    isLoading,
    tableState,
    tableActions,
    onStartPipeline,
    onStopPipeline
}) => {
    // Existing code...
});
```

### 4. Add Virtualization Safeguards

Add checks to ensure the virtualization library doesn't cause issues when re-rendering:

```typescript
// In PipelineTable.tsx
const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => 53,
    overscan: 20,
    // Add this to prevent issues when re-rendering:
    getItemKey: (index) => rows[index]?.original?.id || index,
});
```

### 5. Add Performance Monitoring

Enhance the existing performance monitoring to help identify the exact cause of the freeze:

```typescript
// In PipelinesPage.tsx
useEffect(() => {
    logPerf('PipelinesPage mounted', perfMarks.current.pageLoad);

    // Log memory usage if available (Chrome only)
    const performanceWithMemory = window.performance as any;
    if (performanceWithMemory.memory) {
        const memoryInfo = performanceWithMemory.memory;
        console.log('[PERF-PAGE] Initial memory usage:', {
            totalJSHeapSize: Math.round(memoryInfo.totalJSHeapSize / (1024 * 1024)) + ' MB',
            usedJSHeapSize: Math.round(memoryInfo.usedJSHeapSize / (1024 * 1024)) + ' MB'
        });
    }

    // Add this to monitor re-renders
    console.log('[PERF-PAGE] PipelinesPage render with data:', {
        pipelinesCount: pipelines?.length || 0,
        isLoading,
        hasError: !!error
    });

    return () => {
        logPerf('PipelinesPage unmounting');
    };
}, [pipelines, isLoading, error]);
```

## Implementation Steps

1. Switch to Code mode to implement these changes
2. Start with the React Query optimizations in pipelinesController.ts
3. Then add memoization to the PipelinesPage component
4. Add the virtualization safeguards to the PipelineTable component
5. Test the solution by clicking the Pipeline sidebar item after the table is loaded

## Expected Outcome

After implementing these changes, the page should no longer freeze when clicking the Pipeline sidebar item after the table is loaded with data. The optimizations will:

1. Prevent unnecessary data refetching
2. Reduce the number of re-renders
3. Ensure the virtualization library handles re-renders properly
4. Provide better performance monitoring to identify any remaining issues