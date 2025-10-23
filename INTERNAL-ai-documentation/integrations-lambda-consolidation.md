# Integrations API Lambda Consolidation

## Overview

This document describes the refactoring of the Integrations API from multiple separate Lambda functions to a single consolidated Lambda using AWS Lambda Powertools routing pattern, matching the architecture established by the Collections API.

**Date:** October 21, 2025
**Status:** Completed

## Changes Summary

### Before: Multiple Lambda Functions

The integrations API previously consisted of 4 separate Lambda functions:

- `lambdas/api/integrations/get_integrations/` - GET /integrations
- `lambdas/api/integrations/post_integrations/` - POST /integrations
- `lambdas/api/integrations/rp_integrationsId/put_integrationsId/` - PUT /integrations/{id}
- `lambdas/api/integrations/rp_integrationsId/del_integrationsId/` - DELETE /integrations/{id}

Each Lambda had its own:

- Separate deployment package
- Individual IAM roles and permissions
- Dedicated API Gateway method integration

### After: Single Consolidated Lambda

All integrations functionality is now handled by a single Lambda function at `lambdas/api/integrations_api/` using AWS Lambda Powertools `APIGatewayRestResolver` for routing.

## New Directory Structure

```
lambdas/api/integrations_api/
├── index.py                          # Main Lambda handler with routing setup
├── requirements.txt                  # Pydantic dependency
├── handlers/                         # Handler modules for each endpoint
│   ├── __init__.py                  # Route registration
│   ├── integrations_get.py          # GET /integrations
│   ├── integrations_post.py         # POST /integrations
│   ├── integrations_ID_put.py       # PUT /integrations/{id}
│   └── integrations_ID_delete.py    # DELETE /integrations/{id}
├── models/                           # Pydantic V2 validation models
│   ├── __init__.py
│   └── integration_models.py        # Request/response models
└── utils/                            # Shared utilities
    ├── __init__.py
    ├── formatting_utils.py          # Data formatting functions
    ├── response_utils.py            # Standard response formatting
    └── secrets_utils.py             # AWS Secrets Manager operations
```

## Key Components

### 1. Main Lambda Handler (`index.py`)

- Initializes AWS Lambda Powertools (Logger, Tracer, Metrics)
- Configures CORS settings
- Sets up `APIGatewayRestResolver` with JSON serialization
- Imports and registers all route handlers
- Provides centralized error handling

### 2. Route Handlers (`handlers/`)

Each handler file contains:

- A single `register_route(app)` function that decorates the endpoint
- Request validation using Pydantic V2 models
- Business logic for the specific operation
- Proper error handling and logging
- CloudWatch metrics tracking

**Endpoints:**

- `GET /integrations` - List all integrations with formatting
- `POST /integrations` - Create new integration with validation
- `PUT /integrations/{integration_id}` - Update existing integration
- `DELETE /integrations/{integration_id}` - Delete integration and associated secrets

### 3. Pydantic Models (`models/`)

Type-safe request/response models using Pydantic V2:

**Request Models:**

- `CreateIntegrationRequest` - Validation for creating integrations
- `UpdateIntegrationRequest` - Validation for updating integrations with at least one field required

**Response Models:**

- `IntegrationResponse` - Standardized integration response format

**Supporting Models:**

- `IntegrationStatus` - Enum for integration status (active/inactive)
- `AuthType` - Enum for authentication types (apiKey)
- `AuthConfig` - Authentication configuration structure
- `AuthCredentials` - Authentication credentials structure

### 4. Utility Modules (`utils/`)

**`formatting_utils.py`:**

- `format_integration()` - Converts DynamoDB items to API response format
- Handles name generation from nodeId
- Sanitizes sensitive data in configurations

**`response_utils.py`:**

- `create_success_response()` - Standard success response with metadata
- `create_error_response()` - Standard error response with metadata
- Consistent timestamp and request ID tracking

**`secrets_utils.py`:**

- `store_api_key_secret()` - Create API key secrets in Secrets Manager
- `update_api_key_secret()` - Update or create API key secrets
- `delete_api_key_secret()` - Delete API key secrets (graceful failure)

## Infrastructure Changes

### API Gateway Construct (`api_gateway_integrations.py`)

**Before:**

- 4 separate Lambda constructs
- 4 separate `LambdaIntegration` instances
- Individual HTTP method routing (GET, POST, PUT, DELETE)
- Separate CORS configurations

**After:**

- Single `Lambda` construct: `IntegrationsLambda`
- Single `LambdaIntegration` with `proxy=True`
- `ANY` method for `/integrations` resource
- `ANY` method for `/integrations/{integration_id}` resource
- Unified CORS configuration

**Key Changes:**

```python
# Single Lambda with routing
integrations_lambda = Lambda(
    self,
    "IntegrationsLambda",
    config=LambdaConfig(
        name="integrations_api",
        entry="lambdas/api/integrations_api",
        environment_variables={...},
    ),
)

# Proxy integration for all methods
integrations_integration = apigateway.LambdaIntegration(
    integrations_lambda.function,
    proxy=True,
    allow_test_invoke=True,
)

# ANY method instead of individual methods
integrations_resource.add_method("ANY", integrations_integration)
integration_id_resource.add_method("ANY", integrations_integration)
```

### IAM Permissions

Consolidated permissions for the single Lambda:

- **DynamoDB**: Full CRUD on integrations table + GSI access
- **Secrets Manager**: Create, update, delete secrets under `integration/*` path
- **DynamoDB Tables**: Read access to pipelines_nodes_table and environments_table

### Environment Variables

The consolidated Lambda receives:

- `X_ORIGIN_VERIFY_SECRET_ARN` - Origin verification secret
- `INTEGRATIONS_TABLE` - Integrations DynamoDB table name
- `PIPELINES_NODES_TABLE` - Pipelines nodes table name
- `ENVIRONMENTS_TABLE` - Environments table name
- `ENVIRONMENT` - Current deployment environment

## Stack Changes

### `integrations_environment_stack.py`

**Circular Dependency Resolution:**

The stack had to be restructured to resolve a circular dependency between integrations and environments:

1. **Environments API created first** with optional integrations references
2. **Integrations API created second** with environments table reference
3. **Post-creation wiring** using setter methods

```python
# Create Environments API first
self._environments_api = ApiGatewayEnvironmentsConstruct(
    self, "EnvironmentsApiGateway",
    props=ApiGatewayEnvironmentsProps(
        integrations_table=None,  # Set later
        post_integrations_handler=None,  # Set later
        ...
    ),
)

# Create Integrations API with environments table
self._integrations_stack = ApiGatewayIntegrationsConstruct(
    self, "Integrations",
    props=ApiGatewayIntegrationsProps(
        environments_table=self._environments_api.environments_table.table,
        ...
    ),
)

# Wire up cross-references
self._environments_api.set_integrations_table(...)
self._environments_api.set_post_integrations_handler(...)
```

### `api_gateway_environments.py`

Added optional parameters and setter methods:

```python
@dataclass
class ApiGatewayEnvironmentsProps:
    integrations_table: Optional[dynamodb.TableV2] = None
    post_integrations_handler: Optional[lambda_.Function] = None
    ...

class ApiGatewayEnvironmentsConstruct:
    def set_integrations_table(self, integrations_table: dynamodb.TableV2) -> None:
        """Set integrations table after construction."""
        ...

    def set_post_integrations_handler(self, handler: lambda_.Function) -> None:
        """Set post integrations handler after construction."""
        ...
```

## Benefits of Consolidation

### 1. **Reduced Cold Start Impact**

- Single Lambda warm instance serves all endpoints
- Shared initialization of PowerTools, boto3 clients
- Faster response times for subsequent requests

### 2. **Simplified Deployment**

- One deployment package instead of four
- Easier version management
- Reduced CloudFormation complexity

### 3. **Code Reusability**

- Shared utilities across all handlers
- Common error handling patterns
- Consistent logging and metrics

### 4. **Improved Maintainability**

- Single codebase for all integrations operations
- Easier to add new endpoints
- Centralized configuration

### 5. **Better Development Experience**

- Clear separation of concerns
- Type-safe request/response handling with Pydantic
- Easy to test individual handlers
- Follows established Collections API pattern

### 6. **Cost Optimization**

- Fewer Lambda functions = lower costs
- Shared execution environment
- Reduced DynamoDB connection overhead

## Testing Considerations

### Unit Testing

- Test each handler independently
- Mock boto3 clients and DynamoDB tables
- Validate Pydantic models with various inputs
- Test error handling paths

### Integration Testing

- Test API Gateway proxy integration
- Verify CORS headers
- Test authorization flow
- Validate DynamoDB and Secrets Manager interactions

### Endpoints to Test

1. `GET /integrations` - List with various filters
2. `POST /integrations` - Create with valid/invalid data
3. `PUT /integrations/{id}` - Update with partial data
4. `DELETE /integrations/{id}` - Delete with cleanup

## Migration Notes

### Backwards Compatibility

The consolidation maintains API compatibility:

- Same endpoint paths
- Same request/response formats
- Same authentication mechanism
- Same error responses

### Deployment Steps

1. Deploy the new consolidated Lambda
2. Update API Gateway routes to use ANY methods
3. Remove old Lambda functions
4. Clean up old Lambda directories

### Rollback Plan

If issues arise:

1. Revert API Gateway routes to individual methods
2. Redeploy old Lambda functions
3. Update CDK construct to use old pattern

## Best Practices Applied

### 1. **AWS Lambda Powertools**

- Structured logging with correlation IDs
- Distributed tracing with X-Ray
- Custom metrics for CloudWatch
- Standard middleware decorators

### 2. **Pydantic V2 Validation**

- Type-safe request validation
- Automatic error messages
- Schema documentation
- Field-level validation rules

### 3. **Error Handling**

- Consistent error response format
- Proper HTTP status codes
- Detailed error logging
- Request ID tracking

### 4. **Security**

- API keys stored in Secrets Manager
- Sensitive data excluded from logs
- Custom authorization per endpoint
- Secure environment variable handling

### 5. **Monitoring**

- CloudWatch metrics for all operations
- Success/failure tracking
- Performance metrics
- Error rate monitoring

## Future Enhancements

### Potential Improvements

1. Add pagination for GET /integrations
2. Implement filtering and sorting options
3. Add batch operations support
4. Enhance validation with custom rules
5. Add integration health checks
6. Implement rate limiting

### Performance Optimizations

1. Add DynamoDB query optimization with GSIs
2. Implement caching for frequent reads
3. Use connection pooling for boto3 clients
4. Optimize Lambda memory allocation

## Related Documentation

- [Collections Lambda Implementation](./collections-lambda-implementation-verification.md)
- [AWS Lambda Powertools Documentation](https://docs.powertools.aws.dev/lambda/python/)
- [Pydantic V2 Documentation](https://docs.pydantic.dev/latest/)
- [API Gateway Proxy Integration](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html)

## References

### Files Modified

- `medialake_constructs/api_gateway/api_gateway_integrations.py`
- `medialake_constructs/api_gateway/api_gateway_environments.py`
- `medialake_stacks/integrations_environment_stack.py`

### Files Created

- `lambdas/api/integrations_api/index.py`
- `lambdas/api/integrations_api/requirements.txt`
- `lambdas/api/integrations_api/handlers/__init__.py`
- `lambdas/api/integrations_api/handlers/integrations_get.py`
- `lambdas/api/integrations_api/handlers/integrations_post.py`
- `lambdas/api/integrations_api/handlers/integrations_ID_put.py`
- `lambdas/api/integrations_api/handlers/integrations_ID_delete.py`
- `lambdas/api/integrations_api/models/__init__.py`
- `lambdas/api/integrations_api/models/integration_models.py`
- `lambdas/api/integrations_api/utils/__init__.py`
- `lambdas/api/integrations_api/utils/formatting_utils.py`
- `lambdas/api/integrations_api/utils/response_utils.py`
- `lambdas/api/integrations_api/utils/secrets_utils.py`

### Files Removed

- `lambdas/api/integrations/` (entire directory)

---

**Completed:** October 21, 2025
**Pattern:** Follows Collections API architecture
**Status:** Ready for deployment
