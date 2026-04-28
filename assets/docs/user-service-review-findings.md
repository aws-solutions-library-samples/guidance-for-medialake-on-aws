# User Service Code Review — Findings & Proposed Fixes

**Date:** 2026-04-24
**Scope:** `lambdas/api/users/*`, `medialake_constructs/api_gateway/api_gateway_users.py`, frontend user management & auth components
**Reviewer:** Kiro

---

## New Code (Password Reset) — Verdict: Clean

The password reset implementation across backend, CDK, and frontend is consistent with existing patterns and has no bugs. The `AuthPage` correctly gates the forgot-password flow behind `hasCognitoProvider`, the admin reset button is conditionally rendered via the `onResetPassword` prop, and the backend handler follows the same structure as `users_enable_post.py` / `users_disable_post.py`.

---

## Pre-Existing Issues Found

### 1. Inconsistent User ID Extraction Across Handlers (Medium Severity)

**Problem:** The handlers use three different methods to extract the authenticated user's identity:

| Handler                                                                  | Method                                  |
| ------------------------------------------------------------------------ | --------------------------------------- |
| `profile_get.py`, `profile_put.py`, `settings_get.py`, `settings_put.py` | `authorizer.claims.sub`                 |
| `favorites_get.py`, `favorites_post.py`, `favorites_delete.py`           | `authorizer.userId`                     |
| `users_get.py`, `users_put.py`, `users_delete.py`, etc.                  | Path parameter `user_id` (admin action) |

The admin-action handlers (CRUD on other users) correctly use path params. But the "self" handlers (profile, settings, favorites) are inconsistent — some read `claims.sub`, others read `authorizer.userId`. If the custom authorizer changes its response shape, some endpoints will break while others won't.

**Proposed Fix:** Create a shared utility function in a new `lambdas/api/users/auth_utils.py`:

```python
def get_authenticated_user_id(app, logger) -> str | None:
    """Extract the authenticated user's ID from the request context.
    Checks authorizer.userId first (custom authorizer), then falls back to claims.sub (Cognito)."""
    request_context = app.current_event.raw_event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})
    user_id = authorizer.get("userId") or authorizer.get("claims", {}).get("sub")
    if not user_id:
        logger.error("Could not extract user ID from request context")
    return user_id
```

Then refactor all "self" handlers to use this single function.

---

### 2. Inconsistent Response Format (Low-Medium Severity)

**Problem:** Handlers return responses in two different formats:

- **Format A** (used by `users_get.py`, `users_put.py`, `profile_get.py`, `settings_get.py`, etc.):

  ```json
  {
    "statusCode": 200,
    "headers": { "Content-Type": "application/json" },
    "body": "{\"status\":\"200\",\"message\":\"...\",\"data\":{...}}"
  }
  ```

  Uses Pydantic `model_dump_json()` for the body, includes explicit `headers`.

- **Format B** (used by `users_post.py`, `users_delete.py`, `users_enable_post.py`, `users_disable_post.py`, `users_reset_password_post.py`):
  ```json
  { "statusCode": 200, "body": "{\"message\":\"...\"}" }
  ```
  Uses `json.dumps()` or raw JSON strings, no explicit `headers`, no `status`/`data` envelope.

The frontend `useCreateUser` hook has a workaround that detects and unwraps the `{statusCode, body}` wrapper, which suggests the API Gateway proxy integration is double-wrapping responses in some cases.

**Proposed Fix:** Standardize all handlers to use a shared response builder:

```python
# lambdas/api/users/response_utils.py
import json

def success_response(status_code: int, message: str, data: dict = None) -> dict:
    body = {"status": status_code, "message": message}
    if data is not None:
        body["data"] = data
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }

def error_response(status_code: int, message: str) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"status": status_code, "message": message}),
    }
```

Migrate all handlers to use these functions. This also eliminates the duplicated `ErrorResponse` / `_create_error_response` Pydantic models that are copy-pasted across 6+ files.

---

### 3. Duplicated Pydantic Models Across Handlers (Low Severity)

**Problem:** `ErrorResponse`, `UserResponse`, and `_create_error_response()` are copy-pasted identically in `users_get.py`, `users_put.py`, `profile_get.py`, `profile_put.py`, `settings_get.py`, `settings_put.py`, `favorites_get.py`, `favorites_post.py`, and `favorites_delete.py`.

Similarly, `CognitoError` is defined in both `users_enable_post.py` and `users_disable_post.py` but never actually used (it's a dead class).

**Proposed Fix:**

- Extract shared models into `lambdas/api/users/models.py`
- Delete the unused `CognitoError` class from enable/disable handlers
- Import from the shared module

---

### 4. `validate_groups_exist` in `users_post.py` Doesn't Paginate (Low-Medium Severity)

**Problem:** `cognito.list_groups()` returns a maximum of 60 groups per call. If the user pool has more than 60 groups, the validation will miss groups beyond the first page, incorrectly marking them as invalid.

```python
response = cognito.list_groups(UserPoolId=user_pool_id)  # Only first page!
```

**Proposed Fix:** Use a paginator or loop with `NextToken`:

```python
existing_group_names = set()
params = {"UserPoolId": user_pool_id}
while True:
    response = cognito.list_groups(**params)
    for group in response.get("Groups", []):
        existing_group_names.add(group["GroupName"])
    next_token = response.get("NextToken")
    if not next_token:
        break
    params["NextToken"] = next_token
```

---

### 5. `_get_user_groups` in `users_put.py` Doesn't Paginate (Low-Medium Severity)

**Problem:** Same pagination issue as above. `admin_list_groups_for_user` also paginates, but the code only reads the first page:

```python
response = cognito.admin_list_groups_for_user(UserPoolId=user_pool_id, Username=user_id)
return [group["GroupName"] for group in response.get("Groups", [])]
```

If a user belongs to many groups, the diff calculation in `_update_user_groups` will be wrong — it could try to re-add groups the user is already in, or fail to remove groups it doesn't know about.

**Proposed Fix:** Same pagination pattern as above.

---

### 6. Error Messages Leak Internal Details in Some Handlers (Low Severity)

**Problem:** Several catch-all handlers expose `str(e)` directly to the client:

- `users_put.py`: `return _create_error_response(500, str(e))`
- `settings_get.py`: `return _create_error_response(500, f"Internal server error: {str(e)}")`
- `profile_put.py`: same pattern
- `favorites_get.py`, `favorites_post.py`, `favorites_delete.py`: same pattern

This can leak stack traces, DynamoDB table names, or Cognito error details to the API consumer.

**Proposed Fix:** Always return a generic message to the client. The `logger.exception()` call already captures the full error for CloudWatch:

```python
except Exception:
    logger.exception("Error processing request")
    return error_response(500, "Internal server error")
```

---

### 7. `users_delete.py` Doesn't Clean Up DynamoDB User Data (Medium Severity)

**Problem:** When a user is deleted via `admin_delete_user`, only the Cognito user is removed. The user's DynamoDB records (profile, settings, favorites) under `USER#{user_id}` are orphaned and never cleaned up.

**Proposed Fix:** After successful Cognito deletion, query and batch-delete all items with `userId = USER#{user_id}` from the user table. This requires passing `dynamodb` and `USER_TABLE_NAME` to the delete handler (currently it only receives `cognito`). Alternatively, implement this as an async cleanup via an EventBridge event or DynamoDB stream.

---

### 8. `profile_put.py` Uses `put_item` Instead of `update_item` (Low Severity)

**Problem:** The profile update does a full `get_item` → merge → `put_item` cycle. This is not atomic — if two concurrent requests update different fields, one will overwrite the other's changes (last-write-wins race condition).

**Proposed Fix:** Use DynamoDB `update_item` with `UpdateExpression` to atomically update only the changed fields:

```python
update_expr_parts = []
expr_attr_values = {}
for key, value in profile_data.items():
    update_expr_parts.append(f"#{key} = :{key}")
    expr_attr_values[f":{key}"] = value
# ... build and execute update_item
```

---

### 9. Frontend `useGetUser` Double-Unwrap Workaround (Low Severity)

**Problem:** In `useUsers.ts`, both `useGetUser` and `useCreateUser` contain identical workaround code to detect and unwrap a `{statusCode, body}` wrapper:

```typescript
if (
  typeof responseData === "object" &&
  "statusCode" in responseData &&
  "body" in responseData
) {
  const wrappedResponse = responseData as { statusCode: number; body: string };
  if (typeof wrappedResponse.body === "string") {
    responseData = JSON.parse(wrappedResponse.body);
  }
}
```

This suggests the API Gateway proxy integration is sometimes returning the Lambda response as-is (with `statusCode` and `body` as separate fields) rather than properly unwrapping it. This is a symptom of the inconsistent response format (Issue #2).

**Proposed Fix:** Once the backend response format is standardized (Issue #2), this workaround can be removed. The `apiClient` Axios interceptor should handle response parsing uniformly.

---

## Priority Summary

| Priority | Issue                                           | Status                                                               |
| -------- | ----------------------------------------------- | -------------------------------------------------------------------- |
| Medium   | #1 Inconsistent user ID extraction              | **Fixed** — shared `auth_utils.get_authenticated_user_id()`          |
| Medium   | #7 User deletion doesn't clean up DynamoDB      | **Fixed** — `_cleanup_user_data()` in `users_delete.py`              |
| Low-Med  | #2 Inconsistent response format                 | **Fixed** — shared `response_utils` (API contract preserved)         |
| Low-Med  | #4, #5 Missing pagination on Cognito list calls | **Fixed** — `cognito_utils.list_all_groups()` / `list_user_groups()` |
| Low      | #6 Error message leaks                          | **Fixed** — all handlers return generic messages                     |
| Low      | #3 Duplicated Pydantic models                   | **Fixed** — shared `response_utils`, dead `CognitoError` removed     |
| Low      | #8 Non-atomic profile update                    | **Fixed** — `update_item` with `UpdateExpression`                    |
| Low      | #9 Frontend double-unwrap workaround            | Deferred — requires frontend coordination                            |
