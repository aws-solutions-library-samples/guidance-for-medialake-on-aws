---
title: Search Parameter Mapping Documentation
task_id: search-optimization-1.1
date: 2025-06-29
last_updated: 2025-06-29
status: DRAFT
owner: Debug
---

# Search Parameter Mapping Documentation

## Overview

This document provides a comprehensive mapping of all search parameters in the media-lake-v2 system, documenting their flow from frontend to backend and their processing at each layer.

## Parameter Categories

### 1. Core Search Parameters

#### Query Parameter (`q`)
- **Frontend Type**: `string`
- **Backend Type**: `str` (required, min_length=1)
- **Purpose**: Main search term
- **Processing**: 
  - Frontend: URL encoded
  - Backend: Parsed and cleaned via [`parse_search_query()`](lambdas/api/search/get_search/search_utils.py:127)
- **OpenSearch Usage**: Multi-field text search with boosting

#### Semantic Search (`semantic`)
- **Frontend Type**: `boolean`
- **Backend Type**: `bool` (default=False)
- **Purpose**: Enable semantic/vector search
- **Processing**:
  - Frontend: Converted to string ("true"/"false")
  - Backend: Boolean conversion
- **OpenSearch Usage**: Triggers KNN vector search vs text search

### 2. Pagination Parameters

#### Page (`page`)
- **Frontend Type**: `number`
- **Backend Type**: `conint(gt=0)` (default=1)
- **Purpose**: Current page number
- **Processing**: 
  - Frontend: Integer validation
  - Backend: Converted to `from_` offset: `(page - 1) * pageSize`
- **OpenSearch Usage**: `from` parameter

#### Page Size (`pageSize`)
- **Frontend Type**: `number`
- **Backend Type**: `conint(gt=0, le=500)` (default=50)
- **Purpose**: Results per page
- **Processing**: 
  - Frontend: Dropdown selection (20, 50, 100, 200)
  - Backend: Validation with 500 max limit
- **OpenSearch Usage**: `size` parameter

### 3. Field Selection Parameters

#### Fields (`fields`)
- **Frontend Type**: `string[]`
- **Backend Type**: `Optional[List[str]]`
- **Purpose**: Select specific fields to return
- **Current Implementation**:
  ```typescript
  // Frontend: Multiple parameters
  params.fields.forEach(field => {
      queryParams.append('fields', field);
  });
  ```
- **Backend Processing**: Array of field names
- **OpenSearch Usage**: `_source.includes` array
- **Available Fields**:
  - `DigitalSourceAsset.Type` (Asset Type)
  - `DigitalSourceAsset.MainRepresentation.Format` (File Format)
  - `DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize` (File Size)
  - `DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate` (Created Date)
  - `DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name` (File Name)
  - `DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath` (Full Path)

### 4. Facet Filter Parameters

#### Asset Type (`type`)
- **Frontend Type**: `string`
- **Backend Type**: `Optional[str]`
- **Purpose**: Filter by asset type
- **Values**: `Image`, `Video`, `Audio`, `Document`
- **Processing**:
  - Frontend: Single or comma-separated values
  - Backend: Split by comma: `params.type.split(",")`
- **OpenSearch Usage**: `terms` query on `DigitalSourceAsset.Type`

#### File Extension (`extension`)
- **Frontend Type**: `string`
- **Backend Type**: `Optional[str]`
- **Purpose**: Filter by file format/extension
- **Values**: `jpg`, `png`, `mp4`, `wav`, etc.
- **Processing**:
  - Frontend: Single or comma-separated values
  - Backend: Split by comma: `params.extension.split(",")`
- **OpenSearch Usage**: `terms` query on `DigitalSourceAsset.MainRepresentation.Format`

#### File Size Filters

##### Larger Than (`LargerThan`)
- **Frontend Type**: `number`
- **Backend Type**: `Optional[int]`
- **Purpose**: Minimum file size in bytes
- **Processing**: Direct integer value
- **OpenSearch Usage**: `range` query with `gte`

##### Asset Size Less Than or Equal (`asset_size_lte`)
- **Frontend Type**: `number`
- **Backend Type**: `Optional[int]`
- **Purpose**: Maximum file size in bytes
- **Processing**: Combined with `asset_size_gte` for range query
- **OpenSearch Usage**: `range` query with `lte`

##### Asset Size Greater Than or Equal (`asset_size_gte`)
- **Frontend Type**: `number`
- **Backend Type**: `Optional[int]`
- **Purpose**: Minimum file size in bytes
- **Processing**: Combined with `asset_size_lte` for range query
- **OpenSearch Usage**: `range` query with `gte`

#### Date Filters

##### Ingested Date Less Than or Equal (`ingested_date_lte`)
- **Frontend Type**: `string` (ISO date)
- **Backend Type**: `Optional[str]`
- **Purpose**: Maximum ingestion date
- **Processing**: Combined with `ingested_date_gte` for range query
- **OpenSearch Usage**: `range` query on `CreateDate` field

##### Ingested Date Greater Than or Equal (`ingested_date_gte`)
- **Frontend Type**: `string` (ISO date)
- **Backend Type**: `Optional[str]`
- **Purpose**: Minimum ingestion date
- **Processing**: Combined with `ingested_date_lte` for range query
- **OpenSearch Usage**: `range` query on `CreateDate` field

#### Filename Filter (`filename`)
- **Frontend Type**: `string`
- **Backend Type**: `Optional[str]`
- **Purpose**: Filter by filename pattern
- **Processing**: Text matching
- **OpenSearch Usage**: Text search on filename fields

### 5. Advanced Parameters

#### Minimum Score (`min_score`)
- **Frontend Type**: Not exposed
- **Backend Type**: `float` (default=0.01)
- **Purpose**: Minimum relevance score threshold
- **Processing**: Direct float value
- **OpenSearch Usage**: `min_score` parameter

#### Search Fields (`search_fields`)
- **Frontend Type**: Not currently used
- **Backend Type**: `Optional[List[str]]`
- **Purpose**: Specify fields to search in
- **Processing**: Array of field paths
- **OpenSearch Usage**: Field targeting in queries

#### Filters (`filters`)
- **Frontend Type**: Not directly exposed
- **Backend Type**: `Optional[List[Dict]]`
- **Purpose**: Generic filter structure
- **Processing**: Dynamic filter construction
- **OpenSearch Usage**: Various query types based on operator

## Parameter Processing Flow

### 1. Frontend Parameter Construction

```typescript
// From useSearch.ts lines 72-95
const queryParams = new URLSearchParams();
queryParams.append('q', query);
queryParams.append('page', page.toString());
queryParams.append('pageSize', pageSize.toString());
queryParams.append('semantic', isSemantic.toString());

// Facet parameters - individual approach
if (params?.type) queryParams.append('type', params.type);
if (params?.extension) queryParams.append('extension', params.extension);
if (params?.LargerThan) queryParams.append('LargerThan', params.LargerThan.toString());
if (params?.asset_size_lte) queryParams.append('asset_size_lte', params.asset_size_lte.toString());
if (params?.asset_size_gte) queryParams.append('asset_size_gte', params.asset_size_gte.toString());
if (params?.ingested_date_lte) queryParams.append('ingested_date_lte', params.ingested_date_lte);
if (params?.ingested_date_gte) queryParams.append('ingested_date_gte', params.ingested_date_gte);
if (params?.filename) queryParams.append('filename', params.filename);

// Fields - multiple parameter approach
if (params?.fields && params.fields.length > 0) {
    params.fields.forEach(field => {
        queryParams.append('fields', field);
    });
}
```

### 2. Backend Parameter Extraction

```python
# From index.py lines 1123-1129
query_params = app.current_event.get("queryStringParameters") or {}

if "q" not in query_params:
    return {"status": "400", "message": "Missing required parameter 'q'", "data": None}

params = SearchParams(**query_params)
```

### 3. OpenSearch Query Construction

```python
# From index.py lines 377-417
filters_to_add = []

if params.type:
    var_type = params.type.split(",")
    filters_to_add.append({"terms": {"DigitalSourceAsset.Type": var_type}})

if params.extension:
    var_ext = params.extension.split(",")
    filters_to_add.append({"terms": {"DigitalSourceAsset.MainRepresentation.Format": var_ext}})

if params.asset_size_lte is not None and params.asset_size_gte is not None:
    filters_to_add.append({
        "range": {
            "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size": {
                "gte": params.asset_size_gte,
                "lte": params.asset_size_lte
            }
        }
    })

# Add all filters at once
query["bool"]["filter"].extend(filters_to_add)
```

## URL Parameter Examples

### Simple Search
```
/search?q=landscape&page=1&pageSize=50&semantic=false
```

### Complex Faceted Search
```
/search?q=mountain&type=Image,Video&extension=jpg,mp4&asset_size_gte=1000000&asset_size_lte=10000000&ingested_date_gte=2024-01-01&ingested_date_lte=2024-12-31&fields=DigitalSourceAsset.Type&fields=DigitalSourceAsset.MainRepresentation.Format&page=1&pageSize=50&semantic=false
```

### Semantic Search
```
/search?q=sunset%20over%20ocean&semantic=true&page=1&pageSize=20
```

## Parameter Validation Rules

### Frontend Validation
- **Page**: Must be positive integer
- **Page Size**: Must be one of [20, 50, 100, 200]
- **Dates**: Must be valid ISO date strings
- **File Sizes**: Must be positive integers

### Backend Validation (Pydantic)
- **Query (`q`)**: Required, minimum length 1
- **Page**: Must be greater than 0
- **Page Size**: Must be between 1 and 500
- **Numeric Fields**: Type validation for integers
- **Optional Fields**: Null/undefined handling

## Performance Considerations

### Current Bottlenecks

1. **Multiple Field Parameters**: Each field creates separate URL parameter
2. **Individual Parameter Processing**: Sequential validation and processing
3. **String Concatenation**: Multiple URLSearchParams.append() calls
4. **URL Length**: Risk of exceeding browser limits with complex filters

### Optimization Opportunities

1. **Comma-Separated Fields**: Single parameter with comma-separated values
2. **Parameter Grouping**: Related parameters in structured format
3. **Batch Processing**: Parallel parameter validation
4. **Parameter Compression**: Encoded parameter strings for complex filters

## Error Handling

### Frontend Error Scenarios
- Invalid parameter types
- URL parsing failures
- State synchronization issues

### Backend Error Scenarios
- Missing required parameters (400 error)
- Invalid parameter values (400 error)
- Parameter validation failures (Pydantic ValidationError)

### OpenSearch Error Scenarios
- Invalid field references
- Malformed query structure
- Index mapping conflicts

## Future Enhancements

### Proposed Parameter Optimizations

1. **Comma-Separated Field Lists**
   ```
   Current: ?fields=field1&fields=field2&fields=field3
   Proposed: ?fields=field1,field2,field3
   ```

2. **Range Parameter Syntax**
   ```
   Current: ?asset_size_gte=100&asset_size_lte=1000
   Proposed: ?size_range=100-1000
   ```

3. **Filter Encoding**
   ```
   Current: ?type=image&type=video&extension=jpg&extension=png
   Proposed: ?filters=type:image,video;ext:jpg,png
   ```

4. **Parameter Versioning**
   ```
   Proposed: ?v=2&filters_v2=encoded_filter_string
   ```

## Dependencies

- **Frontend**: React Router, URLSearchParams API
- **Backend**: Pydantic validation, FastAPI parameter extraction
- **OpenSearch**: Query DSL, field mapping
- **State Management**: Zustand store, React Query cache