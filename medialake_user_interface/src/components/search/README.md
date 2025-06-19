# Score Filter Component

## Overview

The Score Filter is a dedicated component that allows users to filter search results based on their relevance scores when performing semantic searches in clip mode.

## Features

- **Real-time filtering**: Filters results as the user adjusts the score threshold
- **Visual feedback**: Shows how many results are being filtered out
- **Clear functionality**: Easy way to reset the filter
- **Responsive design**: Works well on different screen sizes
- **Accessibility**: Proper ARIA labels and keyboard navigation

## Usage

The Score Filter is automatically displayed when:
1. The user is in clip mode (semantic search with clips)
2. Search results contain items with score properties

### Props

```typescript
interface ScoreFilterProps {
  value: number;                    // Current score threshold (0-1)
  onChange: (value: number) => void; // Callback when threshold changes
  onClear?: () => void;            // Optional callback when filter is cleared
  disabled?: boolean;              // Whether the filter is disabled
  showClearButton?: boolean;       // Whether to show the clear button
  label?: string;                  // Custom label for the filter
  totalResults?: number;           // Total number of results before filtering
  filteredResults?: number;        // Number of results after filtering
}
```

### Example

```tsx
<ScoreFilter
  value={scoreFilter}
  onChange={setScoreFilter}
  onClear={() => setScoreFilter(0)}
  disabled={isLoading}
  totalResults={processedResults.length}
  filteredResults={scoreFilteredResults.length}
/>
```

## Implementation Details

### Filtering Logic

The score filter works by:
1. Checking if each result has a `score` property
2. Comparing the score against the threshold value
3. Only showing results where `score >= threshold`

### State Management

The filter state is managed in the parent component (SearchPage) and passed down as props. This ensures:
- Consistent state across the application
- Proper integration with other filters
- Easy testing and debugging

### Visual States

- **Inactive**: Normal appearance with subtle styling
- **Active**: Enhanced styling with primary color border and background
- **Disabled**: Grayed out when loading or disabled

## Testing

The component includes test IDs for automated testing:
- `data-testid="score-filter"` - Main container
- `data-testid="score-filter-input"` - Input field
- `data-testid="score-filter-clear"` - Clear button

## Accessibility

- Proper ARIA labels for screen readers
- Keyboard navigation support
- Focus management
- Clear visual indicators for active state 