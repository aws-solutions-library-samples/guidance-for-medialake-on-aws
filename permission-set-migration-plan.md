# Permission-Set API Migration Plan

## Overview

This document outlines the plan for migrating the permission-set API from `/authorization/permission-sets` to `/permissions` and creating a dedicated `permissions_stack.py` file. This migration will improve the organization of the codebase and make the permission-set API more intuitive to use.

## Current Structure

Currently, the permission-set API is defined in `medialake_constructs/api_gateway/api_gateway_authorization.py` and is integrated into the application in `app.py`. The API endpoints are created under the `/authorization/permission-sets` path.

The permission sets are stored in a DynamoDB table created in the `AuthorizationStack`, and the frontend interacts with the API through React Query hooks defined in `usePermissionSets.ts`.

## Migration Plan

### 1. Create New Permissions Stack

- Create a new file `medialake_stacks/permissions_stack.py` that will contain the new permissions stack
- Define the necessary imports, props dataclass, and stack class
- Move the relevant code from `api_gateway_authorization.py` to the new stack

### 2. Update Backend Code

- Modify `app.py` to include and instantiate the new permissions stack
- Update API paths from `/authorization/permission-sets` to `/permissions`
- Ensure the new stack has access to the authorization DynamoDB table
- Update any references to the old API paths in the backend code

### 3. Update Frontend Code

- Update `medialake_user_interface/src/api/endpoints.ts` to use the new paths
- Update `medialake_user_interface/src/api/hooks/usePermissionSets.ts` to work with the new endpoints
- Update `medialake_user_interface/src/permissions/transformers/permission-transformer.ts` to handle the new resource paths

### 4. Testing

- Test the new API endpoints to ensure they work correctly
- Test the frontend to ensure it can interact with the new API endpoints
- Verify that permissions are still correctly applied in the UI

## Progress Tracking

| Task | Status | Notes |
|------|--------|-------|
| Create `permissions_stack.py` | Completed | Created new stack file with permission-set API endpoints under `/permissions` path with dedicated Lambda functions |
| Update `app.py` | Completed | Added instantiation of the new permissions stack and updated dependencies |
| Update frontend endpoints | Completed | Updated API endpoints in `endpoints.ts` to use the new `/permissions` path |
| Update frontend hooks | Not Needed | The hooks use the endpoints from `endpoints.ts`, so no changes needed |
| Update permission transformer | Completed | Added support for the new `/permissions` path in the resource mapper |
| Fix resource conflicts | Completed | Redesigned permissions_stack.py to create new Lambda functions with unique names to avoid conflicts |
| Fix import error in groups_stack.py | Completed | Removed duplicate import of `cdk` from `aws_cdk` |
| Remove old endpoints | Not Started | Need to remove the old `/authorization/permission-sets` endpoints after confirming the new ones work |
| Testing | Not Started | Need to test the new API endpoints and frontend integration |