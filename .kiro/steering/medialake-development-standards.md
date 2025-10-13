# MediaLake Development Standards

## Project Overview
MediaLake is a comprehensive serverless media processing platform on AWS that provides media ingestion, processing, management, and workflow orchestration. The platform uses AWS CDK for infrastructure as code and follows a modular, scalable architecture.

## Architecture Principles

### Serverless-First Design
- All components should leverage AWS serverless services (Lambda, Step Functions, EventBridge, etc.)
- Avoid EC2 instances unless absolutely necessary for specific processing requirements
- Use managed services to reduce operational overhead

### Event-Driven Architecture
- Use EventBridge for decoupled event routing between components
- Implement FIFO SQS queues for ordered processing workflows
- Design for eventual consistency and idempotent operations

### Modular Component Design
- Separate concerns into distinct CDK constructs and stacks
- Each Lambda function should have a single responsibility
- Use shared libraries for common functionality across Lambda functions

## Code Organization Standards

### Directory Structure
Follow the established project structure:
- `medialake_constructs/` - Reusable CDK constructs
- `medialake_stacks/` - CDK stack definitions
- `lambdas/` - Lambda function source code organized by domain
- `medialake_user_interface/` - React TypeScript frontend

### Naming Conventions
- Use the ResourceNames class from constants.py for consistent naming
- Lambda functions: `{app_prefix}-lambda-{name}-{environment}`
- S3 buckets: `{app_prefix}-s3-{name}-{environment}`
- DynamoDB tables: `{app_prefix}-ddb-{name}-{environment}`
- Use kebab-case for resource names and snake_case for Python variables

### Configuration Management
- All configuration should be centralized in config.json
- Use the config.py module for accessing configuration values
- Environment-specific settings should be parameterized
- Sensitive values should use AWS Systems Manager Parameter Store or Secrets Manager

## Lambda Development Standards

### Function Structure
- Use the common middleware pattern from `lambdas/common_libraries/lambda_middleware.py`
- Implement proper error handling with `lambda_error_handler.py`
- Include logging using the utilities from `lambda_utils.py`
- Keep functions focused on a single responsibility

### Memory and Timeout Configuration
- Use constants from the Lambda class in constants.py
- Default memory: 256MB, timeout: 60 seconds
- Long-running functions: 900 seconds maximum
- Adjust based on actual performance requirements

### Dependencies
- Use Lambda layers for shared dependencies
- Keep deployment packages minimal
- Pin dependency versions in requirements.txt files

## API Development Standards

### API Gateway Structure
- Use the modular API Gateway constructs in `medialake_constructs/api_gateway/`
- Group related endpoints by domain (assets, users, pipelines, etc.)
- Implement consistent error responses and status codes
- Use Cognito User Pools for authentication

### Request/Response Patterns
- Follow RESTful conventions for endpoint design
- Use consistent JSON response structures
- Implement proper CORS configuration
- Include request validation and sanitization

### Documentation
- Maintain OpenAPI specifications for all endpoints
- Document request/response schemas
- Include example requests and responses

## Database Design Standards

### DynamoDB Best Practices
- Use single-table design where appropriate
- Design partition keys to distribute load evenly
- Use GSIs sparingly and only when necessary
- Implement proper error handling for throttling

### Table Naming
- Use the DynamoDB class methods from constants.py for table names
- Include environment suffix for multi-environment deployments
- Use descriptive names that indicate the data stored

## Frontend Development Standards

### React/TypeScript Structure
- Use feature-based organization in the src/ directory
- Implement proper TypeScript types for all API responses
- Use React hooks for state management
- Follow the established component patterns

### API Integration
- Use the service layer pattern in src/api/
- Implement proper error handling for API calls
- Use consistent loading and error states
- Cache API responses where appropriate

## Testing Standards

### Unit Testing
- Write unit tests for all Lambda functions
- Test business logic separately from AWS service integrations
- Use mocking for external dependencies
- Aim for high code coverage on critical paths

### Integration Testing
- Use Playwright for end-to-end testing
- Test complete user workflows
- Include tests for error scenarios
- Maintain test data fixtures

### Infrastructure Testing
- Test CDK constructs and stacks
- Validate resource configurations
- Test IAM permissions and security policies

## Security Standards

### Authentication and Authorization
- Use AWS Cognito for user authentication
- Implement proper RBAC using permission sets
- Validate all user inputs
- Use least-privilege IAM policies

### Data Protection
- Encrypt data at rest using AWS KMS
- Use HTTPS for all API communications
- Implement proper CORS policies
- Sanitize all user inputs

### Secrets Management
- Never commit secrets to version control
- Use AWS Secrets Manager or Parameter Store
- Rotate secrets regularly
- Use IAM roles instead of access keys where possible

## Performance Standards

### Lambda Optimization
- Use connection pooling for database connections
- Implement proper caching strategies
- Monitor cold start times and optimize accordingly
- Use provisioned concurrency for critical functions

### Database Performance
- Design efficient query patterns
- Use appropriate read/write capacity settings
- Monitor and optimize based on CloudWatch metrics
- Implement proper retry logic with exponential backoff

## Monitoring and Observability

### Logging Standards
- Use structured logging with consistent formats
- Include correlation IDs for request tracing
- Log at appropriate levels (ERROR, WARN, INFO, DEBUG)
- Use CloudWatch Logs for centralized logging

### Metrics and Alarms
- Monitor key business metrics
- Set up alarms for error rates and latency
- Use X-Ray for distributed tracing
- Create CloudWatch dashboards for operational visibility

## Deployment Standards

### CDK Best Practices
- Use CDK constructs for reusable components
- Implement proper stack dependencies
- Use CDK context for environment-specific values
- Tag all resources consistently

### CI/CD Pipeline
- Use AWS CodePipeline for deployment automation
- Implement proper testing stages
- Use blue-green deployments for critical services
- Include rollback procedures

### Environment Management
- Maintain separate environments (dev, staging, prod)
- Use consistent configuration across environments
- Implement proper promotion processes
- Document environment-specific differences

## Documentation Standards

### Code Documentation
- Include docstrings for all Python functions and classes
- Document complex business logic
- Maintain README files for each major component
- Keep documentation up to date with code changes

### Architecture Documentation
- Maintain architecture diagrams
- Document data flow and integration points
- Include deployment and operational procedures
- Document troubleshooting guides

## Error Handling Standards

### Lambda Error Handling
- Use the common error handler from lambda_error_handler.py
- Implement proper retry logic with exponential backoff
- Log errors with sufficient context for debugging
- Return appropriate HTTP status codes

### Pipeline Error Handling
- Implement error handling in Step Functions
- Use dead letter queues for failed messages
- Provide clear error messages for troubleshooting
- Implement proper alerting for critical failures