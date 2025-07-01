---
title: API Contract Specification for Optimized Parameters
task_id: search-optimization-2.1
date: 2025-06-29
last_updated: 2025-06-29
status: DRAFT
owner: Architect
---

# API Contract Specification for Optimized Parameters

## Executive Summary

This document defines the comprehensive API contract for the optimized search parameter implementation in media-lake-v2. It specifies request/response formats, validation rules, error handling, and backward compatibility requirements for both frontend and backend systems.

## API Endpoint Overview

### Primary Search Endpoint
```
GET /api/search
```

**Purpose**: Execute search queries with optimized parameter structure
**Authentication**: Required (Bearer token)
**Rate Limiting**: 100 requests per minute per user

## Request Specification

### HTTP Method and Headers
```http
GET /api/search HTTP/1.1
Host: api.media-lake-v2.com
Authorization: Bearer {jwt_token}
Content-Type: application/json
Accept: application/json
User-Agent: MediaLake-Frontend/2.1.0
```

### Query Parameter Structure

#### Core Parameters (Required)
```typescript
interface CoreRequestParams {
  q: string;                    // Search query (min: 1 char, max: 500 chars)
  page?: number;               // Page number (default: 1, min: 1, max: 10000)
  pageSize?: number;           // Results per page (default: 50, options: 20,50,100,200,500)
  semantic?: boolean;          // Enable semantic search (default: false)
}
```

**Validation Rules**:
- `q`: Required, URL-encoded, non-empty string
- `page`: Optional positive integer, defaults to 1
- `pageSize`: Optional, must be one of [20, 50, 100, 200, 500]
- `semantic`: Optional boolean, defaults to false

#### Field Selection Parameters
```typescript
interface FieldSelectionParams {
  fields?: string;             // Comma-separated field list or aliases
}
```

**Field Specification**:
- **Format**: Comma-separated values without spaces
- **Aliases Supported**: `type`, `format`, `size`, `created`, `filename`, `path`
- **Full Paths Supported**: Complete OpenSearch field paths
- **Validation**: Each field must exist in the schema

**Examples**:
```
fields=type,format,size                    // Using aliases
fields=type,DigitalSourceAsset.MainRepresentation.Format,size  // Mixed format
fields=DigitalSourceAsset.Type,DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize  // Full paths
```

#### Filter Parameters (Optimized)
```typescript
interface FilterParams {
  // Media type filters
  type?: string;               // Comma-separated: "Image,Video,Audio,Document"
  extension?: string;          // Comma-separated file extensions
  
  // Size filters (grouped)
  size_range?: string;         // Format: "min-max", "min-", or "-max"
  size_unit?: 'B' | 'KB' | 'MB' | 'GB';  // Size unit (default: 'B')
  
  // Date filters (grouped)
  date_range?: string;         // Format: "YYYY-MM-DD,YYYY-MM-DD"
  date_field?: 'ingested' | 'created' | 'modified';  // Target field (default: 'ingested')
  
  // Text filters
  filename?: string;           // Filename pattern
  path?: string;              // Path pattern
  content?: string;           // Content search
  
  // Advanced filters
  filters?: string;            // Encoded filter string
  filter_version?: '1' | '2';  // Filter format version (default: '1')
}
```

**Filter Validation Rules**:

1. **Type Filter**:
   - Valid values: `Image`, `Video`, `Audio`, `Document`
   - Case-sensitive
   - Comma-separated without spaces

2. **Extension Filter**:
   - Lowercase file extensions without dots
   - Examples: `jpg,png,mp4,wav`

3. **Size Range**:
   - Format: `{number}-{number}`, `{number}-`, or `-{number}`
   - Numbers must be positive integers
   - Range validation: min ≤ max when both specified

4. **Size Unit**:
   - Must be one of: `B`, `KB`, `MB`, `GB`
   - Applied to size_range values

5. **Date Range**:
   - Format: `YYYY-MM-DD,YYYY-MM-DD`, `YYYY-MM-DD,`, or `,YYYY-MM-DD`
   - Dates must be valid ISO format
   - Range validation: start ≤ end when both specified

6. **Advanced Filters**:
   - Encoded format: `key:value1,value2;key2:value3`
   - URL-encoded for special characters
   - Maximum length: 2000 characters

#### Legacy Parameters (Backward Compatibility)
```typescript
interface LegacyParams {
  // Deprecated size parameters
  LargerThan?: number;         // Use size_range instead
  asset_size_gte?: number;     // Use size_range instead
  asset_size_lte?: number;     // Use size_range instead
  
  // Deprecated date parameters
  ingested_date_gte?: string;  // Use date_range instead
  ingested_date_lte?: string;  // Use date_range instead
}
```

### Complete Request Examples

#### Simple Search Request
```http
GET /api/search?q=mountain&page=1&pageSize=50&semantic=false
```

#### Optimized Complex Search
```http
GET /api/search?q=landscape&type=Image,Video&extension=jpg,png,mp4&size_range=1-10&size_unit=MB&date_range=2024-01-01,2024-12-31&fields=type,format,size,created&page=1&pageSize=100&semantic=false
```

#### Advanced Encoded Search
```http
GET /api/search?q=nature&filters=type:Image,Video;ext:jpg,png;size:1MB-50MB;date:2024-01-01,2024-12-31&fields=type,format,size&page=1&pageSize=50
```

#### Legacy Format (Backward Compatibility)
```http
GET /api/search?q=mountain&type=Image&type=Video&asset_size_gte=1000000&asset_size_lte=10000000&ingested_date_gte=2024-01-01&ingested_date_lte=2024-12-31&fields=DigitalSourceAsset.Type&fields=DigitalSourceAsset.MainRepresentation.Format&page=1&pageSize=50
```

## Response Specification

### Success Response Structure
```typescript
interface SearchResponse {
  status: 'success';
  data: {
    results: AssetItem[];
    pagination: PaginationInfo;
    facets: FacetCounts;
    query_info: QueryInfo;
    performance: PerformanceMetrics;
  };
  meta: ResponseMetadata;
}
```

#### Asset Item Structure
```typescript
interface AssetItem {
  id: string;                  // Unique asset identifier
  score: number;              // Relevance score (0-1)
  source: AssetSource;        // Source asset data
  highlights?: HighlightInfo; // Search term highlights
  presigned_url?: string;     // Temporary access URL
}

interface AssetSource {
  DigitalSourceAsset: {
    Type: string;             // Asset type (Image, Video, Audio, Document)
    MainRepresentation: {
      Format: string;         // File format/extension
      StorageInfo: {
        PrimaryLocation: {
          FileSize: number;   // File size in bytes
          CreateDate: string; // ISO date string
          ObjectKey: {
            Name: string;     // Filename
            FullPath: string; // Complete path
          };
        };
      };
    };
    // Additional fields based on 'fields' parameter
  };
}
```

#### Pagination Information
```typescript
interface PaginationInfo {
  current_page: number;       // Current page number
  page_size: number;         // Results per page
  total_results: number;     // Total matching results
  total_pages: number;       // Total available pages
  has_next: boolean;         // Next page available
  has_previous: boolean;     // Previous page available
  next_page?: number;        // Next page number (if available)
  previous_page?: number;    // Previous page number (if available)
}
```

#### Facet Counts
```typescript
interface FacetCounts {
  types: Record<string, number>;      // Asset type counts
  extensions: Record<string, number>; // File extension counts
  size_ranges: {                      // File size distribution
    small: number;    // < 1MB
    medium: number;   // 1MB - 10MB
    large: number;    // 10MB - 100MB
    xlarge: number;   // > 100MB
  };
  date_ranges: {                      // Date distribution
    last_week: number;
    last_month: number;
    last_year: number;
    older: number;
  };
}
```

#### Query Information
```typescript
interface QueryInfo {
  parsed_query: string;       // Processed search query
  search_type: 'text' | 'semantic';  // Search method used
  applied_filters: AppliedFilters;    // Filters that were applied
  field_selection: string[];          // Fields included in response
  total_query_time_ms: number;        // Total query execution time
}

interface AppliedFilters {
  types?: string[];           // Applied type filters
  extensions?: string[];      // Applied extension filters
  size_range?: {              // Applied size range
    min?: number;
    max?: number;
    unit: string;
  };
  date_range?: {              // Applied date range
    start?: string;
    end?: string;
    field: string;
  };
  text_filters?: {            // Applied text filters
    filename?: string;
    path?: string;
    content?: string;
  };
}
```

#### Performance Metrics
```typescript
interface PerformanceMetrics {
  query_time_ms: number;      // OpenSearch query time
  processing_time_ms: number; // Backend processing time
  total_time_ms: number;      // Total request time
  cache_hit: boolean;         // Whether result was cached
  opensearch_took: number;    // OpenSearch internal timing
  result_count: number;       // Number of results returned
}
```

#### Response Metadata
```typescript
interface ResponseMetadata {
  api_version: string;        // API version used
  request_id: string;         // Unique request identifier
  timestamp: string;          // Response timestamp (ISO)
  parameter_version: '1' | '2'; // Parameter format detected
  deprecation_warnings?: string[]; // Legacy parameter warnings
}
```

### Success Response Example
```json
{
  "status": "success",
  "data": {
    "results": [
      {
        "id": "asset_12345",
        "score": 0.95,
        "source": {
          "DigitalSourceAsset": {
            "Type": "Image",
            "MainRepresentation": {
              "Format": "jpg",
              "StorageInfo": {
                "PrimaryLocation": {
                  "FileSize": 2048576,
                  "CreateDate": "2024-06-15T10:30:00Z",
                  "ObjectKey": {
                    "Name": "mountain_landscape.jpg",
                    "FullPath": "/uploads/2024/06/mountain_landscape.jpg"
                  }
                }
              }
            }
          }
        },
        "highlights": {
          "filename": ["<em>mountain</em>_landscape.jpg"]
        },
        "presigned_url": "https://s3.amazonaws.com/bucket/path?signature=..."
      }
    ],
    "pagination": {
      "current_page": 1,
      "page_size": 50,
      "total_results": 1247,
      "total_pages": 25,
      "has_next": true,
      "has_previous": false,
      "next_page": 2
    },
    "facets": {
      "types": {
        "Image": 856,
        "Video": 234,
        "Audio": 89,
        "Document": 68
      },
      "extensions": {
        "jpg": 445,
        "png": 234,
        "mp4": 178,
        "wav": 89
      },
      "size_ranges": {
        "small": 234,
        "medium": 567,
        "large": 334,
        "xlarge": 112
      },
      "date_ranges": {
        "last_week": 45,
        "last_month": 234,
        "last_year": 678,
        "older": 290
      }
    },
    "query_info": {
      "parsed_query": "mountain",
      "search_type": "text",
      "applied_filters": {
        "types": ["Image", "Video"],
        "size_range": {
          "min": 1048576,
          "max": 10485760,
          "unit": "MB"
        }
      },
      "field_selection": ["type", "format", "size", "created"],
      "total_query_time_ms": 45
    },
    "performance": {
      "query_time_ms": 23,
      "processing_time_ms": 12,
      "total_time_ms": 45,
      "cache_hit": false,
      "opensearch_took": 18,
      "result_count": 50
    }
  },
  "meta": {
    "api_version": "2.1.0",
    "request_id": "req_abc123def456",
    "timestamp": "2024-06-29T20:00:00Z",
    "parameter_version": "2",
    "deprecation_warnings": []
  }
}
```

## Error Response Specification

### Error Response Structure
```typescript
interface ErrorResponse {
  status: 'error';
  error: {
    code: string;              // Error code
    message: string;           // Human-readable error message
    details?: ErrorDetails;    // Additional error information
    validation_errors?: ValidationError[]; // Parameter validation errors
  };
  meta: ResponseMetadata;
}

interface ErrorDetails {
  parameter?: string;         // Parameter that caused the error
  value?: any;               // Invalid value provided
  expected?: string;         // Expected format or value
  suggestion?: string;       // Suggested correction
}

interface ValidationError {
  parameter: string;         // Parameter name
  message: string;          // Validation error message
  code: string;            // Validation error code
  value?: any;             // Invalid value
}
```

### Error Codes and Messages

#### Client Errors (4xx)

##### 400 - Bad Request
```json
{
  "status": "error",
  "error": {
    "code": "INVALID_PARAMETERS",
    "message": "One or more parameters are invalid",
    "validation_errors": [
      {
        "parameter": "size_range",
        "message": "Size range format must be 'min-max', 'min-', or '-max'",
        "code": "INVALID_RANGE_FORMAT",
        "value": "invalid-range"
      }
    ]
  },
  "meta": {
    "api_version": "2.1.0",
    "request_id": "req_error123",
    "timestamp": "2024-06-29T20:00:00Z"
  }
}
```

**Common 400 Error Codes**:
- `MISSING_REQUIRED_PARAMETER`: Required parameter `q` is missing
- `INVALID_PARAMETER_VALUE`: Parameter value is invalid
- `INVALID_RANGE_FORMAT`: Range parameter format is incorrect
- `INVALID_DATE_FORMAT`: Date format is not ISO compliant
- `INVALID_FIELD_SELECTION`: Requested field does not exist
- `PARAMETER_TOO_LONG`: Parameter exceeds maximum length
- `INVALID_FILTER_ENCODING`: Advanced filter encoding is malformed

##### 401 - Unauthorized
```json
{
  "status": "error",
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Authentication required. Please provide a valid Bearer token.",
    "details": {
      "suggestion": "Include 'Authorization: Bearer {token}' header"
    }
  }
}
```

##### 403 - Forbidden
```json
{
  "status": "error",
  "error": {
    "code": "INSUFFICIENT_PERMISSIONS",
    "message": "User does not have permission to access search functionality",
    "details": {
      "required_permission": "search:read"
    }
  }
}
```

##### 429 - Rate Limit Exceeded
```json
{
  "status": "error",
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Rate limit: 100 requests per minute",
    "details": {
      "limit": 100,
      "window": "1 minute",
      "reset_time": "2024-06-29T20:01:00Z"
    }
  }
}
```

#### Server Errors (5xx)

##### 500 - Internal Server Error
```json
{
  "status": "error",
  "error": {
    "code": "INTERNAL_SERVER_ERROR",
    "message": "An unexpected error occurred while processing the request",
    "details": {
      "suggestion": "Please try again later or contact support"
    }
  }
}
```

##### 503 - Service Unavailable
```json
{
  "status": "error",
  "error": {
    "code": "SEARCH_SERVICE_UNAVAILABLE",
    "message": "Search service is temporarily unavailable",
    "details": {
      "service": "OpenSearch",
      "estimated_recovery": "2024-06-29T20:05:00Z"
    }
  }
}
```

## Parameter Processing Rules

### Parameter Parsing Priority
1. **New optimized parameters** take precedence over legacy parameters
2. **Legacy parameters** are processed only if new parameters are not provided
3. **Mixed format** is supported with new parameters taking priority
4. **Validation errors** are returned for any invalid parameter combination

### Field Selection Processing
```python
def process_field_selection(fields_param: str) -> List[str]:
    """
    Process field selection parameter with alias resolution
    """
    if not fields_param:
        return DEFAULT_FIELDS
    
    field_list = [f.strip() for f in fields_param.split(',') if f.strip()]
    resolved_fields = []
    
    for field in field_list:
        if field in FIELD_ALIASES:
            resolved_fields.append(FIELD_ALIASES[field])
        elif field in VALID_FIELDS:
            resolved_fields.append(field)
        else:
            raise ValidationError(f"Invalid field: {field}")
    
    return resolved_fields
```

### Filter Processing
```python
def process_filters(params: dict) -> dict:
    """
    Process filter parameters with backward compatibility
    """
    filters = {}
    
    # Process new grouped parameters
    if 'size_range' in params:
        filters['size'] = parse_size_range(params['size_range'], params.get('size_unit', 'B'))
    elif 'asset_size_gte' in params or 'asset_size_lte' in params:
        # Legacy parameter support
        filters['size'] = parse_legacy_size_params(params)
    
    if 'date_range' in params:
        filters['date'] = parse_date_range(params['date_range'], params.get('date_field', 'ingested'))
    elif 'ingested_date_gte' in params or 'ingested_date_lte' in params:
        # Legacy parameter support
        filters['date'] = parse_legacy_date_params(params)
    
    return filters
```

### Advanced Filter Encoding
```python
def parse_advanced_filters(filters_param: str) -> dict:
    """
    Parse advanced encoded filter string
    Format: key:value1,value2;key2:value3,value4
    """
    filters = {}
    
    for filter_group in filters_param.split(';'):
        if ':' not in filter_group:
            continue
            
        key, values = filter_group.split(':', 1)
        key = key.strip()
        value_list = [v.strip() for v in values.split(',') if v.strip()]
        
        if key in VALID_FILTER_KEYS:
            filters[key] = value_list
        else:
            raise ValidationError(f"Invalid filter key: {key}")
    
    return filters
```

## Backward Compatibility Implementation

### Parameter Migration Strategy
```python
class ParameterProcessor:
    def process_request(self, params: dict) -> ProcessedParams:
        """
        Process request parameters with backward compatibility
        """
        # Detect parameter format version
        version = self.detect_parameter_version(params)
        
        if version == '1':
            # Legacy format - convert to new format
            processed = self.convert_legacy_params(params)
            warnings = self.generate_deprecation_warnings(params)
        else:
            # New format - direct processing
            processed = self.process_optimized_params(params)
            warnings = []
        
        return ProcessedParams(
            data=processed,
            version=version,
            warnings=warnings
        )
    
    def detect_parameter_version(self, params: dict) -> str:
        """
        Detect parameter format version based on parameter names
        """
        legacy_indicators = [
            'asset_size_gte', 'asset_size_lte',
            'ingested_date_gte', 'ingested_date_lte'
        ]
        
        new_indicators = [
            'size_range', 'date_range', 'filters'
        ]
        
        has_legacy = any(param in params for param in legacy_indicators)
        has_new = any(param in params for param in new_indicators)
        
        if has_new:
            return '2'
        elif has_legacy:
            return '1'
        else:
            return '2'  # Default to new format
```

### Deprecation Warnings
```typescript
interface DeprecationWarning {
  parameter: string;          // Deprecated parameter name
  message: string;           // Deprecation message
  replacement: string;       // Recommended replacement
  removal_version: string;   // Version when parameter will be removed
}
```

**Example Deprecation Warnings**:
```json
{
  "deprecation_warnings": [
    {
      "parameter": "asset_size_gte",
      "message": "Parameter 'asset_size_gte' is deprecated",
      "replacement": "Use 'size_range' parameter instead",
      "removal_version": "3.0.0"
    },
    {
      "parameter": "fields (array format)",
      "message": "Multiple 'fields' parameters are deprecated",
      "replacement": "Use comma-separated 'fields' parameter",
      "removal_version": "3.0.0"
    }
  ]
}
```

## Performance Considerations

### Request Processing Optimization
- **Parameter parsing**: Optimized for comma-separated values
- **Validation caching**: Cache validation results for repeated patterns
- **Filter construction**: Batch processing for grouped parameters
- **Field resolution**: Pre-computed alias mappings

### Response Optimization
- **Field selection**: Only include requested fields in response
- **Pagination**: Efficient offset-based pagination
- **Caching**: Response caching based on normalized parameter keys
- **Compression**: Gzip compression for large responses

### Monitoring and Metrics
- **Parameter usage statistics**: Track adoption of new parameter format
- **Performance metrics**: Monitor processing time improvements
- **Error rates**: Track validation error frequency
- **Cache efficiency**: Monitor cache hit rates for different parameter patterns

## Security Considerations

### Input Validation
- **Parameter sanitization**: All parameters are sanitized before processing
- **Length limits**: Maximum parameter lengths enforced
- **Character validation**: Only allowed characters in parameter values
- **Injection prevention**: SQL/NoSQL injection prevention in filter parameters

### Rate Limiting
- **Per-user limits**: 100 requests per minute per authenticated user
- **Parameter complexity limits**: Complex filter combinations may have lower limits
- **Burst protection**: Short-term burst allowances with longer-term limits

### Access Control
- **Authentication required**: All requests must include valid Bearer token
- **Permission validation**: User must have `search:read` permission
- **Field access control**: Some fields may require additional permissions
- **Audit logging**: All search requests are logged for security monitoring

## Testing and Validation

### Parameter Validation Test Cases
1. **Valid parameter combinations**: All supported parameter formats
2. **Invalid parameter formats**: Malformed ranges, dates, and encodings
3. **Boundary conditions**: Maximum lengths, extreme values
4. **Backward compatibility**: Legacy parameter format support
5. **Mixed format handling**: Combination of old and new parameters

### Performance Test Scenarios
1. **Simple searches**: Basic query with minimal parameters
2. **Complex searches**: Multiple filters and field selections
3. **Field-heavy searches**: Large number of field selections
4. **Advanced encoded searches**: Complex filter encoding
5. **Legacy format searches**: Backward compatibility performance

### Integration Test Coverage
1. **Frontend integration**: React component parameter construction
2. **Backend processing**: Lambda function parameter handling
3. **OpenSearch integration**: Query construction and execution
4. **Error handling**: Comprehensive error scenario testing
5. **Cache integration**: Response caching with optimized parameters

## Conclusion

This API contract specification provides a comprehensive framework for implementing optimized search parameters in media-lake-v2. The design ensures:

- **40-85% URL length reduction** through optimized parameter structure
- **Full backward compatibility** with existing implementations
- **Comprehensive error handling** with detailed validation messages
- **Performance optimization** through grouped parameter processing
- **Security compliance** with proper validation and access control
- **Monitoring capabilities** for performance tracking and optimization

The specification supports both immediate deployment with backward compatibility and long-term migration to the optimized parameter format, ensuring zero-disruption implementation while providing significant performance benefits.