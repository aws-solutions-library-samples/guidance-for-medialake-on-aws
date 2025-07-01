---
title: Current Search Parameter Flow Analysis
task_id: search-optimization-1.1
date: 2025-06-29
last_updated: 2025-06-29
status: DRAFT
owner: Debug
---

# Current Search Parameter Flow Analysis

## Executive Summary

The media-lake-v2 system implements a complex search functionality that flows from React frontend → API Gateway → Lambda functions → OpenSearch. The current implementation uses individual query parameters for each field, creating potential performance bottlenecks and URL length limitations.

## System Architecture Overview

### Frontend Layer (React/TypeScript)
- **Entry Point**: [`SearchPage.tsx`](medialake_user_interface/src/pages/SearchPage.tsx:1)
- **State Management**: [`useSearchState.ts`](medialake_user_interface/src/hooks/useSearchState.ts:1) with Zustand store
- **API Integration**: [`useSearch.ts`](medialake_user_interface/src/api/hooks/useSearch.ts:1) with React Query

### Backend Layer (Python Lambda)
- **Search Handler**: [`lambdas/api/search/get_search/index.py`](lambdas/api/search/get_search/index.py:1)
- **Utility Functions**: [`search_utils.py`](lambdas/api/search/get_search/search_utils.py:1)
- **Fields API**: [`get_fields/index.py`](lambdas/api/search/fields/get_fields/index.py:1)

## Parameter Flow Analysis

### 1. Frontend Parameter Construction

#### URL Parameter Initialization
The frontend initializes search parameters from multiple sources:

```typescript
// From SearchPage.tsx lines 114-137
const initialFacetFilters: FacetFilters = {
    type: searchParams.get('type') || type,
    extension: searchParams.get('extension') || extension,
    LargerThan: searchParams.has('LargerThan') 
        ? parseInt(searchParams.get('LargerThan') || '0', 10) 
        : LargerThan,
    asset_size_lte: searchParams.has('asset_size_lte') 
        ? parseInt(searchParams.get('asset_size_lte') || '0', 10) 
        : asset_size_lte,
    // ... additional parameters
};
```

#### State Management Pattern
The system follows the frontend best practices from [`frontEndSystemPatterns.md`](cline_docs/frontEndSystemPatterns.md:1):
- **Client State (Zustand)**: UI preferences, filter states, form interactions
- **Server State (React Query)**: Search results, field definitions, cached responses

### 2. API Request Construction

#### Individual Parameter Approach
Currently, each search parameter is added individually to the query string:

```typescript
// From useSearch.ts lines 73-95
const queryParams = new URLSearchParams();
queryParams.append('q', query);
queryParams.append('page', page.toString());
queryParams.append('pageSize', pageSize.toString());
queryParams.append('semantic', isSemantic.toString());

// Individual facet parameters
if (params?.type) queryParams.append('type', params.type);
if (params?.extension) queryParams.append('extension', params.extension);
if (params?.LargerThan) queryParams.append('LargerThan', params.LargerThan.toString());
// ... continues for each parameter
```

#### Field Selection Implementation
Fields are currently added as multiple query parameters:

```typescript
// From useSearch.ts lines 89-95
if (params?.fields && params.fields.length > 0) {
    params.fields.forEach(field => {
        queryParams.append('fields', field);
    });
}
```

### 3. Backend Parameter Processing

#### Parameter Validation
The Lambda function uses Pydantic models for parameter validation:

```python
# From index.py lines 75-94
class SearchParams(BaseModelWithConfig):
    q: str = Field(..., min_length=1)
    page: conint(gt=0) = Field(default=1)
    pageSize: conint(gt=0, le=500) = Field(default=50)
    # ... facet parameters
    type: Optional[str] = None
    extension: Optional[str] = None
    LargerThan: Optional[int] = None
    # ... additional parameters
```

#### Query Construction
Parameters are processed into OpenSearch query filters:

```python
# From index.py lines 377-417
if params.type:
    var_type = params.type.split(",")
    filters_to_add.append({"terms": {"DigitalSourceAsset.Type": var_type}})

if params.extension:
    var_ext = params.extension.split(",")
    filters_to_add.append({"terms": {"DigitalSourceAsset.MainRepresentation.Format": var_ext}})
```

### 4. OpenSearch Integration

#### Query Structure
The system builds complex OpenSearch queries with:
- **Main Query**: Text search with multiple field matching strategies
- **Filters**: Facet-based filtering using terms and range queries
- **Aggregations**: For facet counts and suggestions
- **Source Filtering**: Field selection for response optimization

## Current Implementation Strengths

### 1. Robust State Management
- Proper separation of client and server state
- URL synchronization for bookmarkable searches
- Efficient caching with React Query

### 2. Flexible Search Capabilities
- Support for both semantic and text-based search
- Complex filtering with multiple facet types
- Dynamic field selection

### 3. Performance Optimizations
- Batch presigned URL generation
- Parallel processing for semantic results
- Connection pooling for OpenSearch client

## Identified Issues and Bottlenecks

### 1. URL Length Limitations
- Individual parameters create long URLs
- Risk of hitting browser URL length limits (2048 characters)
- Poor user experience with complex filter combinations

### 2. Parameter Processing Inefficiency
- Multiple individual parameter checks
- Repetitive validation logic
- No parameter grouping or batching

### 3. Field Selection Limitations
- Multiple `fields` parameters in URL
- No comma-separated field list support
- Inefficient for large field selections

### 4. Scalability Concerns
- Linear parameter processing
- No parameter compression
- Potential for parameter explosion with new features

## Performance Impact Analysis

### Frontend Performance
- **Parameter Construction**: O(n) complexity for each parameter
- **URL Updates**: Multiple URLSearchParams operations
- **State Synchronization**: Individual parameter tracking

### Backend Performance
- **Parameter Parsing**: Individual field extraction
- **Query Building**: Sequential filter construction
- **Validation Overhead**: Per-parameter validation

### Network Performance
- **Request Size**: Proportional to parameter count
- **URL Complexity**: Impacts caching and logging
- **Debugging Difficulty**: Complex parameter strings

## Recommendations for Optimization

### 1. Implement Comma-Separated Field Lists
Replace multiple `fields` parameters with single comma-separated list:
```
Current: ?fields=field1&fields=field2&fields=field3
Optimized: ?fields=field1,field2,field3
```

### 2. Parameter Grouping
Group related parameters into structured objects:
```
Current: ?asset_size_gte=100&asset_size_lte=1000
Optimized: ?size_range=100-1000
```

### 3. Filter Compression
Implement parameter encoding for complex filter combinations:
```
Current: ?type=image&type=video&extension=jpg&extension=png
Optimized: ?filters=type:image,video;ext:jpg,png
```

### 4. Batch Parameter Processing
Implement batch processing for parameter validation and query construction.

## Next Steps

1. **Parameter Mapping Documentation**: Detailed mapping of all current parameters
2. **Performance Bottleneck Analysis**: Specific performance impact measurements
3. **Optimization Implementation**: Phased approach to parameter optimization
4. **Testing Strategy**: Comprehensive testing of optimized parameter handling

## Dependencies

- Frontend state management system (Zustand + React Query)
- Backend parameter validation (Pydantic)
- OpenSearch query construction
- URL routing and navigation