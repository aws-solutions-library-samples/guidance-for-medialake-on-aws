import base64
import json
import os
from typing import Any, Dict

import boto3
import requests


def get_secret_value(secret_arn: str) -> Dict[str, Any]:
    """
    Retrieve secret value from AWS Secrets Manager
    """
    try:
        print(f"Attempting to retrieve secret from ARN")
        secrets_client = boto3.client("secretsmanager")
        response = secrets_client.get_secret_value(SecretId=secret_arn)
        print(f"Successfully retrieved secret from Secrets Manager")

        secret_string = response.get("SecretString", "")

        if not secret_string.strip():
            raise ValueError("Secret string is empty")

        # Try to parse as JSON first
        try:
            return json.loads(secret_string)
        except json.JSONDecodeError:
            # If JSON parsing fails, treat as plain text personal token
            print("Secret is not JSON format, treating as plain text personal token")
            return {"personal_token": secret_string.strip()}
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse secret JSON: {str(e)}."
        print(f"ERROR: {error_msg}")
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Failed to retrieve secret: {str(e)}"
        print(f"ERROR: {error_msg}")
        raise RuntimeError(error_msg)


def get_coactive_access_token() -> str:
    """
    Authenticate with Coactive API and get access token
    Uses AWS Secrets Manager to retrieve credentials from API_KEY_SECRET_ARN
    """
    # Get the secret ARN from environment variable
    secret_arn = os.environ.get("API_KEY_SECRET_ARN")
    if not secret_arn:
        error_msg = "API_KEY_SECRET_ARN environment variable not set"
        print(f"ERROR: {error_msg}")
        raise RuntimeError(error_msg)

    # Retrieve credentials from Secrets Manager
    try:
        secret_data = get_secret_value(secret_arn)
    except Exception as e:
        error_msg = f"Failed to retrieve Coactive credentials: {str(e)}"
        print(f"ERROR: {error_msg}")
        raise RuntimeError(error_msg)

    login_url = "https://api.coactive.ai/api/v0/login"

    # Check if we have a personal token or client credentials
    if "personal_token" in secret_data:
        # Use personal token authentication
        personal_token = secret_data["personal_token"]
        headers = {
            "Authorization": f"Bearer {personal_token}",
            "Content-Type": "application/json",
        }
        data = {"grant_type": "refresh_token"}
    elif "client_id" in secret_data and "client_secret" in secret_data:
        # Use system credentials (basic auth)
        client_id = secret_data["client_id"]
        client_secret = secret_data["client_secret"]

        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        }
        data = {"grant_type": "client_credentials"}
    else:
        error_msg = "Secret must contain either 'personal_token' or both 'client_id' and 'client_secret'"
        print(f"ERROR: {error_msg}")
        raise RuntimeError(error_msg)

    try:
        print(f"Making authentication request to: {login_url}")
        response = requests.post(login_url, headers=headers, json=data)
        print(f"Authentication response status: {response.status_code}")

        response.raise_for_status()

        login_response = response.json()
        access_token = login_response.get("access_token")

        if not access_token:
            error_msg = "No access token received from Coactive login"
            print(f"ERROR: {error_msg}")
            print(f"Login response: {login_response}")
            raise RuntimeError(error_msg)

        print("Successfully obtained Coactive access token")
        return access_token
    except requests.RequestException as e:
        error_msg = f"Failed to authenticate with Coactive API: {str(e)}"
        print(f"ERROR: {error_msg}")
        raise RuntimeError(error_msg)


def process_api_request(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pre-process API request with Coactive authentication
    This function is called by the API handler before making the API call
    """
    try:
        print("Processing Coactive API request - adding authentication")

        # Get access token for authenticated requests
        access_token = get_coactive_access_token()

        # Add authentication headers to the event
        if "headers" not in event:
            event["headers"] = {}

        event["headers"]["Authorization"] = f"Bearer {access_token}"

        # Log successful authentication
        print(
            f"Successfully added Coactive authentication for operation: {event.get('operation', 'unknown')}"
        )

        return event

    except Exception as e:
        error_msg = f"Error in Coactive pre-request authentication: {str(e)}"
        print(f"ERROR: {error_msg}")
        raise RuntimeError(error_msg)


def process_api_response(
    api_response: Dict[str, Any], event: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process API response with Coactive authentication
    This function is called by the API handler after making the API call
    """
    try:
        print("Processing Coactive API response")

        # Use the response and event parameters directly
        response_body = api_response

        # Log successful response processing
        print(
            f"Successfully processed Coactive API response for operation: {event.get('operation', 'unknown')}"
        )

        return response_body

    except Exception as e:
        error_msg = f"Error in Coactive response processing: {str(e)}"
        print(f"ERROR: {error_msg}")
        raise RuntimeError(error_msg)
