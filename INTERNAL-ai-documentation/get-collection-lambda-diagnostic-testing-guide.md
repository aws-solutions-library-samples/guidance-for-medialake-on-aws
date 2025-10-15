# Get Collection Lambda Diagnostic Testing Guide

## Overview

This document provides step-by-step instructions for deploying and testing the get_collection Lambda with enhanced diagnostic logging to identify the root cause of the user context extraction error.

## Error Being Diagnosed

```
"message": "Failed to extract user context",
"error": "'str' object has no attribute 'get'",
"operation": "extract_user_context"
```

## Hypothesis

The error occurs because the `event` parameter in `extract_user_context()` is being passed as a string instead of a dictionary, causing the failure at `event.get("requestContext")`.

## Deployment Instructions

### Step 1: Deploy Updated Lambda

```bash
# Navigate to project root
cd /Users/raverrr/codebase/gitlab-guidance-for-medialake-on-aws

# Deploy the Collections stack with updated get_collection Lambda
cdk deploy CollectionsStack --require-approval never

# Or if using specific deployment commands:
cdk deploy --all --require-approval never
```

### Step 2: Verify Deployment

```bash
# Check Lambda function version/update time
aws lambda get-function --function-name <get-collection-lambda-name>
```

## Testing Instructions

### Step 3: Trigger the Failing Endpoint

Make a request to the get_collection endpoint that was previously failing:

```bash
# Example API call (adjust URL and collection ID as needed)
curl -X GET "https://your-api-gateway-url/api/collections/your-collection-id" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

### Step 4: Check CloudWatch Logs

1. Go to AWS CloudWatch Console
2. Navigate to Log Groups
3. Find the log group for get_collection Lambda (usually `/aws/lambda/get-collection-function-name`)
4. Look for the most recent log stream
5. Search for "DIAGNOSTIC: extract_user_context called"

## Expected Diagnostic Output

### If Hypothesis is CORRECT (event is string):

```json
{
  "message": "DIAGNOSTIC: extract_user_context called",
  "event_type": "str",
  "event_is_dict": false,
  "event_is_str": true,
  "event_keys": "NOT_A_DICT",
  "event_preview": "{\"requestContext\":{\"requestId\":\"...\",\"authorizer\":{...}}",
  "operation": "extract_user_context_diagnostic"
}
```

### If Hypothesis is WRONG (event is dict):

```json
{
  "message": "DIAGNOSTIC: extract_user_context called",
  "event_type": "dict",
  "event_is_dict": true,
  "event_is_str": false,
  "event_keys": ["requestContext", "pathParameters", "queryStringParameters", ...],
  "event_preview": "NOT_A_STRING",
  "operation": "extract_user_context_diagnostic"
}
```

## Next Steps After Testing

### If Event is String (Hypothesis Confirmed):

1. Report diagnostic results confirming string event
2. Apply robust fix that handles both string and dict event formats
3. Add JSON parsing logic for string events

### If Event is Dict (Hypothesis Wrong):

1. Report diagnostic results showing dict event
2. Investigate deeper into event structure
3. Look for nested string properties or malformed event data
4. May need additional diagnostic logging

## Troubleshooting

### No Diagnostic Logs Appear:

- Check if deployment was successful
- Verify correct Lambda function was updated
- Confirm API request reached the Lambda (check access logs)
- Try multiple test requests

### Deployment Issues:

```bash
# Check CDK diff to see what will change
cdk diff CollectionsStack

# Force deployment if needed
cdk deploy CollectionsStack --force
```

### Lambda Not Updating:

- Check for deployment errors in CDK output
- Verify Lambda function permissions
- Confirm correct environment and region

## Clean Up After Testing

Once diagnostic results are obtained and root cause confirmed, the diagnostic logging can be removed and replaced with the production fix.

## Contact

Report diagnostic results and any issues encountered during testing for immediate analysis and next steps.
