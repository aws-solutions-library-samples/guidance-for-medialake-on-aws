# Video Asset Card Performance Optimization

## Overview

Optimizations applied to `AssetCard.tsx` to improve rendering performance for video assets in search results and collections.

## Key Optimizations

### 1. Multi-Threaded/Parallel Loading

- **Staggered Initialization**: Random 0-100ms delay spreads out video player initialization across frames
- **requestIdleCallback**: Defers marker creation to idle periods, preventing main thread blocking
- **Batch Video Loading**: IntersectionObserver triggers loading in batches as cards become visible

### 2. Improved Lazy Loading

#### IntersectionObserver Configuration

```typescript
{
  rootMargin: "400px",  // Increased from 200px - start loading earlier
  threshold: 0.01,      // Very low threshold - trigger as soon as visible
}
```

Benefits:

- Loads videos **before** they enter viewport (400px margin)
- Smoother scrolling experience
- Reduces perceived loading time

### 3. Deferred Marker Creation

- Markers (clip boundaries) created in `requestIdleCallback` after video loads
- Video starts playing immediately without waiting for markers
- Markers added when browser is idle, not blocking playback

### 4. Reduced Main Thread Blocking

- Video initialization happens asynchronously
- Heavy operations (marker calculation, timecode conversion) deferred
- Player creation doesn't block card rendering

### 5. Query Caching Improvements

Enhanced TanStack Query caching for video assets:

```typescript
// Video Assets
staleTime: 30 minutes
gcTime: 1 hour
refetchOnMount: false
refetchOnWindowFocus: false

// Search Results
staleTime: 10 minutes
gcTime: 30 minutes
```

Benefits:

- Videos cached across page navigations
- No refetch when returning to previous searches
- Proxy URLs cached and shared between search/detail views

## Performance Metrics

### Before Optimization

- All videos tried to initialize simultaneously
- Markers created synchronously during video load
- Main thread blocked during heavy operations
- Videos refetched on every page visit

### After Optimization

- Videos initialize in staggered batches
- Markers created during idle time
- Main thread remains responsive
- Videos cached for 30-60 minutes

## Implementation Details

### Video Loading Flow

1. **Card Renders** → Minimal work, just DOM structure
2. **IntersectionObserver Triggers** → When card is near viewport (+400px)
3. **Random Delay** → 0-100ms stagger to spread load
4. **Player Init** → Omakase player created asynchronously
5. **Video Load Starts** → Video begins loading/buffering
6. **requestIdleCallback** → Waits for idle period
7. **Markers Created** → Clip markers added without blocking

### Query Key Strategy

- **Asset Details**: Keyed by `inventoryId` → Shared across all views
- **Search Results**: Keyed by query+params → Cached per search
- **Cross-Page Benefit**: Same video in search results and detail page uses same cache

## Browser Compatibility

- `requestIdleCallback`: Supported in all modern browsers
- Polyfill: Falls back to `setTimeout` if not available
- IntersectionObserver: Widely supported (since 2019)

## Future Optimizations

Consider if performance issues persist:

1. **Virtual Scrolling**: Only render visible cards (react-window/react-virtuoso)
2. **Web Workers**: Move marker calculations off main thread entirely
3. **Service Workers**: Cache video segments for offline playback
4. **Thumbnail Sprites**: Show video thumbnails without loading full video

## Configuration

Tunable parameters in `AssetCard.tsx`:

- `rootMargin: "400px"` - How far ahead to load
- `Math.random() * 100` - Max stagger delay
- Video quality settings in Omakase player config
