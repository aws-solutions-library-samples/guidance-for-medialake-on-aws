# Collection Types Permissions Fix

## Issue

Users in the "superAdministrators" group were getting "Access Denied" when trying to access System Settings → Collections tab, even though they should have full access.

## Root Cause

The collection-types permissions were not included in the JWT token claims for the superAdministrator permission set.

## Solution

Permissions are now properly configured through the auth system rather than hardcoded in CASL.

## Changes Made

### 1. Auth Seeder Update ✅

**File**: `lambdas/auth/auth_seeder/index.py`

Added collection-types permissions to the superAdministrator permission set:

```python
"settings": {
    # ... existing permissions ...
    "collection-types": {
        "create": True,
        "view": True,
        "edit": True,
        "delete": True,
        "manage": True,
    },
}
```

### 2. Backend Permission Check Update ✅

**File**: `lambdas/api/collections_api/utils/permission_utils.py`

Updated `check_admin_permission()` to recognize the superAdministrators group:

```python
admin_groups = ["admin", "superadministrators", "administrators"]
is_admin = any(g.lower() in admin_groups for g in groups)
```

## Deployment Steps

### Step 1: Deploy Backend

```bash
# Deploy the updated collections API Lambda
cdk deploy CollectionsApiStack

# Or deploy all stacks
cdk deploy --all
```

### Step 2: Update Permission Sets

You need to trigger an update to the auth seeder custom resource to update the superAdministrator permission set in DynamoDB:

**Option A: Via CDK (Recommended)**

```bash
# This will trigger the auth seeder to update permission sets
cdk deploy AuthStack --force
```

**Option B: Manual Update**
If you don't want to redeploy, manually update DynamoDB:

1. Go to DynamoDB console
2. Find your auth table (MediaLakeAuthTable or similar)
3. Find item with:
   - PK: `PS#superAdministrator`
   - SK: `METADATA`
4. Edit the `permissions` attribute to add:

```json
"settings": {
  "collection-types": {
    "create": true,
    "view": true,
    "edit": true,
    "delete": true,
    "manage": true
  }
}
```

### Step 3: Users Need to Re-Login

After updating the permission set, users in the superAdministrators group need to:

1. **Log out** of the application
2. **Log back in** to get a new JWT token with updated permissions

The new JWT token will include the custom permissions claim with collection-types access.

## How It Works

### JWT Token Claims Flow

1. **User Logs In** → Cognito authenticates user
2. **Pre-Token Generation Lambda** triggers:
   - Looks up user's groups (e.g., "superAdministrators")
   - Fetches permission sets assigned to those groups from DynamoDB
   - Flattens permissions into format like: `["settings.collection-types.manage", "settings.collection-types.create", ...]`
   - Adds to JWT as `customPermissions` claim
3. **Frontend receives JWT** with permissions embedded
4. **CASL ability factory** reads `customPermissions` from JWT and builds ability instance
5. **User can access Collection Types** management page

### Frontend Permission Check

The `<Can>` component in SystemSettingsPage checks:

```tsx
<Can I="manage" a="collection-types">
  <CollectionTypesManagement />
</Can>
```

This checks if the JWT token's `customPermissions` includes `settings.collection-types.manage`.

### Backend Permission Check

Each collection-types mutation endpoint calls:

```python
check_admin_permission(user_context)
```

This checks if the user's Cognito group is in the admin groups list.

## Verification

After deployment and re-login, verify access works:

1. **Check JWT Token** (in browser devtools):

   ```javascript
   // In browser console
   const token = localStorage.getItem("idToken"); // or wherever you store it
   const payload = JSON.parse(atob(token.split(".")[1]));
   console.log(payload.customPermissions);
   // Should include: "settings.collection-types.manage"
   ```

2. **Test Frontend Access**:
   - Navigate to System Settings
   - Click "Collections" tab
   - Should see CollectionTypesManagement component (not "Access Denied")

3. **Test Backend Access**:

   ```bash
   # Try to create a collection type
   curl -X POST https://api.yourdomain.com/settings/collection-types \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Test Type",
       "description": "Test",
       "color": "#1976d2",
       "icon": "Work"
     }'

   # Should return 201 Created (not 403 Forbidden)
   ```

## Permission Structure

The permission set now includes these hierarchical permissions:

```
settings.collection-types.create
settings.collection-types.view
settings.collection-types.edit
settings.collection-types.delete
settings.collection-types.manage
```

The `manage` permission is the most permissive and is what the CASL check looks for.

## Troubleshooting

### Still Getting "Access Denied"?

1. **Verify user is in superAdministrators group**:
   - Check Cognito user pool
   - User should be member of "superAdministrators" group

2. **Verify permission set was updated**:
   - Check DynamoDB auth table
   - Item `PS#superAdministrator` should have collection-types permissions

3. **Verify user has new JWT token**:
   - User must log out and log back in
   - Check JWT payload for `customPermissions` claim
   - Should include `settings.collection-types.manage`

4. **Check browser console for CASL errors**:
   - Look for "Ability created" logs
   - Check if customPermissions are being parsed correctly

5. **Check Lambda logs**:
   - Pre-token generation Lambda should show permission flattening
   - Collection types Lambda should show admin check passing

### Backend Returns 403?

If the frontend shows the page but API calls return 403:

- The JWT might not have the group claim
- Check `extract_user_context()` is properly reading `cognito:groups`
- Verify the group name matches exactly (case-insensitive check is in place)

## Files Changed

- `lambdas/auth/auth_seeder/index.py` - Added collection-types to superAdministrator permissions
- `lambdas/api/collections_api/utils/permission_utils.py` - Updated admin group check

## No Changes Needed

- Frontend CASL configuration - automatically reads from JWT customPermissions
- Frontend components - already using correct permission checks
- Other permission sets (editor, viewer) - they don't need collection-types access
