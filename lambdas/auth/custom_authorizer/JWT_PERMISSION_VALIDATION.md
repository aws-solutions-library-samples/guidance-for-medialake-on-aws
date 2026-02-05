# JWT Custom Claims Permission Validation

## Overview

The custom authorizer now validates JWT custom claims (`custom:permissions`) against API actions before allowing requests. This provides fine-grained access control based on user permissions stored in the JWT token.

## How It Works

### 1. Permission Mapping

The authorizer maintains a mapping of HTTP method + resource path to required permissions:

**IMPORTANT**: API Gateway resource paths do NOT include `/api` prefix. They start directly with the resource name (e.g., `/pipelines/{pipelineId}`, not `/api/pipelines/{pipelineId}`).

```python
{
    "get /assets": "assets:view",
    "post /assets/upload": "assets:upload",
    "delete /assets/{id}": "assets:delete",
    "put /assets/{id}": "assets:edit",
    "delete /pipelines/{pipelineId}": "pipelines:delete",  # Note: {pipelineId} not {id}
    ...
}
```

### 2. JWT Token Structure

JWT tokens contain a `custom:permissions` claim with a JSON array of permissions:

```json
{
  "sub": "user-id-123",
  "cognito:username": "john.doe",
  "custom:permissions": "[\"assets:view\", \"assets:upload\", \"collections:view\"]"
}
```

### 3. Validation Flow

1. **Extract token** - Get JWT from Authorization header
2. **Verify signature** - Validate token with Cognito JWKS
3. **Parse custom claims** - Extract `custom:permissions` from token
4. **Determine required permission** - Map HTTP method + path to permission
5. **Validate permission** - Check if user has required permission
6. **Return policy** - Allow or Deny with descriptive error message

### 4. Authorization Response

**Success (Allow):**

```json
{
  "principalId": "User::user-id-123",
  "policyDocument": {
    "Effect": "Allow",
    "Resource": "arn:aws:execute-api:..."
  },
  "context": {
    "actionId": "get /api/assets",
    "userId": "User::user-id-123",
    "username": "john.doe",
    "claims": "{...}"
  }
}
```

**Failure (Deny):**

```json
{
  "principalId": "User::user-id-123",
  "policyDocument": {
    "Effect": "Deny",
    "Resource": "arn:aws:execute-api:..."
  },
  "context": {
    "authError": "Access denied: Missing required permission 'assets:delete'",
    "requiredPermission": "assets:delete",
    "requestId": "correlation-id-123"
  }
}
```

## Permission Format

Permissions use a flat `resource:action` format:

- `assets:view` - View assets
- `assets:upload` - Upload assets
- `assets:edit` - Edit assets
- `assets:delete` - Delete assets
- `collections:view` - View collections
- `collections:create` - Create collections
- `permissions:view` - View permissions
- `permissions:edit` - Edit permissions
- `api-keys:view` - View API keys
- `users:view` - View users

## Special Cases

### No Permission Required

If a route has no specific permission mapping, access is **allowed** by default. This is useful for public endpoints or endpoints that don't require specific permissions.

### Missing custom:permissions Claim

If the JWT token is missing the `custom:permissions` claim, all requests are **denied** with error:

```
"Access denied: No permissions found in token"
```

### DEBUG_MODE

When `DEBUG_MODE=true`, permission validation still runs but:

- Failures are logged as warnings
- Requests are allowed regardless of permission check result
- Useful for development and testing

## Frontend Integration

The frontend can access authorization errors from the API Gateway context:

```javascript
// On 403 Forbidden response
const authError = response.headers["x-amzn-errortype"];
const requiredPermission = response.headers["x-amzn-requiredpermission"];

// Display user-friendly message
if (authError) {
  showError(`${authError}. You need the '${requiredPermission}' permission.`);
}
```

## Future: AVP Integration

The code is structured to easily add Amazon Verified Permissions (AVP) as a secondary authorization layer:

```python
# Current: Custom claims only
has_permission, error_message = validate_jwt_permissions(
    parsed_token, required_permission, correlation_id
)
is_authorized = has_permission

# Future: Custom claims + AVP (both must pass)
has_permission, error_message = validate_jwt_permissions(
    parsed_token, required_permission, correlation_id
)
avp_authorized, avp_response = check_authorization_with_avp(
    bearer_token, action_id, event, correlation_id
)
is_authorized = has_permission and avp_authorized  # Defense in depth
```

The `check_authorization_with_avp()` function is already implemented but commented out for future use.

## Metrics

The authorizer emits CloudWatch metrics for monitoring:

- `validate.jwt_permissions.granted` - Permission check passed
- `validate.jwt_permissions.denied` - Permission check failed
- `validate.jwt_permissions.missing_claim` - Token missing custom:permissions
- `validate.jwt_permissions.parse_error` - Failed to parse permissions JSON
- `validate.jwt_permissions.latency` - Validation time in milliseconds
- `authorize.jwt.no_permission_required` - Route has no permission requirement
- `authorize.jwt.debug_bypass` - DEBUG_MODE bypass

## Testing

Run the test suite to verify permission validation:

```bash
python lambdas/auth/custom_authorizer/test_permission_logic.py
python lambdas/auth/custom_authorizer/test_permission_validation.py
```

## Adding New Permissions

To add a new permission mapping:

1. Update `create_permission_mapping()` in `index.py`:

```python
"get /api/new-resource": "new-resource:view",
"post /api/new-resource": "new-resource:create",
```

2. Ensure the permission is added to user tokens in `pre_token_generation` Lambda

3. Update frontend permission definitions to match

4. Add test cases to verify the new permission
