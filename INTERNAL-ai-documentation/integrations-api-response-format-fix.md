# Integrations API Response Format Fix

## Issue

After consolidating the integrations Lambda to use AWS Lambda Powertools `APIGatewayRestResolver`, the frontend was unable to render the integrations data. The Lambda was working but returning data in the wrong format.

**Date Fixed:** October 21, 2025

## Root Cause

The response utility functions were wrapping responses with `statusCode` and `body`:

```python
# INCORRECT - Old format
{
    "statusCode": 200,
    "body": {
        "success": True,
        "status": "success",
        "message": "...",
        "data": [...],
        "meta": {...}
    }
}
```

However, Lambda Powertools `APIGatewayRestResolver` **automatically** wraps the response with HTTP status codes. When you return a dict from a route handler, Powertools handles the API Gateway response format.

## Solution

Updated `response_utils.py` to return just the body content:

```python
# CORRECT - New format
{
    "success": True,
    "status": "success",
    "message": "...",
    "data": [...],
    "meta": {...}
}
```

Lambda Powertools then wraps this automatically for API Gateway.

## Files Modified

### `/lambdas/api/integrations_api/response_utils.py`

**Before:**

```python
def create_success_response(...):
    response = {
        "statusCode": status_code,
        "body": {
            "success": True,
            "status": "success",
            "message": message,
            "data": data,
            "meta": {...},
        },
    }
    if request_id:
        response["body"]["meta"]["request_id"] = request_id
    return response
```

**After:**

```python
def create_success_response(...):
    response = {
        "success": True,
        "status": "success",
        "message": message,
        "data": data,
        "meta": {...},
    }
    if request_id:
        response["meta"]["request_id"] = request_id
    return response
```

Same changes applied to `create_error_response()`.

## Frontend Expectations

The frontend TypeScript interfaces expect:

```typescript
interface IntegrationsResponse {
  status: string;
  message: string;
  data: Integration[];
}

interface Integration {
  id: string;
  name: string;
  type: string;
  status: string;
  description: string;
  configuration: Record<string, any>;
  createdAt: string;
  updatedAt: string;
}
```

With the fix, the backend now returns data in the format:

```json
{
  "success": true,
  "status": "success",
  "message": "Integrations retrieved successfully",
  "data": [
    {
      "id": "uuid",
      "name": "Integration Name",
      "nodeId": "node_id",
      "type": "integration",
      "status": "active",
      "description": "Description",
      "createdAt": "2025-10-21T...",
      "updatedAt": "2025-10-21T...",
      "environment": "env-id",
      "configuration": {...}
    }
  ],
  "meta": {
    "timestamp": "2025-10-21T...",
    "version": "v1",
    "request_id": "..."
  }
}
```

## Key Learnings

### Lambda Powertools Response Handling

When using `APIGatewayRestResolver`:

1. **DO NOT** return `{"statusCode": 200, "body": {...}}`
2. **DO** return just the body content: `{"success": True, "data": [...]}`
3. Powertools automatically handles:
   - HTTP status codes
   - API Gateway response format
   - Content-Type headers
   - CORS headers (if configured)

### Setting HTTP Status Codes

To return specific status codes with Powertools:

```python
from aws_lambda_powertools.event_handler import Response

# Method 1: Return Response object
@app.post("/resource")
def handler():
    return Response(
        status_code=201,
        content_type="application/json",
        body=json.dumps({"data": "..."}),
    )

# Method 2: Raise HTTP exceptions
from aws_lambda_powertools.event_handler.exceptions import BadRequestError

@app.post("/resource")
def handler():
    if invalid:
        raise BadRequestError("Invalid request")
    return {"data": "..."}  # Defaults to 200
```

### Collections API Pattern

The consolidated integrations API now follows the same pattern as the collections API:

- Both use `APIGatewayRestResolver` with proxy integration
- Both return body content only
- Both let Powertools handle HTTP response wrapping
- Both use similar response structure with `success`, `data`, and `meta` fields

## Testing

To verify the fix:

### 1. Test GET /integrations

```bash
curl -X GET https://api.medialake.example/integrations \
  -H "Authorization: Bearer <token>"
```

Expected response (200 OK):

```json
{
  "success": true,
  "status": "success",
  "message": "Integrations retrieved successfully",
  "data": [...],
  "meta": {...}
}
```

### 2. Test POST /integrations

```bash
curl -X POST https://api.medialake.example/integrations \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "nodeId": "twelve_labs",
    "description": "Test integration",
    "auth": {
      "type": "apiKey",
      "credentials": {"apiKey": "test-key"}
    }
  }'
```

Expected response (201 Created):

```json
{
  "success": true,
  "status": "success",
  "message": "Integration created successfully",
  "data": {
    "id": "uuid",
    "name": "Twelve Labs",
    ...
  },
  "meta": {...}
}
```

### 3. Frontend Rendering

- Navigate to Settings → Integrations
- Verify integrations table displays data
- Verify create, update, delete operations work
- Check browser console for any errors

## Related Documentation

- [Integrations Lambda Consolidation](./integrations-lambda-consolidation.md)
- [AWS Lambda Powertools Documentation](https://docs.powertools.aws.dev/lambda/python/latest/core/event_handler/api_gateway/)
- [Collections Lambda Implementation](./collections-lambda-implementation-verification.md)

## Commit Message

```
fix(integrations): correct API response format for Lambda Powertools

The response utility functions were incorrectly wrapping responses with
statusCode and body. Lambda Powertools APIGatewayRestResolver
automatically handles response wrapping, so handlers should return just
the body content.

Updated create_success_response() and create_error_response() to return
body content only. This matches the collections API pattern and fixes
frontend rendering issues.

Affected endpoints:
- GET /integrations
- POST /integrations
- PUT /integrations/{id}
- DELETE /integrations/{id}
```

---

**Status:** Fixed and Verified
**Pattern:** Follows Collections API architecture
**Impact:** Frontend now successfully renders integrations data
