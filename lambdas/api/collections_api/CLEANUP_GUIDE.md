# Collections Lambda Cleanup Guide

## Overview

After testing and verifying the new consolidated Collections Lambda is working correctly, you can safely remove the old individual lambda directories.

## ⚠️ IMPORTANT - Test First!

**DO NOT** remove the old lambda directories until you have:

1. ✅ Successfully deployed the new consolidated lambda
2. ✅ Tested all collections API endpoints
3. ✅ Verified no errors in CloudWatch logs
4. ✅ Confirmed the API behaves as expected in your application

## Directories to Remove

Once testing is complete, you can safely delete these directories:

### Collection Types Lambdas

```bash
rm -rf lambdas/api/collections/collection-types/
```

### Collections Lambdas

```bash
rm -rf lambdas/api/collections/collections/
```

### Collection Detail Lambda (if exists)

```bash
rm -rf lambdas/api/collections/collection/
```

## Complete Cleanup Command

After thorough testing, run this command from the project root:

```bash
# Remove all old collections lambda directories
rm -rf lambdas/api/collections/collection-types/ \
       lambdas/api/collections/collections/ \
       lambdas/api/collections/collection/
```

## What to Keep

**DO NOT DELETE:**

- `lambdas/api/collections_api/` - The new consolidated lambda
- `lambdas/common_libraries/` - Shared utilities used by the new lambda
- `lambdas/api/collections/collections-openapi.json` - API specification (if exists)

## Verification After Cleanup

After removing the old directories:

1. Run CDK diff to ensure only expected changes:

   ```bash
   cdk diff
   ```

2. Verify no references to old lambdas in infrastructure code

3. Check that deployment still works:
   ```bash
   cdk deploy <your-stack-name>
   ```

## Rollback Plan

If you need to rollback to the old lambda structure:

1. Use git to restore the deleted directories:

   ```bash
   git checkout HEAD -- lambdas/api/collections/
   ```

2. Restore the old infrastructure file:

   ```bash
   git checkout HEAD -- medialake_constructs/api_gateway/api_gateway_collections.py
   ```

3. Redeploy:
   ```bash
   cdk deploy <your-stack-name>
   ```

## Testing Checklist Before Cleanup

Use this checklist to verify the new lambda works correctly:

### Collection Types

- [ ] GET /collection-types - Lists types correctly
- [ ] POST /collection-types - Creates new type
- [ ] Authentication is enforced

### Collections

- [ ] GET /collections - Lists collections
- [ ] POST /collections - Creates new collection
- [ ] GET /collections/shared-with-me - Lists shared collections
- [ ] GET /collections/{id} - Gets collection details
- [ ] PATCH /collections/{id} - Updates collection
- [ ] DELETE /collections/{id} - Deletes collection

### Collection Items

- [ ] GET /collections/{id}/items - Lists items
- [ ] POST /collections/{id}/items - Adds item
- [ ] POST /collections/{id}/items/batch - Batch adds items
- [ ] POST /collections/{id}/items/batch-remove - Batch removes items
- [ ] PUT /collections/{id}/items/{itemId} - Updates item
- [ ] DELETE /collections/{id}/items/{itemId} - Removes item

### Collection Rules

- [ ] GET /collections/{id}/rules - Lists rules
- [ ] POST /collections/{id}/rules - Creates rule
- [ ] PUT /collections/{id}/rules/{ruleId} - Updates rule
- [ ] DELETE /collections/{id}/rules/{ruleId} - Deletes rule

### Collection Sharing

- [ ] GET /collections/{id}/share - Lists shares
- [ ] POST /collections/{id}/share - Shares collection
- [ ] DELETE /collections/{id}/share/{userId} - Unshares collection

### Collection Assets

- [ ] GET /collections/{id}/assets - Retrieves assets

### Error Handling

- [ ] 401 errors for unauthenticated requests
- [ ] 404 errors for non-existent resources
- [ ] 422 errors for validation failures
- [ ] 500 errors are properly logged

### Performance

- [ ] Response times are acceptable
- [ ] No significant increase in cold starts
- [ ] CloudWatch metrics are being recorded

## Support

If you encounter issues after cleanup:

1. Check CloudWatch logs for errors
2. Review the rollback plan above
3. Refer to the main README.md in collections_api/

## Notes

- The cleanup is optional - the old directories don't affect the new lambda
- Keep old directories if you want to reference the original implementation
- Consider creating a git tag before cleanup for easy rollback:
  ```bash
  git tag pre-collections-cleanup
  git push origin pre-collections-cleanup
  ```
