# Frontend Test Reference Files

This directory contains reference implementations for unit and property-based tests for the Assets Page features.

## Current Status

The MediaLake project currently uses **Playwright** for end-to-end testing, not unit testing frameworks like Vitest or Jest. The test files in this directory are **reference implementations** that demonstrate how to test the implemented features if unit testing is added to the project in the future.

## Reference Files

### 1. `url-state-management.test.tsx.reference`

Property-based tests for URL state management using fast-check.

**Tests:**

- URL state round-trip (encoding/decoding)
- URL state synchronization
- Parameter initialization from URL
- Invalid parameter handling

**Requirements Validated:** 3.1, 3.2, 3.3, 3.4, 3.5, 3.6

### 2. `facet-filter-properties.test.tsx.reference`

Property-based tests for facet filter functionality using fast-check.

**Tests:**

- Facet filter application
- Multiple facet AND logic
- Facet filter removal
- Query construction with filters

**Requirements Validated:** 6.2, 6.3, 6.4, 6.5, 6.6

### 3. `FacetFilterPanel.test.tsx.reference`

Unit tests for the FacetFilterPanel component using React Testing Library.

**Tests:**

- Component rendering
- Facet count display
- Zero-count facet handling
- User interactions (checkbox, clear all)
- Active filters display

**Requirements Validated:** 6.7, 6.8

## To Enable These Tests

If you want to add unit testing to the project, follow these steps:

### 1. Install Dependencies

```bash
npm install --save-dev vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event fast-check @vitest/ui jsdom
```

### 2. Create Vitest Configuration

Create `vitest.config.ts`:

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
```

### 3. Create Test Setup File

Create `src/test/setup.ts`:

```typescript
import "@testing-library/jest-dom";
```

### 4. Update package.json Scripts

Add to `scripts` section:

```json
{
  "test:unit": "vitest",
  "test:unit:ui": "vitest --ui",
  "test:unit:coverage": "vitest --coverage"
}
```

### 5. Rename Reference Files

Remove the `.reference` extension from the test files:

```bash
cd medialake_user_interface/src/features/assets/__tests__
mv url-state-management.test.tsx.reference url-state-management.test.tsx
mv facet-filter-properties.test.tsx.reference facet-filter-properties.test.tsx
mv FacetFilterPanel.test.tsx.reference FacetFilterPanel.test.tsx
```

### 6. Run Tests

```bash
npm run test:unit
```

## Current Testing Approach

Since unit testing is not currently set up, the implemented features should be tested using:

1. **Backend Python Tests** - Comprehensive property-based and unit tests exist in `tests/api/search/`
2. **Manual Testing** - Test the features in the development environment
3. **Playwright E2E Tests** - Consider adding E2E tests for critical user flows

## Backend Tests (Already Implemented)

The backend has comprehensive test coverage with Hypothesis (property-based testing):

- `tests/api/search/test_sort_parameter_extraction_properties.py`
- `tests/api/search/test_sort_parameter_validation_properties.py`
- `tests/api/search/test_sort_clause_construction_properties.py`
- `tests/api/search/test_page_validation_properties.py`
- `tests/api/search/test_type_conversion_properties.py`
- `tests/api/search/test_field_verification.py`
- `tests/api/search/test_bucket_error_handling.py`
- And more...

Run backend tests with:

```bash
pytest tests/api/search/ -v
```

## Recommended Next Steps

1. **Manual Testing**: Test the implemented features in your development environment
2. **E2E Tests**: Consider adding Playwright tests for critical user flows
3. **Unit Testing Setup**: If desired, follow the steps above to enable unit testing
4. **Integration Testing**: Test with real AWS OpenSearch instance

## Documentation

See also:

- `.kiro/specs/assets-page-bugs/IMPLEMENTATION_SUMMARY.md` - Complete implementation summary
- `.kiro/specs/assets-page-bugs/TESTING_GUIDE.md` - Testing strategy and guide
- `tests/api/search/README.md` - Backend test documentation
