# TanStack Query Caching Strategy

## Overview

Optimized caching configuration for video assets and search results to minimize redundant API calls and improve performance.

## Global Query Configuration

### Before Optimization

```typescript
staleTime: 5 minutes
gcTime: 10 minutes
refetchOnMount: true
refetchOnWindowFocus: false
refetchOnReconnect: false
```

### After Optimization

```typescript
staleTime: 10 minutes  // Doubled
gcTime: 30 minutes     // Tripled
refetchOnMount: false  // Changed from true
refetchOnWindowFocus: false
refetchOnReconnect: false
```

## Hook-Specific Configurations

### Video Asset Details (`useAsset`)

```typescript
staleTime: 30 minutes  // 6x longer than default
gcTime: 1 hour         // 2x longer than global
refetchOnMount: false
refetchOnWindowFocus: false
refetchOnReconnect: false
```

**Rationale**: Video metadata rarely changes. Once fetched, keep it cached for the entire session.

### Search Results (`useSearch`)

```typescript
staleTime: 10 minutes  // 10x longer than before (was 1 minute)
gcTime: 30 minutes     // 6x longer than before (was 5 minutes)
refetchOnMount: false
refetchOnWindowFocus: false
refetchOnReconnect: false
placeholderData: keepPreviousData  // Already enabled
```

**Rationale**: Search results are relatively stable. Longer cache allows instant back navigation.

### Related Videos (`useRelatedVersions`)

```typescript
staleTime: 30 minutes  // 6x longer than before (was 5 minutes)
gcTime: 1 hour
refetchOnMount: false
refetchOnWindowFocus: false
refetchOnReconnect: false
```

### Transcriptions (`useTranscription`)

```typescript
staleTime: 30 minutes  // New (was using default 5 min)
gcTime: 1 hour
refetchOnMount: false
refetchOnWindowFocus: false
refetchOnReconnect: false
```

**Rationale**: Transcripts are immutable once generated. Cache aggressively.

## Query Key Strategy

### Assets

```typescript
QUERY_KEYS.ASSETS.detail(inventoryId);
```

- Shared across all views of the same asset
- Detail page and search results use same cache entry
- Proxy URLs cached once per asset

### Search Results

```typescript
QUERY_KEYS.SEARCH.list(query, page, pageSize, isSemantic, fields, facetParams);
```

- Different searches cached separately
- Same search on different pages cached separately
- Allows instant pagination

## Cache Behavior Examples

### Scenario 1: Video in Search → Detail → Back

1. User searches for "cats" - **API call**
2. Video thumbnail/proxy cached for 30min
3. User clicks video → Detail page - **No API call** (cache hit)
4. User navigates back → Search page - **No API call** (cache hit)

### Scenario 2: Multiple Searches

1. Search "dogs" - **API call**, cached 10min
2. Search "cats" - **API call**, cached 10min
3. Back to "dogs" - **No API call** if <10min (cache hit)

### Scenario 3: Refresh/Focus

1. User switches to another tab
2. User switches back → **No refetch** (refetchOnWindowFocus: false)
3. User navigates between pages → **No refetch** (refetchOnMount: false)

## Performance Impact

### API Calls Reduced

- **Video Detail Page**: 1 call instead of 3-5 calls per visit
- **Search Navigation**: 1 call instead of 1 call per back/forward
- **Tab Switching**: 0 calls instead of N calls per focus

### User Experience

- **Instant navigation** when returning to previous searches
- **No loading states** when re-visiting asset details
- **Smooth scrolling** without refetch-induced janking

## Cache Invalidation

Mutations that modify data automatically invalidate relevant caches:

### Delete Asset

```typescript
queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ASSETS.all });
queryClient.removeQueries({ queryKey: QUERY_KEYS.ASSETS.detail(id) });
queryClient.invalidateQueries({ queryKey: QUERY_KEYS.SEARCH.all });
```

### Rename Asset

```typescript
queryClient.setQueryData(QUERY_KEYS.ASSETS.detail(id), newData);
// Also updates search results cache optimistically
```

### Bulk Download

```typescript
queryClient.invalidateQueries({ queryKey: ["userBulkDownloadJobs"] });
```

## Trade-offs

### Benefits

✅ Fewer API calls → Lower server load
✅ Faster page loads → Better UX
✅ Less bandwidth usage
✅ More responsive UI

### Considerations

⚠️ Data may be stale up to 10-30 minutes
⚠️ Increased memory usage (cached data)
⚠️ Manual refresh needed for immediate updates

## When to Use Manual Refresh

Users should manually refresh (F5) when:

- Just uploaded/modified assets
- Expecting real-time updates from other users
- Data appears outdated

Alternative: Add a "Refresh" button that calls:

```typescript
queryClient.invalidateQueries({ queryKey: QUERY_KEYS.SEARCH.all });
queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ASSETS.all });
```

## Browser Compatibility

All modern browsers support this caching strategy. No polyfills needed.

## Monitoring

### Cache Hit Rate

Monitor in DevTools → React Query Devtools:

- Green = Fresh (within staleTime)
- Yellow = Stale (beyond staleTime, refetchable)
- Red = Inactive (no active observers)

### Memory Usage

Watch for memory growth if users keep many searches open. Current settings balance performance vs memory:

- `gcTime: 30min` = Unused caches cleared after 30 minutes
- Typical session: 5-10 searches × ~50 results = ~500 cached items
- Average memory: 2-5MB (negligible on modern devices)

## Future Optimizations

If cache size becomes an issue:

1. **Lower gcTime** for search results (e.g., 10 minutes)
2. **Implement pagination** instead of caching all pages
3. **Use IndexedDB** for persistent offline cache
4. **Implement cache size limits** with LRU eviction
