"""
Webhook API Gateway Lambda Authorizer.

Validates incoming webhook requests by looking up the pipeline record in DynamoDB,
retrieving the webhook secret from Secrets Manager, and comparing credentials
using constant-time comparison.

Accepts tokens from any common header format so callers don't need to know
the exact auth method configured on the pipeline:
  - X-Api-Key: <token>
  - Authorization: Bearer <token>
  - Authorization: Basic <base64(user:pass)>
"""

import base64
import hmac
import json
import os
from datetime import datetime, timezone

import boto3

PIPELINE_TABLE_NAME = os.environ.get("PIPELINE_TABLE_NAME", "")

dynamodb = boto3.resource("dynamodb")
secretsmanager = boto3.client("secretsmanager")


def _build_policy(principal_id, effect, method_arn, context=None):
    policy = {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": method_arn,
                }
            ],
        },
    }
    if context:
        policy["context"] = context
    return policy


def _allow(method_arn, context=None):
    return _build_policy("webhook-caller", "Allow", method_arn, context)


def _deny(method_arn):
    return _build_policy("webhook-caller", "Deny", method_arn)


def _get_header(headers, name):
    """Truly case-insensitive header lookup."""
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def _extract_token(headers):
    """Extract a bearer/api-key token from any common header.

    Checks in order:
      1. X-Api-Key header
      2. Authorization: Bearer <token>
      3. Authorization: <token>  (raw token, no scheme)
    """
    api_key = _get_header(headers, "X-Api-Key")
    if api_key:
        return api_key

    auth = _get_header(headers, "Authorization")
    if auth:
        if auth.lower().startswith("bearer "):
            return auth[7:]
        # Raw token (no scheme prefix and not Basic auth)
        if not auth.lower().startswith("basic "):
            return auth

    return None


def _extract_basic_auth(headers):
    """Extract username and password from Authorization Basic header."""
    auth = _get_header(headers, "Authorization")
    if not auth or not auth.lower().startswith("basic "):
        return None, None

    try:
        decoded = base64.b64decode(auth[6:]).decode("utf-8")
        username, password = decoded.split(":", maxsplit=1)
        return username, password
    except Exception:
        return None, None


def _in_grace_window(grace_until):
    """Check if current time is within the grace window."""
    if not grace_until:
        return False
    try:
        parsed = datetime.fromisoformat(grace_until.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < parsed
    except Exception:
        return False


def _check_credential(candidate, stored, previous, grace_until):
    """Compare a candidate credential against current (and optionally previous)."""
    if not candidate or not stored:
        return False
    if hmac.compare_digest(candidate, stored):
        return True
    if _in_grace_window(grace_until) and previous:
        if hmac.compare_digest(candidate, previous):
            return True
    return False


def lambda_handler(event, context):
    method_arn = event.get("methodArn", "*")

    try:
        path_params = event.get("pathParameters") or {}
        pipeline_id = path_params.get("pipelineId")
        if not pipeline_id:
            return _deny(method_arn)

        table = dynamodb.Table(PIPELINE_TABLE_NAME)
        response = table.get_item(Key={"id": pipeline_id})
        item = response.get("Item")

        if not item:
            return _deny(method_arn)

        if not item.get("active"):
            return _deny(method_arn)
        if item.get("deploymentStatus") != "DEPLOYED":
            return _deny(method_arn)

        auth_method = item.get("webhookAuthMethod")
        secret_arn = item.get("webhookSecretArn")
        if not auth_method or not secret_arn:
            return _deny(method_arn)

        # HMAC verification requires the request body, which REQUEST
        # authorizers don't receive.  We confirm the pipeline is valid
        # and pass the secret ARN to the ingress Lambda via context so
        # it can perform the actual signature check.
        if auth_method == "hmac_sha256":
            return _allow(
                method_arn,
                {"authMethod": "hmac_sha256", "webhookSecretArn": secret_arn},
            )

        secret_response = secretsmanager.get_secret_value(SecretId=secret_arn)
        secret_data = json.loads(secret_response["SecretString"])

        current = secret_data.get("current", {})
        previous = secret_data.get("previous", {})
        grace_until = secret_data.get("graceUntil")

        headers = event.get("headers") or {}

        if auth_method == "api_key":
            token = _extract_token(headers)
            if _check_credential(
                token,
                current.get("apiKey", ""),
                previous.get("apiKey", ""),
                grace_until,
            ):
                return _allow(method_arn, {"authMethod": "api_key"})
            return _deny(method_arn)

        elif auth_method == "basic_auth":
            # Try Basic auth header first
            username, password = _extract_basic_auth(headers)
            if username is not None and password is not None:
                current_user = current.get("basicAuthUsername", "")
                current_pass = current.get("basicAuthPassword", "")
                if hmac.compare_digest(username, current_user) and hmac.compare_digest(
                    password, current_pass
                ):
                    return _allow(method_arn, {"authMethod": "basic_auth"})

                if _in_grace_window(grace_until):
                    prev_user = previous.get("basicAuthUsername", "")
                    prev_pass = previous.get("basicAuthPassword", "")
                    if hmac.compare_digest(username, prev_user) and hmac.compare_digest(
                        password, prev_pass
                    ):
                        return _allow(method_arn, {"authMethod": "basic_auth"})

            # Fallback: also accept the password as a plain token via
            # X-Api-Key / Bearer so callers can use a single header style
            token = _extract_token(headers)
            if token:
                current_pass = current.get("basicAuthPassword", "")
                prev_pass = previous.get("basicAuthPassword", "")
                if _check_credential(token, current_pass, prev_pass, grace_until):
                    return _allow(method_arn, {"authMethod": "basic_auth"})

            return _deny(method_arn)

        else:
            return _deny(method_arn)

    except Exception:
        return _deny(method_arn)
