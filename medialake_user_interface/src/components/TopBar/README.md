# Semantic Mode Toggle

## Overview

The `SemanticModeToggle` component provides a toggle interface for switching between "Full" and "Clip" modes when semantic search is enabled.

## Features

- **Conditional Visibility**: Only appears when semantic search is active
- **Two Modes**:
  - `full`: Full semantic search mode
  - `clip`: Clip-based semantic search mode
- **State Management**: Uses Zustand store for state persistence
- **Theme Support**: Adapts to light/dark theme

## Usage

The toggle automatically appears inside the search bar when the user enables semantic search by clicking the "Semantic" button.

## State Management

The component uses the following store hooks:

- `useSemanticMode()`: Gets the current semantic mode
- `useDomainActions()`: Provides `setSemanticMode()` action

## Implementation Details

1. **Store Updates**: Added `semanticMode` state to `searchStore.ts`
2. **Component Integration**: Integrated into `TopBar.tsx` within the search input area
3. **Styling**: Uses Material-UI components with custom theming
4. **Persistence**: State is persisted in sessionStorage via Zustand middleware

## Files Modified

- `medialake_user_interface/src/stores/searchStore.ts`: Added semantic mode state and actions
- `medialake_user_interface/src/TopBar.tsx`: Integrated the toggle component
- `medialake_user_interface/src/components/TopBar/SemanticModeToggle.tsx`: New component

## Clip Mode Implementation

When semantic mode is set to "clip", the search results are transformed to show individual clips instead of assets:

### How It Works

1. **Full Mode (Default)**: Shows one asset card per video with multiple markers for each clip
2. **Clip Mode**: Shows one asset card per clip, ranked by semantic search score

### Transformation Logic

- Each clip from all search results is extracted and becomes its own asset card
- Clips are sorted by their semantic search score (highest first)
- **Pagination Respected**: Only shows the number of clips specified by the user's page size setting
- Each clip asset shows the original video name with timestamp information
- The video player shows only the specific clip's marker
- Total results count is updated to reflect the actual number of clips available

### Files Modified for Clip Mode

- `medialake_user_interface/src/utils/clipTransformation.ts`: Core transformation logic with pagination support
- `medialake_user_interface/src/components/search/MasterResultsView.tsx`: Integration of transformation with metadata adjustment
- `medialake_user_interface/src/components/shared/AssetCard.tsx`: Updated clip interface

### Pagination Implementation

- **Efficient Caching**: Full clip transformation is cached, pagination is applied on-demand
- **Metadata Adjustment**: Total results count reflects actual clip count in clip mode
- **Performance Optimized**: Only transforms clips once, applies pagination to cached results
- **Memory Management**: Cache size is limited to prevent memory leaks

## Future Enhancements

The semantic mode state is now available throughout the application and can be used to:

- Modify search API calls based on the selected mode
- Update result presentation logic
- Customize UI elements based on the active mode
- Implement different ranking algorithms for clip vs full mode
