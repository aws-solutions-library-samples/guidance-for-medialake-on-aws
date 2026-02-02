# System View Permission Fix

## Problem

Users (including super admins, editors, and viewers) were getting 403 errors on login and being redirected to the access-denied page. The app was making a request to `/v1/settings/system/search` during initialization, but users didn't have the required `system:view` permission.

## Root Cause

1. The app makes an API call to `/v1/settings/system/search` on login to fetch system settings
2. The custom authorizer requires `system:view` permission for this endpoint
3. The viewer permission set was missing `system` permissions entirely
4. The editor permission set was missing `system` permissions entirely
5. The super admin had `settings.system:view` (nested format) but the authorizer expected `system:view` (flat format)

## Solution

Updated all three default permission sets in `lambdas/auth/auth_seeder/index.py`:

### 1. Viewer Permission Set

Added top-level `system` permissions:

```python
"system": {
    "view": True,  # Allow viewers to read system settings (needed for app initialization)
    "edit": False,
}
```

### 2. Editor Permission Set

Added top-level `system` permissions:

```python
"system": {
    "view": True,  # Allow editors to read system settings (needed for app initialization)
    "edit": False,
}
```

### 3. Super Administrator Permission Set

Added top-level `system` permissions (in addition to existing nested `settings.system`):

```python
"system": {
    "view": True,  # Top-level system permissions for app initialization
    "edit": True,
}
```

Note: Super admin retains the nested `settings.system` structure for backward compatibility with other parts of the system.

## Permission Flattening

The `pre_token_generation` lambda flattens nested permissions into JWT claims:

- Nested: `settings.system.view` → JWT claim: `settings.system:view`
- Top-level: `system.view` → JWT claim: `system:view`

The custom authorizer expects `system:view` for the `/settings/system/search` endpoint, so all permission sets now include the top-level format.

## Deployment Notes

1. Deploy the updated `auth_seeder` lambda
2. The `update_handler` in auth_seeder has `force_update=True` for system permission sets, so it will update existing permission sets in DynamoDB
3. Users must log out and log back in to get new JWT tokens with updated permissions
4. CloudFront distribution may take 15-30 minutes to fully deploy, or create an invalidation for faster updates

## Files Modified

- `lambdas/auth/auth_seeder/index.py` - Updated all three default permission sets

## Testing

After deployment and user re-login:

1. Viewer users should be able to log in and see the app without 403 errors
2. Editor users should be able to log in and see the app without 403 errors
3. Super admin users should be able to log in and see the app without 403 errors
4. All users should be able to access `/v1/settings/system/search` endpoint
5. Permission restrictions for other endpoints should still work as expected

## Related Documentation

- `INTERNAL-ai-documentation/cloudfront-403-error-handling-fix.md` - CloudFront error handling
- `INTERNAL-ai-documentation/403-redirect-to-access-denied-page.md` - Frontend 403 redirect
- `lambdas/auth/custom_authorizer/JWT_PERMISSION_VALIDATION.md` - JWT permission validation
