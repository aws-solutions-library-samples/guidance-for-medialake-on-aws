# Authorization Type Fixed ✅

## Issue Resolved

**Error**:

```
ValidationError: MediaLakeStack/SharedRestApi/Default/settings/collection-types/GET -
Authorization type is set to COGNITO_USER_POOLS which is different from what is
required by the authorizer [CUSTOM]
```

**Root Cause**: The `SettingsApi` construct was using `AuthorizationType.COGNITO` directly in `add_method()`, but the authorizer passed in is a `CUSTOM` authorizer.

## Solution

Changed the authorization pattern to match how other API Gateway constructs in the codebase handle custom authorizers.

### Before (Incorrect) ❌

```python
collection_types_resource.add_method(
    "GET",
    lambda_integration,
    authorizer=props.authorizer,
    authorization_type=api_gateway.AuthorizationType.COGNITO,  # ❌ Wrong!
)
```

### After (Correct) ✅

```python
get_method = collection_types_resource.add_method(
    "GET",
    lambda_integration,
)
# Access CloudFormation method and set custom authorization
cfn_method = get_method.node.default_child
cfn_method.authorization_type = "CUSTOM"  # ✅ Correct!
cfn_method.authorizer_id = props.authorizer.authorizer_id
```

## Pattern Used

This pattern matches the existing `CollectionsApi` construct:

**File**: `medialake_constructs/api_gateway/api_gateway_collections.py` (lines 240-241)

```python
cfn_method = collection_types_method.node.default_child
cfn_method.authorization_type = "CUSTOM"
cfn_method.authorizer_id = props.authorizer.authorizer_id
```

## Why This Works

### API Gateway Authorization Hierarchy

1. **Authorizer Resource** - Created once (by `ApiGatewayStack`)
   - Type: CUSTOM (Lambda authorizer)
   - Uses Cognito for token validation

2. **Method Configuration** - Each endpoint
   - Must specify: `authorization_type = "CUSTOM"`
   - Must reference: `authorizer_id`

### The Problem with Direct Parameters

When you pass `authorization_type=AuthorizationType.COGNITO` to `add_method()`, CDK tries to validate that the authorizer type matches. Since the authorizer is CUSTOM (not COGNITO_USER_POOLS), it fails validation.

### The Solution: CloudFormation Direct Access

By accessing the CloudFormation method directly via `.node.default_child`, we bypass CDK's validation and set the properties at the CloudFormation level where the authorizer is already correctly configured as CUSTOM.

## Files Modified

### `medialake_constructs/api_gateway/api_gateway_settings.py`

Updated all 6 method definitions:

- ✅ `GET /settings/collection-types`
- ✅ `POST /settings/collection-types`
- ✅ `GET /settings/collection-types/{proxy+}`
- ✅ `PUT /settings/collection-types/{proxy+}`
- ✅ `DELETE /settings/collection-types/{proxy+}`
- ✅ `POST /settings/collection-types/{proxy+}` (for migrate)

Each now uses:

```python
method = resource.add_method(http_method, lambda_integration)
cfn_method = method.node.default_child
cfn_method.authorization_type = "CUSTOM"
cfn_method.authorizer_id = props.authorizer.authorizer_id
```

## Verification

The fix ensures:

- ✅ All methods use CUSTOM authorization type
- ✅ All methods reference the correct authorizer ID
- ✅ Pattern matches existing API Gateway constructs
- ✅ No CDK validation errors

## Deployment Ready

The authorization error is now fixed. You can deploy:

```bash
cdk deploy MediaLakeStack
```

This will:

1. Create the Settings API Lambda
2. Create API Gateway routes with CUSTOM authorization
3. Configure all 6 endpoints correctly
4. Enable your POST requests to work!

## How Authorization Will Work

```
POST /v1/settings/collection-types
    ↓
API Gateway receives request
    ↓
Custom Lambda Authorizer triggered
    ↓
Validates JWT token from Cognito
    ↓
Checks user groups/permissions
    ↓
Returns authorization policy
    ↓
✅ If authorized → Settings API Lambda invoked
    ↓
Admin permission check
    ↓
Process request
```

## Other APIs Using This Pattern

This pattern is used consistently across the codebase:

- ✅ `CollectionsApi` - Lines 240-241, 252-253, etc.
- ✅ `UsersApi` - Similar pattern
- ✅ `GroupsApi` - Similar pattern
- ✅ All other API constructs with custom authorizers

## Summary

✅ **Authorization type fixed to match custom authorizer**
✅ **Pattern matches existing API Gateway constructs**
✅ **All 6 endpoints configured correctly**
✅ **Ready to deploy**

Run: `cdk deploy MediaLakeStack` 🚀
