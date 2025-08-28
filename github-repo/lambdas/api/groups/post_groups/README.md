# Post Groups Lambda Function

This Lambda function handles the creation of groups in both DynamoDB and Amazon Cognito with transactional integrity and automatic rollback capabilities.

## Overview

The function creates groups in two systems:

1. **DynamoDB**: Stores group metadata in the auth table following the authorization schema
2. **Amazon Cognito**: Creates the group for user management and authentication

If either operation fails, the function automatically rolls back any completed operations to maintain data consistency.

## Schema

The function follows this DynamoDB schema for group storage:

```json
{
  "PK": "GROUP#{groupId}",
  "SK": "METADATA",
  "assignedPermissionSets": ["permissionSet1", "permissionSet2"],
  "createdAt": "2025-06-15T04:22:09.990787",
  "department": "IT",
  "description": "Group description",
  "entity": "group",
  "id": "groupId",
  "name": "Display Name",
  "updatedAt": "2025-06-15T04:22:09.990787"
}
```

## Request Format

```json
{
  "name": "MediaLake Super Admin",
  "id": "administrators",
  "description": "System administrators with full access to all features and settings",
  "department": "IT",
  "assignedPermissionSets": ["superAdministrator"]
}
```

### Required Fields

- `name`: Display name of the group
- `id`: Unique identifier (alphanumeric and underscores only)
- `description`: Description of the group

### Optional Fields

- `department`: Department associated with the group
- `assignedPermissionSets`: Array of permission sets assigned to the group

## Response Format

### Success (201)

```json
{
  "status": "201",
  "message": "Group created successfully",
  "data": {
    "id": "administrators",
    "name": "MediaLake Super Admin",
    "description": "System administrators with full access to all features and settings",
    "department": "IT",
    "assignedPermissionSets": ["superAdministrator"],
    "createdAt": "2025-06-15T04:22:09.990787",
    "updatedAt": "2025-06-15T04:22:09.990787",
    "entity": "group"
  }
}
```

### Error (400/500)

```json
{
  "status": "400",
  "message": "Group with ID 'administrators' already exists",
  "data": {}
}
```

## Rollback Logic

The function implements a two-phase creation process:

1. **Phase 1**: Create Cognito group
2. **Phase 2**: Create DynamoDB entry

If Phase 2 fails, the function automatically deletes the Cognito group created in Phase 1.

## Environment Variables

- `AUTH_TABLE_NAME`: Name of the DynamoDB auth table
- `COGNITO_USER_POOL_ID`: ID of the Cognito User Pool
- `LOG_LEVEL`: Logging level (default: WARNING)

## IAM Permissions Required

- DynamoDB: `dynamodb:PutItem`, `dynamodb:DeleteItem`
- Cognito: `cognito-idp:CreateGroup`, `cognito-idp:DeleteGroup`, `cognito-idp:GetGroup`, `cognito-idp:ListGroups`

## Error Handling

The function handles various error scenarios:

- **Validation Errors**: Invalid request format or missing required fields
- **Duplicate Groups**: Group ID already exists in either DynamoDB or Cognito
- **Permission Errors**: Insufficient IAM permissions
- **Service Errors**: AWS service failures

All errors are logged with appropriate metrics for monitoring and debugging.

## Monitoring

The function includes comprehensive CloudWatch metrics:

- `SuccessfulGroupCreation`: Successful group creations
- `CognitoGroupCreated`: Cognito group creations
- `DynamoDBGroupCreated`: DynamoDB entry creations
- `GroupCreationError`: General creation errors
- `CognitoRollbackSuccess`/`DynamoDBRollbackSuccess`: Successful rollbacks
- Various error metrics for different failure scenarios

## Usage

This function is automatically deployed and configured through the `GroupsStack` CDK stack and is accessible via the `/groups` POST endpoint in the API Gateway.
