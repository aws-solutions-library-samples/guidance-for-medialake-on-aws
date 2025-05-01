# UPSF API Test Plan

## Overview
This test plan covers the core functionality of the User Profile, Settings, and Favorites (UPSF) API endpoints. The tests will verify that the endpoints work as expected, handle valid and invalid inputs correctly, and interact with the DynamoDB user table as designed.

## Prerequisites
- The UPSF API is deployed to the development environment
- A valid Cognito user is available for testing
- The DynamoDB user table exists and is accessible

## Authentication
All tests will use Cognito authentication. We'll need to:
1. Authenticate with Cognito to get an ID token
2. Include the ID token in the Authorization header of all API requests

## Test Cases

### 1. User Profile Endpoints

#### 1.1 GET /users/profile
- **Test Case 1.1.1:** Get user profile with valid authentication
  - **Expected Result:** 200 OK with user profile data
  - **Verification:** Check that the response contains the expected user profile fields

- **Test Case 1.1.2:** Get user profile with invalid authentication
  - **Expected Result:** 401 Unauthorized
  - **Verification:** Check that the response contains an appropriate error message

#### 1.2 PUT /users/profile
- **Test Case 1.2.1:** Update user profile with valid data
  - **Expected Result:** 200 OK with updated profile data
  - **Verification:** Check that the response contains the updated fields and verify in DynamoDB

- **Test Case 1.2.2:** Update user profile with invalid data (missing required fields)
  - **Expected Result:** 400 Bad Request
  - **Verification:** Check that the response contains an appropriate error message

- **Test Case 1.2.3:** Update user profile with protected fields (should be sanitized)
  - **Expected Result:** 200 OK with updated profile data, protected fields unchanged
  - **Verification:** Check that the protected fields are not updated in the response or in DynamoDB

### 2. User Settings Endpoints

#### 2.1 GET /users/settings
- **Test Case 2.1.1:** Get all user settings with valid authentication
  - **Expected Result:** 200 OK with all user settings
  - **Verification:** Check that the response contains the expected settings structure

- **Test Case 2.1.2:** Get user settings with namespace filter
  - **Expected Result:** 200 OK with filtered settings
  - **Verification:** Check that the response only contains settings for the specified namespace

- **Test Case 2.1.3:** Get user settings with invalid authentication
  - **Expected Result:** 401 Unauthorized
  - **Verification:** Check that the response contains an appropriate error message

#### 2.2 PUT /users/settings/{namespace}/{key}
- **Test Case 2.2.1:** Update user setting with valid data
  - **Expected Result:** 200 OK with updated setting data
  - **Verification:** Check that the response contains the updated setting and verify in DynamoDB

- **Test Case 2.2.2:** Update user setting with invalid data (missing value)
  - **Expected Result:** 400 Bad Request
  - **Verification:** Check that the response contains an appropriate error message

- **Test Case 2.2.3:** Update user setting with invalid namespace or key
  - **Expected Result:** 400 Bad Request
  - **Verification:** Check that the response contains an appropriate error message

### 3. User Favorites Endpoints

#### 3.1 POST /users/favorites
- **Test Case 3.1.1:** Add favorite with valid data
  - **Expected Result:** 201 Created with favorite data
  - **Verification:** Check that the response contains the added favorite and verify in DynamoDB

- **Test Case 3.1.2:** Add favorite with invalid data (missing required fields)
  - **Expected Result:** 400 Bad Request
  - **Verification:** Check that the response contains an appropriate error message

- **Test Case 3.1.3:** Add favorite with invalid itemType
  - **Expected Result:** 400 Bad Request
  - **Verification:** Check that the response contains an appropriate error message

#### 3.2 GET /users/favorites
- **Test Case 3.2.1:** Get all user favorites with valid authentication
  - **Expected Result:** 200 OK with all user favorites
  - **Verification:** Check that the response contains the expected favorites structure

- **Test Case 3.2.2:** Get user favorites with itemType filter
  - **Expected Result:** 200 OK with filtered favorites
  - **Verification:** Check that the response only contains favorites for the specified itemType

- **Test Case 3.2.3:** Get user favorites with invalid authentication
  - **Expected Result:** 401 Unauthorized
  - **Verification:** Check that the response contains an appropriate error message

#### 3.3 DELETE /users/favorites/{itemType}/{itemId}
- **Test Case 3.3.1:** Delete favorite with valid itemType and itemId
  - **Expected Result:** 200 OK with deletion result
  - **Verification:** Check that the response indicates successful removal and verify in DynamoDB

- **Test Case 3.3.2:** Delete favorite with non-existent itemType and itemId
  - **Expected Result:** 200 OK with indication that favorite was not found
  - **Verification:** Check that the response indicates the favorite was not found

- **Test Case 3.3.3:** Delete favorite with invalid itemType
  - **Expected Result:** 400 Bad Request
  - **Verification:** Check that the response contains an appropriate error message

## Test Script
A Python script will be created to execute these test cases and report the results.