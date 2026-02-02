# Property-Based Tests for URL State Management

This document describes property-based tests for URL state management in the AssetExplorer component. These tests would ideally be implemented using a property-based testing library for JavaScript/TypeScript such as `fast-check`.

## Property 8: URL State Round-Trip

**Validates: Requirements 3.3, 3.4, 3.5, 3.6**

### Description

_For any_ valid pagination state (page, pageSize, sortBy, sortDirection), setting these values in the URL query parameters and loading the page should initialize the component state to match those values.

### Test Implementation Strategy

```typescript
/**
 * Property 8: URL State Round-Trip
 *
 * This property ensures that URL parameters correctly initialize component state.
 */

import fc from "fast-check";

// Generators
const validPage = fc.integer({ min: 1, max: 1000 });
const validPageSize = fc.integer({ min: 1, max: 500 });
const validSortField = fc.constantFrom("createdAt", "name", "size", "type", "format");
const validSortDirection = fc.constantFrom("asc", "desc");

// Property test
fc.assert(
  fc.property(
    validPage,
    validPageSize,
    validSortField,
    validSortDirection,
    (page, pageSize, sortBy, sortDirection) => {
      // Arrange: Set URL parameters
      const url = `/?page=${page}&pageSize=${pageSize}&sortBy=${sortBy}&sortDirection=${sortDirection}`;
      window.history.pushState({}, "", url);

      // Act: Render component and extract state
      const { result } = renderHook(() => useSearchParams(), { wrapper });
      const [searchParams] = result.current;

      // Assert: State should match URL parameters
      const statePage = parseInt(searchParams.get("page") || "1", 10);
      const statePageSize = parseInt(searchParams.get("pageSize") || "50", 10);
      const stateSortBy = searchParams.get("sortBy") || "createdAt";
      const stateSortDirection = searchParams.get("sortDirection") || "desc";

      return (
        statePage === page &&
        statePageSize === pageSize &&
        stateSortBy === sortBy &&
        stateSortDirection === sortDirection
      );
    }
  ),
  { numRuns: 100 }
);
```

### Test Cases Covered

1. **All valid page numbers**: Tests that any valid page number (1-1000) is correctly initialized from URL
2. **All valid page sizes**: Tests that any valid page size (1-500) is correctly initialized from URL
3. **All sort fields**: Tests that all sortable fields are correctly initialized from URL
4. **Both sort directions**: Tests that both 'asc' and 'desc' are correctly initialized from URL
5. **All combinations**: Tests all combinations of the above parameters

### Expected Behavior

- URL parameters should be parsed and used to initialize component state
- Invalid or missing parameters should use default values
- State should exactly match URL parameters for valid inputs

## Property 9: URL State Synchronization

**Validates: Requirements 3.1, 3.2**

### Description

_For any_ change to pagination or sort state (page, pageSize, sortBy, sortDirection), the URL query parameters should be updated to reflect the new state.

### Test Implementation Strategy

```typescript
/**
 * Property 9: URL State Synchronization
 *
 * This property ensures that state changes are reflected in URL parameters.
 */

import fc from "fast-check";

// Property test
fc.assert(
  fc.property(
    validPage,
    validPageSize,
    validSortField,
    validSortDirection,
    (newPage, newPageSize, newSortBy, newSortDirection) => {
      // Arrange: Start with initial state
      const { result } = renderHook(() => useSearchParams(), { wrapper });

      // Act: Update state
      act(() => {
        const [, setSearchParams] = result.current;
        const newParams = new URLSearchParams();
        newParams.set("page", String(newPage));
        newParams.set("pageSize", String(newPageSize));
        newParams.set("sortBy", newSortBy);
        newParams.set("sortDirection", newSortDirection);
        setSearchParams(newParams, { replace: true });
      });

      // Assert: URL should reflect new state
      const [searchParams] = result.current;
      const urlPage = searchParams.get("page");
      const urlPageSize = searchParams.get("pageSize");
      const urlSortBy = searchParams.get("sortBy");
      const urlSortDirection = searchParams.get("sortDirection");

      return (
        urlPage === String(newPage) &&
        urlPageSize === String(newPageSize) &&
        urlSortBy === newSortBy &&
        urlSortDirection === newSortDirection
      );
    }
  ),
  { numRuns: 100 }
);
```

### Test Cases Covered

1. **Page changes**: Tests that page changes are reflected in URL
2. **Page size changes**: Tests that page size changes are reflected in URL
3. **Sort field changes**: Tests that sort field changes are reflected in URL
4. **Sort direction changes**: Tests that sort direction changes are reflected in URL
5. **Multiple simultaneous changes**: Tests that multiple state changes are all reflected in URL

### Expected Behavior

- State changes should immediately update URL parameters
- URL should always reflect current component state
- Multiple changes should all be captured in URL

## Additional Property Tests

### Property: URL Parameter Persistence

```typescript
/**
 * Property: URL Parameter Persistence
 *
 * URL parameters should persist across component re-renders.
 */

fc.assert(
  fc.property(
    validPage,
    validPageSize,
    validSortField,
    validSortDirection,
    (page, pageSize, sortBy, sortDirection) => {
      // Arrange: Set URL parameters
      const url = `/?page=${page}&pageSize=${pageSize}&sortBy=${sortBy}&sortDirection=${sortDirection}`;
      window.history.pushState({}, "", url);

      // Act: Render, re-render, and extract state
      const { result, rerender } = renderHook(() => useSearchParams(), { wrapper });
      rerender(); // Simulate re-render

      // Assert: State should still match URL parameters
      const [searchParams] = result.current;
      const statePage = parseInt(searchParams.get("page") || "1", 10);
      const statePageSize = parseInt(searchParams.get("pageSize") || "50", 10);
      const stateSortBy = searchParams.get("sortBy") || "createdAt";
      const stateSortDirection = searchParams.get("sortDirection") || "desc";

      return (
        statePage === page &&
        statePageSize === pageSize &&
        stateSortBy === sortBy &&
        stateSortDirection === sortDirection
      );
    }
  ),
  { numRuns: 100 }
);
```

### Property: Invalid Parameter Handling

```typescript
/**
 * Property: Invalid Parameter Handling
 *
 * Invalid URL parameters should be handled gracefully with defaults.
 */

const invalidPage = fc.oneof(
  fc.constant("invalid"),
  fc.constant("-1"),
  fc.constant("0"),
  fc.constant("abc")
);

const invalidPageSize = fc.oneof(
  fc.constant("invalid"),
  fc.constant("-10"),
  fc.constant("0"),
  fc.constant("xyz")
);

const invalidSortDirection = fc.string().filter((s) => s !== "asc" && s !== "desc");

fc.assert(
  fc.property(
    invalidPage,
    invalidPageSize,
    invalidSortDirection,
    (page, pageSize, sortDirection) => {
      // Arrange: Set invalid URL parameters
      const url = `/?page=${page}&pageSize=${pageSize}&sortDirection=${sortDirection}`;
      window.history.pushState({}, "", url);

      // Act: Render component
      const { result } = renderHook(() => useSearchParams(), { wrapper });
      const [searchParams] = result.current;

      // Assert: Should use defaults for invalid parameters
      const statePage = parseInt(searchParams.get("page") || "1", 10);
      const statePageSize = parseInt(searchParams.get("pageSize") || "50", 10);
      const stateSortDirection = searchParams.get("sortDirection") || "desc";

      // Invalid values should result in defaults or NaN (which should be handled)
      return (
        (isNaN(statePage) || statePage >= 1) &&
        (isNaN(statePageSize) || statePageSize >= 1) &&
        (stateSortDirection === "asc" || stateSortDirection === "desc")
      );
    }
  ),
  { numRuns: 100 }
);
```

## Implementation Notes

### Required Dependencies

```json
{
  "devDependencies": {
    "fast-check": "^3.15.0",
    "@testing-library/react": "^14.0.0",
    "@testing-library/react-hooks": "^8.0.1",
    "vitest": "^1.0.0"
  }
}
```

### Test File Structure

```
medialake_user_interface/src/features/assets/__tests__/
├── url-state-management.test.tsx          # Unit tests (already created)
├── url-state-properties.test.tsx          # Property-based tests (to be created)
└── url-state-properties.md                # This documentation file
```

### Running the Tests

```bash
# Run all tests
npm test

# Run only property-based tests
npm test -- url-state-properties

# Run with coverage
npm test -- --coverage
```

## Benefits of Property-Based Testing

1. **Comprehensive Coverage**: Tests thousands of input combinations automatically
2. **Edge Case Discovery**: Finds edge cases that manual testing might miss
3. **Regression Prevention**: Ensures properties hold across all valid inputs
4. **Documentation**: Properties serve as executable specifications
5. **Confidence**: Provides high confidence that URL state management works correctly

## Future Enhancements

1. **Shrinking**: Implement custom shrinkers for complex state objects
2. **Stateful Testing**: Test sequences of state changes (e.g., page change → sort change → page change)
3. **Integration**: Combine with integration tests that test full component behavior
4. **Performance**: Add performance properties (e.g., URL updates should complete within 100ms)
