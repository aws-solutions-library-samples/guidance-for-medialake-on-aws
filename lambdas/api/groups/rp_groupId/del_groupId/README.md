# Delete Group Lambda Function

This Lambda function handles deletion of groups from both DynamoDB and Cognito with proper rollback capabilities.

## API Endpoint

**DELETE** `/groups/{groupId}`

## Directory Structure

```
lambdas/api/groups/rp_groupId/del_groupId/
├── index.py          # Main Lambda handler
└── README.md         # This documentation
```

## Function Overview

The Lambda function performs the following operations:

1. **Validates the request** - Ensures groupId is provided in path parameters
2. **Checks user authorization** - Extracts user information from Cognito claims
3. **Verifies group exists** - Confirms the group exists in DynamoDB before deletion
4. **Two-phase deletion with rollback**:
   - Phase 1: Delete group from Cognito
   - Phase 2: Delete group metadata and memberships from DynamoDB
   - If Phase 2 fails, automatically restore Cognito group

## Request Format

### Path Parameters

- `groupId` (string, required): The ID of the group to delete

### Headers

- `Authorization`: Bearer token (handled by API Gateway Cognito authorizer)

## Response Format

### Success Response (200)

```json
{
  "status": "200",
  "message": "Group deleted successfully",
  "data": {}
}
```

### Error Responses

#### 400 - Bad Request

```json
{
  "status": "400",
  "message": "Missing group ID",
  "data": {}
}
```

#### 404 - Not Found

```json
{
  "status": "404",
  "message": "Group with ID 'groupId' not found",
  "data": {}
}
```

#### 500 - Internal Server Error

```json
{
  "status": "500",
  "message": "Internal server error: {error details}",
  "data": {}
}
```

## Environment Variables

| Variable               | Description                                | Required              |
| ---------------------- | ------------------------------------------ | --------------------- |
| `AUTH_TABLE_NAME`      | DynamoDB table name for authorization data | Yes                   |
| `COGNITO_USER_POOL_ID` | Cognito User Pool ID                       | Yes                   |
| `LOG_LEVEL`            | Logging level (INFO, WARNING, ERROR)       | No (default: WARNING) |

## IAM Permissions Required

### DynamoDB Permissions

- `dynamodb:GetItem` - Check if group exists
- `dynamodb:Query` - Get all group-related items
- `dynamodb:BatchWriteItem` - Delete group items in batches

### Cognito Permissions

- `cognito-idp:DeleteGroup` - Delete Cognito group
- `cognito-idp:CreateGroup` - Restore group during rollback
- `cognito-idp:GetGroup` - Verify group existence

## DynamoDB Data Structure

The function deletes the following items:

### Group Metadata

```
PK: "GROUP#{groupId}"
SK: "METADATA"
```

### Group Memberships

```
PK: "GROUP#{groupId}"
SK: "MEMBER#{userId}"
```

## Rollback Logic

The function implements sophisticated rollback logic:

1. **Backup Phase**: Before deletion, all group-related DynamoDB items are backed up in memory
2. **Cognito Deletion**: Group is deleted from Cognito first
3. **DynamoDB Deletion**: Group items are deleted from DynamoDB in batches
4. **Rollback Trigger**: If DynamoDB deletion fails after successful Cognito deletion:
   - The function attempts to recreate the Cognito group
   - Uses original group description from backed-up metadata
   - Logs rollback success/failure for monitoring

## Monitoring and Metrics

The function emits CloudWatch metrics:

- `GroupNotFoundError` - Group not found in DynamoDB
- `MissingUserIdError` - User ID missing from context
- `MissingConfigError` - Environment variables not configured
- `CognitoGroupDeleted` - Cognito group successfully deleted
- `DynamoDBGroupDeleted` - DynamoDB items successfully deleted
- `GroupDeletionError` - General deletion errors
- `CognitoRollbackSuccess` - Successful rollback of Cognito group
- `CognitoRollbackError` - Failed rollback attempt
- `SuccessfulGroupDeletion` - Complete successful deletion

## Error Handling

- **Validation Errors**: Input validation with Pydantic models
- **Authorization Errors**: Missing user context or insufficient permissions
- **Resource Not Found**: Group doesn't exist in DynamoDB
- **Cognito Errors**: Group not found in Cognito (continues with DynamoDB deletion)
- **DynamoDB Errors**: Batch write failures with automatic retry logic
- **Rollback Errors**: Logs but doesn't fail the operation

## Usage Examples

### Delete a Group

```bash
curl -X DELETE \
  'https://api.medialake.ai/groups/engineering-team' \
  -H 'Authorization: Bearer {jwt-token}'
```

### Success Response

```json
{
  "status": "200",
  "message": "Group deleted successfully",
  "data": {}
}
```

## Integration with CDK

The function is deployed via CDK with:

- Entry point: `lambdas/api/groups/rp_groupId/del_groupId`
- Method: DELETE on `/groups/{groupId}` resource
- Authorizer: Cognito User Pool
- Environment variables injected from CDK stack
- IAM permissions automatically assigned

## Related Functions

- **POST** `/groups` - Create groups ([post_groups](../../../post_groups/))
- **GET** `/groups` - List groups ([get_groups](../../../get_groups/))
- **GET** `/groups/{groupId}` - Get specific group ([get_groupId](../get_groupId/))
- **PATCH** `/groups/{groupId}` - Update group ([patch_groupId](../patch_groupId/))

## Testing

The function supports Lambda warmer for performance:

```json
{
  "lambda_warmer": true
}
```

## Security Considerations

1. **Authorization**: User must be authenticated via Cognito
2. **Input Validation**: All inputs validated with Pydantic schemas
3. **Error Handling**: No sensitive information leaked in error messages
4. **Audit Trail**: All operations logged with correlation IDs
5. **Rollback Safety**: Failed operations don't leave system in inconsistent state
