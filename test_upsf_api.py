#!/usr/bin/env python3
"""
Test script for the UPSF API endpoints.
This script tests the User Profile, Settings, and Favorites API endpoints.
"""

import boto3
import json
import requests
import time
import uuid
from typing import Dict, Any, List, Optional

# Configuration
# Replace these values with your actual configuration
API_ENDPOINT = "https://api.dev.medialake.example.com"  # Replace with your API Gateway endpoint
USER_POOL_ID = "us-west-2_abcdefghi"  # Replace with your Cognito User Pool ID
CLIENT_ID = "1234567890abcdefghijklmno"  # Replace with your Cognito App Client ID
USERNAME = "test@example.com"  # Replace with your test user email
PASSWORD = "TestPassword123!"  # Replace with your test user password

# DynamoDB configuration
REGION = "us-west-2"  # Replace with your AWS region
USER_TABLE_NAME = "medialake-user-dev"  # Replace with your actual user table name

# Initialize AWS clients
cognito_idp = boto3.client('cognito-idp', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)
user_table = dynamodb.Table(USER_TABLE_NAME)

# Test results tracking
test_results = {
    "passed": 0,
    "failed": 0,
    "total": 0,
    "details": []
}


def authenticate() -> str:
    """
    Authenticate with Cognito and return the ID token.
    """
    try:
        response = cognito_idp.initiate_auth(
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': USERNAME,
                'PASSWORD': PASSWORD
            },
            ClientId=CLIENT_ID
        )
        return response['AuthenticationResult']['IdToken']
    except Exception as e:
        print(f"Authentication failed: {str(e)}")
        raise


def make_request(method: str, endpoint: str, token: str, data: Optional[Dict] = None) -> Dict:
    """
    Make a request to the API Gateway endpoint.
    """
    url = f"{API_ENDPOINT}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=headers, json=data)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        return {
            "status_code": response.status_code,
            "body": response.json() if response.text else {}
        }
    except Exception as e:
        print(f"Request failed: {str(e)}")
        return {
            "status_code": 500,
            "body": {"error": str(e)}
        }


def check_dynamodb_item(user_id: str, item_key: str) -> Dict:
    """
    Check if an item exists in the DynamoDB table.
    """
    try:
        formatted_user_id = f"USER#{user_id}"
        response = user_table.get_item(
            Key={
                "userId": formatted_user_id,
                "itemKey": item_key
            }
        )
        return response.get("Item", {})
    except Exception as e:
        print(f"DynamoDB query failed: {str(e)}")
        return {}


def run_test(test_name: str, test_func, *args, **kwargs) -> Dict:
    """
    Run a test and record the result.
    """
    print(f"\nRunning test: {test_name}")
    test_results["total"] += 1
    
    try:
        result = test_func(*args, **kwargs)
        if result["passed"]:
            test_results["passed"] += 1
            print(f"✅ Test passed: {test_name}")
        else:
            test_results["failed"] += 1
            print(f"❌ Test failed: {test_name}")
            print(f"   Reason: {result['message']}")
        
        test_results["details"].append({
            "name": test_name,
            "passed": result["passed"],
            "message": result["message"]
        })
        
        return result
    except Exception as e:
        test_results["failed"] += 1
        message = f"Test threw an exception: {str(e)}"
        print(f"❌ Test failed: {test_name}")
        print(f"   Reason: {message}")
        
        test_results["details"].append({
            "name": test_name,
            "passed": False,
            "message": message
        })
        
        return {
            "passed": False,
            "message": message
        }


def test_get_profile(token: str) -> Dict:
    """
    Test Case 1.1.1: Get user profile with valid authentication
    """
    response = make_request("GET", "/users/profile", token)
    
    if response["status_code"] != 200:
        return {
            "passed": False,
            "message": f"Expected status code 200, got {response['status_code']}"
        }
    
    body = response["body"]
    if "data" not in body:
        return {
            "passed": False,
            "message": "Response body does not contain 'data' field"
        }
    
    data = body["data"]
    required_fields = ["userId"]
    for field in required_fields:
        if field not in data:
            return {
                "passed": False,
                "message": f"Response data does not contain required field: {field}"
            }
    
    return {
        "passed": True,
        "message": "User profile retrieved successfully",
        "data": data
    }


def test_update_profile(token: str) -> Dict:
    """
    Test Case 1.2.1: Update user profile with valid data
    """
    # Generate a unique display name to verify the update
    display_name = f"Test User {uuid.uuid4().hex[:8]}"
    
    update_data = {
        "displayName": display_name,
        "preferences": {
            "theme": "dark",
            "notifications": True
        }
    }
    
    response = make_request("PUT", "/users/profile", token, update_data)
    
    if response["status_code"] != 200:
        return {
            "passed": False,
            "message": f"Expected status code 200, got {response['status_code']}"
        }
    
    body = response["body"]
    if "data" not in body:
        return {
            "passed": False,
            "message": "Response body does not contain 'data' field"
        }
    
    data = body["data"]
    if data.get("displayName") != display_name:
        return {
            "passed": False,
            "message": f"Display name not updated correctly. Expected: {display_name}, Got: {data.get('displayName')}"
        }
    
    # Verify in DynamoDB
    user_id = data.get("userId")
    if user_id:
        item = check_dynamodb_item(user_id, "PROFILE")
        if not item:
            return {
                "passed": False,
                "message": "Profile not found in DynamoDB"
            }
        
        if item.get("displayName") != display_name:
            return {
                "passed": False,
                "message": f"Display name in DynamoDB does not match. Expected: {display_name}, Got: {item.get('displayName')}"
            }
    
    return {
        "passed": True,
        "message": "User profile updated successfully",
        "data": data
    }


def test_update_profile_protected_fields(token: str) -> Dict:
    """
    Test Case 1.2.3: Update user profile with protected fields (should be sanitized)
    """
    # First, get the current profile to know the userId
    get_response = make_request("GET", "/users/profile", token)
    if get_response["status_code"] != 200:
        return {
            "passed": False,
            "message": f"Could not get current profile. Status code: {get_response['status_code']}"
        }
    
    current_user_id = get_response["body"]["data"].get("userId")
    fake_user_id = f"FAKE_{uuid.uuid4().hex}"
    
    update_data = {
        "displayName": "Protected Fields Test",
        "userId": fake_user_id,
        "createdAt": 12345,
        "email": "fake@example.com"
    }
    
    response = make_request("PUT", "/users/profile", token, update_data)
    
    if response["status_code"] != 200:
        return {
            "passed": False,
            "message": f"Expected status code 200, got {response['status_code']}"
        }
    
    data = response["body"]["data"]
    
    # Check that userId was not changed
    if data.get("userId") == fake_user_id:
        return {
            "passed": False,
            "message": "Protected field 'userId' was not sanitized"
        }
    
    # Check that userId is still the original value
    if data.get("userId") != current_user_id:
        return {
            "passed": False,
            "message": f"userId changed unexpectedly. Expected: {current_user_id}, Got: {data.get('userId')}"
        }
    
    return {
        "passed": True,
        "message": "Protected fields were properly sanitized",
        "data": data
    }


def test_get_settings(token: str) -> Dict:
    """
    Test Case 2.1.1: Get all user settings with valid authentication
    """
    response = make_request("GET", "/users/settings", token)
    
    if response["status_code"] != 200:
        return {
            "passed": False,
            "message": f"Expected status code 200, got {response['status_code']}"
        }
    
    body = response["body"]
    if "data" not in body:
        return {
            "passed": False,
            "message": "Response body does not contain 'data' field"
        }
    
    data = body["data"]
    required_fields = ["userId", "settings"]
    for field in required_fields:
        if field not in data:
            return {
                "passed": False,
                "message": f"Response data does not contain required field: {field}"
            }
    
    return {
        "passed": True,
        "message": "User settings retrieved successfully",
        "data": data
    }


def test_update_setting(token: str) -> Dict:
    """
    Test Case 2.2.1: Update user setting with valid data
    """
    namespace = "display"
    key = "colorMode"
    value = "dark" if time.time() % 2 == 0 else "light"  # Alternate between dark and light
    
    update_data = {
        "value": value
    }
    
    response = make_request("PUT", f"/users/settings/{namespace}/{key}", token, update_data)
    
    if response["status_code"] != 200:
        return {
            "passed": False,
            "message": f"Expected status code 200, got {response['status_code']}"
        }
    
    body = response["body"]
    if "data" not in body:
        return {
            "passed": False,
            "message": "Response body does not contain 'data' field"
        }
    
    data = body["data"]
    if data.get("namespace") != namespace:
        return {
            "passed": False,
            "message": f"Namespace not correct. Expected: {namespace}, Got: {data.get('namespace')}"
        }
    
    if data.get("key") != key:
        return {
            "passed": False,
            "message": f"Key not correct. Expected: {key}, Got: {data.get('key')}"
        }
    
    if data.get("value") != value:
        return {
            "passed": False,
            "message": f"Value not updated correctly. Expected: {value}, Got: {data.get('value')}"
        }
    
    # Verify in DynamoDB
    user_id = data.get("userId")
    if user_id:
        item = check_dynamodb_item(user_id, f"SETTING#{namespace}#{key}")
        if not item:
            return {
                "passed": False,
                "message": "Setting not found in DynamoDB"
            }
        
        if item.get("value") != value:
            return {
                "passed": False,
                "message": f"Value in DynamoDB does not match. Expected: {value}, Got: {item.get('value')}"
            }
    
    return {
        "passed": True,
        "message": "User setting updated successfully",
        "data": data
    }


def test_get_settings_with_namespace(token: str, namespace: str) -> Dict:
    """
    Test Case 2.1.2: Get user settings with namespace filter
    """
    response = make_request("GET", f"/users/settings?namespace={namespace}", token)
    
    if response["status_code"] != 200:
        return {
            "passed": False,
            "message": f"Expected status code 200, got {response['status_code']}"
        }
    
    body = response["body"]
    if "data" not in body:
        return {
            "passed": False,
            "message": "Response body does not contain 'data' field"
        }
    
    data = body["data"]
    settings = data.get("settings", {})
    
    # Check that only the requested namespace is returned
    for ns in settings.keys():
        if ns != namespace:
            return {
                "passed": False,
                "message": f"Response contains settings for namespace '{ns}', expected only '{namespace}'"
            }
    
    return {
        "passed": True,
        "message": f"User settings for namespace '{namespace}' retrieved successfully",
        "data": data
    }


def test_add_favorite(token: str) -> Dict:
    """
    Test Case 3.1.1: Add favorite with valid data
    """
    # Generate a unique item ID
    item_id = f"test-item-{uuid.uuid4().hex[:8]}"
    item_type = "ASSET"
    
    favorite_data = {
        "itemId": item_id,
        "itemType": item_type,
        "metadata": {
            "name": "Test Asset",
            "description": "This is a test asset"
        }
    }
    
    response = make_request("POST", "/users/favorites", token, favorite_data)
    
    if response["status_code"] != 201:
        return {
            "passed": False,
            "message": f"Expected status code 201, got {response['status_code']}"
        }
    
    body = response["body"]
    if "data" not in body:
        return {
            "passed": False,
            "message": "Response body does not contain 'data' field"
        }
    
    data = body["data"]
    if data.get("itemId") != item_id:
        return {
            "passed": False,
            "message": f"Item ID not correct. Expected: {item_id}, Got: {data.get('itemId')}"
        }
    
    if data.get("itemType") != item_type:
        return {
            "passed": False,
            "message": f"Item type not correct. Expected: {item_type}, Got: {data.get('itemType')}"
        }
    
    # Store the favorite ID for later use in delete test
    favorite_id = data.get("favoriteId")
    
    return {
        "passed": True,
        "message": "Favorite added successfully",
        "data": data,
        "favorite_id": favorite_id,
        "item_id": item_id,
        "item_type": item_type
    }


def test_get_favorites(token: str) -> Dict:
    """
    Test Case 3.2.1: Get all user favorites with valid authentication
    """
    response = make_request("GET", "/users/favorites", token)
    
    if response["status_code"] != 200:
        return {
            "passed": False,
            "message": f"Expected status code 200, got {response['status_code']}"
        }
    
    body = response["body"]
    if "data" not in body:
        return {
            "passed": False,
            "message": "Response body does not contain 'data' field"
        }
    
    data = body["data"]
    required_fields = ["userId", "favorites", "count"]
    for field in required_fields:
        if field not in data:
            return {
                "passed": False,
                "message": f"Response data does not contain required field: {field}"
            }
    
    return {
        "passed": True,
        "message": "User favorites retrieved successfully",
        "data": data
    }


def test_get_favorites_with_item_type(token: str, item_type: str) -> Dict:
    """
    Test Case 3.2.2: Get user favorites with itemType filter
    """
    response = make_request("GET", f"/users/favorites?itemType={item_type}", token)
    
    if response["status_code"] != 200:
        return {
            "passed": False,
            "message": f"Expected status code 200, got {response['status_code']}"
        }
    
    body = response["body"]
    if "data" not in body:
        return {
            "passed": False,
            "message": "Response body does not contain 'data' field"
        }
    
    data = body["data"]
    favorites = data.get("favorites", [])
    
    # Check that only the requested item type is returned
    for favorite in favorites:
        if favorite.get("itemType") != item_type:
            return {
                "passed": False,
                "message": f"Response contains favorite with itemType '{favorite.get('itemType')}', expected only '{item_type}'"
            }
    
    return {
        "passed": True,
        "message": f"User favorites for itemType '{item_type}' retrieved successfully",
        "data": data
    }


def test_delete_favorite(token: str, item_type: str, item_id: str) -> Dict:
    """
    Test Case 3.3.1: Delete favorite with valid itemType and itemId
    """
    response = make_request("DELETE", f"/users/favorites/{item_type}/{item_id}", token)
    
    if response["status_code"] != 200:
        return {
            "passed": False,
            "message": f"Expected status code 200, got {response['status_code']}"
        }
    
    body = response["body"]
    if "data" not in body:
        return {
            "passed": False,
            "message": "Response body does not contain 'data' field"
        }
    
    data = body["data"]
    if not data.get("removed"):
        return {
            "passed": False,
            "message": "Favorite was not removed"
        }
    
    return {
        "passed": True,
        "message": "Favorite removed successfully",
        "data": data
    }


def test_delete_nonexistent_favorite(token: str) -> Dict:
    """
    Test Case 3.3.2: Delete favorite with non-existent itemType and itemId
    """
    item_type = "ASSET"
    item_id = f"nonexistent-{uuid.uuid4().hex}"
    
    response = make_request("DELETE", f"/users/favorites/{item_type}/{item_id}", token)
    
    if response["status_code"] != 200:
        return {
            "passed": False,
            "message": f"Expected status code 200, got {response['status_code']}"
        }
    
    body = response["body"]
    if "data" not in body:
        return {
            "passed": False,
            "message": "Response body does not contain 'data' field"
        }
    
    data = body["data"]
    if data.get("removed"):
        return {
            "passed": False,
            "message": "Response indicates favorite was removed, but it should not exist"
        }
    
    return {
        "passed": True,
        "message": "Correctly reported that favorite does not exist",
        "data": data
    }


def test_invalid_item_type(token: str) -> Dict:
    """
    Test Case 3.1.3: Add favorite with invalid itemType
    """
    item_id = f"test-item-{uuid.uuid4().hex[:8]}"
    item_type = "INVALID_TYPE"
    
    favorite_data = {
        "itemId": item_id,
        "itemType": item_type
    }
    
    response = make_request("POST", "/users/favorites", token, favorite_data)
    
    if response["status_code"] != 400:
        return {
            "passed": False,
            "message": f"Expected status code 400, got {response['status_code']}"
        }
    
    return {
        "passed": True,
        "message": "Correctly rejected invalid itemType",
        "data": response["body"]
    }


def main():
    """
    Main function to run all tests.
    """
    print("Starting UPSF API tests...")
    
    try:
        # Authenticate with Cognito
        print("Authenticating with Cognito...")
        token = authenticate()
        print("Authentication successful.")
        
        # Run profile tests
        profile_result = run_test("Get User Profile", test_get_profile, token)
        run_test("Update User Profile", test_update_profile, token)
        run_test("Update User Profile with Protected Fields", test_update_profile_protected_fields, token)
        
        # Run settings tests
        run_test("Get User Settings", test_get_settings, token)
        settings_result = run_test("Update User Setting", test_update_setting, token)
        
        # If we successfully updated a setting, test getting settings with namespace filter
        if settings_result.get("passed"):
            namespace = settings_result["data"]["namespace"]
            run_test(f"Get User Settings with Namespace Filter ({namespace})", 
                    test_get_settings_with_namespace, token, namespace)
        
        # Run favorites tests
        favorite_result = run_test("Add Favorite", test_add_favorite, token)
        run_test("Get User Favorites", test_get_favorites, token)
        
        # If we successfully added a favorite, test getting favorites with itemType filter
        if favorite_result.get("passed"):
            item_type = favorite_result["data"]["itemType"]
            run_test(f"Get User Favorites with ItemType Filter ({item_type})", 
                    test_get_favorites_with_item_type, token, item_type)
            
            # And test deleting the favorite
            item_id = favorite_result["data"]["itemId"]
            run_test("Delete Favorite", test_delete_favorite, token, item_type, item_id)
        
        # Test deleting a non-existent favorite
        run_test("Delete Non-existent Favorite", test_delete_nonexistent_favorite, token)
        
        # Test invalid item type
        run_test("Add Favorite with Invalid ItemType", test_invalid_item_type, token)
        
    except Exception as e:
        print(f"Error running tests: {str(e)}")
    
    # Print summary
    print("\n=== Test Summary ===")
    print(f"Total tests: {test_results['total']}")
    print(f"Passed: {test_results['passed']}")
    print(f"Failed: {test_results['failed']}")
    print(f"Success rate: {(test_results['passed'] / test_results['total'] * 100):.2f}%")
    
    # Print details of failed tests
    if test_results["failed"] > 0:
        print("\n=== Failed Tests ===")
        for detail in test_results["details"]:
            if not detail["passed"]:
                print(f"❌ {detail['name']}: {detail['message']}")


if __name__ == "__main__":
    main()