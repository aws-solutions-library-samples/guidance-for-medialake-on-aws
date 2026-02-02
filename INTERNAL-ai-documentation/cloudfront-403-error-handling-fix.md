# CloudFront 403 Error Handling Fix - Final Solution

## Problem

When users get 403 errors from the API (permission denied), CloudFront was converting them to 200 responses with index.html, preventing the frontend from detecting and handling authorization failures properly. After removing the 403 mapping, users experienced a flash and redirect loop when getting 403 errors.

## Root Cause

CloudFront had a 403 → 200 error response mapping that served index.html for all 403 errors. This was originally needed for SPA routing when S3 returns 403 for missing files with OAC (Origin Access Control), but it also caught API 403 errors from the authorizer.

When we removed the 403 mapping, the axios interceptor was using `window.location.href = "/access-denied"` which caused a full page reload, triggering the same API call that caused the 403, creating an infinite loop.

## Solution

### 1. Remove 403 Error Response from CloudFront

Updated `medialake_constructs/userInterface.py` to only handle 404 errors:

```python
"error_responses": [
    # NOTE: Only handle 404 errors for SPA routing
    # 403 errors from API pass through and are handled by axios interceptor
    cloudfront.ErrorResponse(
        http_status=404,
        response_http_status=200,
        response_page_path="/index.html",
        ttl=Duration.minutes(0),
    ),
],
```

### 2. Create Navigation Utility

Created `medialake_user_interface/src/utils/navigation.ts` to enable programmatic navigation outside React components:

```typescript
export const navigateToAccessDenied = (errorDetails: {
  message: string;
  requiredPermission?: string;
  attemptedUrl?: string;
  timestamp: string;
}) => {
  sessionStorage.setItem("accessDeniedError", JSON.stringify(errorDetails));
  router.navigate("/access-denied");
};
```

This uses the router instance directly, avoiding full page reloads that would cause the flash and redirect loop.

### 3. Update Axios Interceptor

Updated `medialake_user_interface/src/api/apiClient.ts` to use the navigation utility:

```typescript
// Use dynamic import to avoid circular dependency issues
import("@/utils/navigation").then(({ navigateToAccessDenied }) => {
  navigateToAccessDenied({
    message: authError,
    requiredPermission,
    attemptedUrl: error.config?.url,
    timestamp: new Date().toISOString(),
  });
});
```

The dynamic import prevents circular dependencies and the router navigation prevents full page reloads.

## How It Works

### API 403 Flow:

1. User attempts action without permission (e.g., delete pipeline as viewer)
2. API Gateway custom authorizer returns 403 with error details
3. CloudFront passes through the 403 (no longer converts to 200)
4. Axios interceptor catches the 403 response
5. Checks if it's an API error (JSON content-type or has authError/message fields)
6. Stores error details in sessionStorage
7. Uses router.navigate() to go to `/access-denied` without page reload
8. AccessDeniedPage displays the error with "Go Back" and "Go Home" buttons

### SPA Routing Flow:

1. User navigates to `/access-denied` (or any SPA route)
2. CloudFront requests `/access-denied` from S3
3. S3 returns 404 (file doesn't exist)
4. CloudFront catches 404 and serves index.html with 200 status
5. React app loads and routes to the access-denied page
6. Page reads error details from sessionStorage and displays them

## Key Benefits

1. No full page reload - smooth navigation to access-denied page
2. No flash or redirect loop
3. Proper error messages with permission details
4. Works for both in-app navigation and direct URL access
5. Maintains SPA routing for 404 errors

## Files Modified

- `medialake_constructs/userInterface.py` - Removed 403 error response
- `medialake_user_interface/src/utils/navigation.ts` - Created navigation utility
- `medialake_user_interface/src/api/apiClient.ts` - Updated to use navigation utility

## Testing

After deployment:

1. As viewer, try to delete a pipeline → Should see access-denied page without flash
2. As viewer, try to create a pipeline → Should see access-denied page without flash
3. Direct navigation to `/access-denied` → Should load properly via 404 → index.html
4. All SPA routes should work normally via 404 → index.html mapping

## Deployment Notes

This change requires:

- ✅ CDK deployment to update CloudFront distribution
- ⚠️ CloudFront distribution update takes 15-30 minutes
- ⚠️ May require cache invalidation: `aws cloudfront create-invalidation --distribution-id XXX --paths "/*"`

## Related Documentation

- `INTERNAL-ai-documentation/403-redirect-to-access-denied-page.md` - Initial 403 redirect implementation
- `lambdas/auth/custom_authorizer/JWT_PERMISSION_VALIDATION.md` - JWT permission validation
