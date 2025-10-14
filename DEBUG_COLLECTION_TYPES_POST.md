# Debug: Collection Types POST Returns 200 But No Data

## Issue

- POST to `/settings/collection-types` returns status 200
- Expected: status 201 with created collection type
- Collection type not appearing in database

## Most Likely Causes

### 1. Response Body Contains Error (Most Likely)

The handler might be returning status 200 with an error message in the body.

**Check the response body**:

```json
{
  "success": false,  // ← Check this!
  "error": {
    "code": "SOME_ERROR",
    "message": "Error description",
    "details": [...]
  }
}
```

Common errors:

- `FORBIDDEN` - Admin permission check failed
- `VALIDATION_ERROR` - Input validation failed
- `INTERNAL_SERVER_ERROR` - DynamoDB write failed

### 2. Admin Permission Check Failing

If you're not in the correct group, the handler returns 403.

**Check your user groups**:

```bash
# Get your JWT token payload
echo "YOUR_JWT_TOKEN" | cut -d'.' -f2 | base64 -d | jq .

# Look for:
{
  "cognito:groups": ["admin"] // or ["superAdministrators"]
}
```

### 3. Validation Failing

Check your request payload matches the schema.

**Required fields**:

```json
{
  "name": "string (1-50 chars)",
  "color": "#RRGGBB (hex format)",
  "icon": "string (must be in allowed list)"
}
```

**Allowed icons**:

- Folder, Work, Campaign, Task, Archive, Collections
- Star, Label, Category, Bookmark, Description
- Assignment, Event, Storage, Cloud, AttachFile

### 4. DynamoDB Permission Issue

Lambda might not have write permissions to the DynamoDB table.

## Debug Steps

### Step 1: Capture Full Response

```bash
curl -v -X POST https://d3ghgww307ikzd.cloudfront.net/v1/settings/collection-types \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Debug Test",
    "description": "Testing POST",
    "color": "#1976d2",
    "icon": "Work"
  }' 2>&1 | tee full_response.txt

# Check:
# - HTTP status code (200 vs 201)
# - Response body (success: true/false)
# - Error messages if any
```

### Step 2: Check CloudWatch Logs

```bash
# Find the Lambda function name
aws lambda list-functions --query 'Functions[?contains(FunctionName, `settings_api`)].FunctionName'

# Tail logs
aws logs tail /aws/lambda/medialake_settings_api_dev --follow --format short
```

**Look for**:

- `"Creating collection type: colltype_xxxxx"` - Success path
- `"Admin permission check failed"` - Permission issue
- `"Validation error"` - Validation issue
- `"Error creating collection type"` - DynamoDB/other error

### Step 3: Check DynamoDB Table

```bash
# Query for collection types
aws dynamodb query \
  --table-name medialake_collections_dev \
  --key-condition-expression 'PK = :pk AND begins_with(SK, :sk)' \
  --expression-attribute-values '{
    ":pk":{"S":"SYSTEM"},
    ":sk":{"S":"COLLTYPE#"}
  }'
```

If empty, the write is failing.

### Step 4: Check Lambda IAM Permissions

```bash
# Get Lambda function details
aws lambda get-function --function-name medialake_settings_api_dev

# Get the role ARN and check its policies
aws iam get-role --role-name ROLE_NAME_FROM_ABOVE
aws iam list-attached-role-policies --role-name ROLE_NAME
```

**Required permissions**:

- `dynamodb:PutItem` on collections table
- `dynamodb:Query` on collections table
- `dynamodb:GetItem` on collections table

## Debugging the Handler

### Check 1: Validation Errors

The handler validates:

```python
# Required fields
if not request_data.get("name"):
    return {"success": false, "error": {...}, "statusCode": 422}

# Color format
if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
    return validation error

# Icon in allowed list
if icon not in ALLOWED_ICONS:
    return validation error
```

### Check 2: Permission Check

```python
# In collection_types_post.py line 38-40
user_context = extract_user_context(app.current_event.raw_event)
check_admin_permission(user_context)  # Raises ForbiddenError if not admin
```

If you're not in `admin`, `superAdministrators`, or `administrators` group → 403

### Check 3: DynamoDB Write

```python
# In collection_types_post.py line 68-83
collection_type = CollectionTypeModel()
collection_type.PK = "SYSTEM"
collection_type.SK = f"COLLTYPE#{type_id}"
# ... set other fields
collection_type.save()  # ← This might fail silently
```

## Quick Fix Script

Run this to test directly:

```python
# test_collection_type_creation.py
import boto3
import json
from datetime import datetime, timezone

dynamodb = boto3.client('dynamodb', region_name='us-east-1')

# Test write to DynamoDB
response = dynamodb.put_item(
    TableName='medialake_collections_dev',
    Item={
        'PK': {'S': 'SYSTEM'},
        'SK': {'S': 'COLLTYPE#test_manual'},
        'name': {'S': 'Manual Test'},
        'color': {'S': '#1976d2'},
        'icon': {'S': 'Work'},
        'isActive': {'BOOL': True},
        'isSystem': {'BOOL': False},
        'createdAt': {'S': datetime.now(timezone.utc).isoformat()},
        'updatedAt': {'S': datetime.now(timezone.utc).isoformat()},
    }
)

print("DynamoDB write successful!")
print(json.dumps(response, indent=2, default=str))

# Now query it back
response = dynamodb.query(
    TableName='medialake_collections_dev',
    KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
    ExpressionAttributeValues={
        ':pk': {'S': 'SYSTEM'},
        ':sk': {'S': 'COLLTYPE#'}
    }
)

print(f"\nFound {response['Count']} collection types:")
for item in response.get('Items', []):
    print(f"  - {item['name']['S']} ({item['SK']['S']})")
```

## Expected Behavior

### Successful POST Response (Status 201)

```json
{
  "success": true,
  "data": {
    "id": "colltype_abc12345",
    "name": "Your Type Name",
    "description": "Your description",
    "color": "#1976d2",
    "icon": "Work",
    "isActive": true,
    "isSystem": false,
    "createdAt": "2025-10-14T...",
    "updatedAt": "2025-10-14T..."
  },
  "meta": {
    "timestamp": "2025-10-14T...",
    "version": "v1",
    "request_id": "req_..."
  }
}
```

### Failed POST Response (Status 422/403/500)

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR", // or FORBIDDEN, INTERNAL_SERVER_ERROR
    "message": "Request validation failed",
    "details": [
      {
        "field": "color",
        "message": "Invalid hex color format",
        "code": "INVALID_FORMAT"
      }
    ]
  },
  "meta": {
    "timestamp": "2025-10-14T...",
    "version": "v1",
    "request_id": "req_..."
  }
}
```

## Resolution Checklist

- [ ] Check actual response body (not just status code)
- [ ] Verify user is in admin/superAdministrators group
- [ ] Verify request payload has all required fields
- [ ] Verify color is valid hex format (#RRGGBB)
- [ ] Verify icon is in allowed list
- [ ] Check CloudWatch logs for errors
- [ ] Check Lambda has DynamoDB write permissions
- [ ] Query DynamoDB to confirm write succeeded

## Need More Help?

**Share these details**:

1. Full response body (including status code)
2. CloudWatch log excerpt
3. Your user groups from JWT token
4. Request payload you're sending
5. DynamoDB query results

This will help identify the exact issue!
