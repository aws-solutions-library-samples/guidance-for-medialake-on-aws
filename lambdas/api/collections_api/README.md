# Collections API - Consolidated Lambda

This directory contains the consolidated Collections API Lambda function that handles all collections-related endpoints using AWS Lambda Powertools routing.

## Overview

The Collections API has been refactored from multiple individual Lambda functions into a single Lambda function with internal routing. This approach:

- Reduces cold start times for collections operations
- Simplifies deployment and management
- Maintains clear separation of concerns through modular route files
- Uses AWS Lambda Powertools `APIGatewayRestResolver` for efficient routing

## Directory Structure

```
collections_api/
├── index.py              # Main Lambda handler with routing setup
├── requirements.txt      # Python dependencies
├── routes/              # Route modules (each handles specific endpoints)
│   ├── __init__.py
│   ├── collection_types_routes.py    # /collection-types endpoints
│   ├── collections_routes.py          # /collections list and create
│   ├── collection_detail_routes.py   # /collections/{id} CRUD
│   ├── items_routes.py               # /collections/{id}/items
│   ├── rules_routes.py               # /collections/{id}/rules
│   ├── shares_routes.py              # /collections/{id}/share
│   └── assets_routes.py              # /collections/{id}/assets
└── README.md            # This file
```

## Endpoints

All endpoints are now handled by a single Lambda function:

### Collection Types

- `GET /collection-types` - List collection types
- `POST /collection-types` - Create collection type

### Collections

- `GET /collections` - List collections with filtering
- `POST /collections` - Create a new collection
- `GET /collections/shared-with-me` - Get shared collections
- `GET /collections/{collectionId}` - Get collection details
- `PATCH /collections/{collectionId}` - Update collection
- `DELETE /collections/{collectionId}` - Delete collection

### Collection Items

- `GET /collections/{collectionId}/items` - List collection items
- `POST /collections/{collectionId}/items` - Add item to collection
- `POST /collections/{collectionId}/items/batch` - Batch add items
- `POST /collections/{collectionId}/items/batch-remove` - Batch remove items
- `PUT /collections/{collectionId}/items/{itemId}` - Update collection item
- `DELETE /collections/{collectionId}/items/{itemId}` - Remove item from collection

### Collection Rules

- `GET /collections/{collectionId}/rules` - List collection rules
- `POST /collections/{collectionId}/rules` - Create rule
- `PUT /collections/{collectionId}/rules/{ruleId}` - Update rule
- `DELETE /collections/{collectionId}/rules/{ruleId}` - Delete rule

### Collection Sharing

- `GET /collections/{collectionId}/share` - List collection shares
- `POST /collections/{collectionId}/share` - Share collection
- `DELETE /collections/{collectionId}/share/{userId}` - Unshare collection

### Collection Assets

- `GET /collections/{collectionId}/assets` - Get collection assets (with OpenSearch integration)

## Dependencies

The Lambda function depends on:

- **AWS Lambda Powertools** - For routing, logging, tracing, and metrics
- **boto3/botocore** - AWS SDK for Python
- **opensearch-py** - For OpenSearch integration (assets endpoint)
- **pydantic** - For data validation
- **Common Libraries** - Shared utilities from `/opt/python` (Lambda layer):
  - `collections_utils` - Collection-specific utilities
  - `user_auth` - Authentication and user context extraction

## Shared Utilities

The Lambda uses utilities from the `lambdas/common_libraries/` directory which are deployed as a Lambda layer:

- `collections_utils.py` - Collection constants, formatting, validation
- `user_auth.py` - User authentication and context extraction

## Infrastructure

The infrastructure (CDK) has been updated in:

- `medialake_constructs/api_gateway/api_gateway_collections.py`

Key changes:

- Single Lambda function deployment
- API Gateway proxy integration (`{proxy+}`)
- All routes handled by the same Lambda with internal routing
- Proper IAM permissions for DynamoDB and OpenSearch

## Deployment

To deploy the updated Collections API:

```bash
# From the project root
cdk deploy <your-stack-name>
```

## Testing

After deployment, test the endpoints to ensure:

1. All collection operations work correctly
2. Authentication is properly enforced
3. DynamoDB queries are efficient
4. Error handling works as expected

Example test:

```bash
# List collections
curl -X GET \
  https://your-api.execute-api.region.amazonaws.com/prod/collections \
  -H 'Authorization: Bearer <token>'

# Create collection
curl -X POST \
  https://your-api.execute-api.region.amazonaws.com/prod/collections \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"name": "Test Collection", "description": "Test"}'
```

## Migration Notes

### What Changed

1. **Multiple Lambdas → Single Lambda**: All collections endpoints now route through one Lambda function
2. **Individual handlers → Route modules**: Logic organized into route modules under `routes/`
3. **API Gateway Integration**: Changed from individual integrations to proxy integration
4. **Shared Logic**: Common utilities remain in `common_libraries/` (Lambda layer)

### What Stayed the Same

- DynamoDB table structure and GSIs
- Authentication and authorization logic
- Response formats and error handling
- Business logic for each operation

### Old Lambda Locations (can be removed after testing)

The old individual lambda functions are still in:

- `lambdas/api/collections/collection-types/`
- `lambdas/api/collections/collections/`
- `lambdas/api/collections/collection/`

**Important**: Only remove these after thoroughly testing the new consolidated lambda.

## Monitoring and Observability

The Lambda uses AWS Lambda Powertools for:

- **Logging**: Structured JSON logging with correlation IDs
- **Tracing**: AWS X-Ray tracing for performance monitoring
- **Metrics**: Custom CloudWatch metrics for:
  - Successful/failed operations
  - Validation errors
  - Unexpected errors

View metrics in CloudWatch under namespace: `medialake`

## Development

To add new endpoints:

1. Create or update the appropriate route module in `routes/`
2. Register route handlers with the app resolver
3. Follow existing patterns for error handling and response formatting
4. Use shared utilities from `collections_utils` and `user_auth`
5. Add appropriate logging, tracing, and metrics

Example:

```python
def register_routes(app, dynamodb, table_name):
    @app.get("/collections/<collection_id>/new-endpoint")
    @tracer.capture_method
    def new_endpoint(collection_id: str):
        try:
            # Implementation
            return create_success_response(data=result)
        except Exception as e:
            logger.exception("Error", exc_info=e)
            return create_error_response(...)
```

## Troubleshooting

### Lambda not routing correctly

- Check CloudWatch logs for routing errors
- Verify API Gateway proxy integration is configured correctly
- Ensure all route modules are properly imported in `index.py`

### DynamoDB permission errors

- Verify Lambda execution role has proper permissions
- Check environment variables are set correctly

### Cold starts

- Monitor cold start metrics in CloudWatch
- Consider provisioned concurrency for high-traffic endpoints

## Support

For issues or questions, refer to:

- Project documentation in `/design/`
- Internal documentation in `/INTERNAL-ai-documentation/`
- AWS Lambda Powertools documentation: https://docs.powertools.aws.dev/
