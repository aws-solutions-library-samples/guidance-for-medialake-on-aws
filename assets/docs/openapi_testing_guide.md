# Testing the MediaLake OpenAPI Specification

This guide provides instructions for testing the MediaLake OpenAPI specification using popular redoc

## Setup

1. Install Redoc CLI:

   ```bash
   npm install -g @redocly/cli
   ```

2. Run Linting using redocly

   ```bash
   redocly lint assets/docs/openapi.yaml
   ```

3. Serve the OpenAPI specification with Redoc:

   ```bash
   redoc-cli serve assets/docs/openapi.yaml
   ```

4. Open your browser and navigate to `http://localhost:8080` to view the API documentation.

## Testing Checklist

When testing your OpenAPI specification, ensure the following:

- [ ] All endpoints are properly documented
- [ ] Request and response schemas are correctly defined
- [ ] Examples are provided for requests and responses
- [ ] Security schemes are properly configured
- [ ] Error responses are documented
- [ ] Parameter validation rules are correctly defined
- [ ] Required fields are marked as required
- [ ] Enum values are correctly specified
- [ ] Descriptions are clear and informative
- [ ] Tags are used consistently
- [ ] Operation IDs are unique and descriptive

## Next Steps

After testing your OpenAPI specification, consider the following next steps:

1. Fix any issues identified during testing
2. Implement the API based on the specification
3. Set up automated testing to ensure the API implementation matches the specification
4. Publish the API documentation for developers to use
