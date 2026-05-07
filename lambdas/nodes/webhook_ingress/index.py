import hashlib
import hmac as hmac_mod
import json
import os
import time
import uuid
from datetime import datetime

import boto3

dynamodb = boto3.resource("dynamodb")
events = boto3.client("events")
secretsmanager = boto3.client("secretsmanager")

PIPELINES_EVENT_BUS_NAME = os.environ["PIPELINES_EVENT_BUS_NAME"]
PIPELINE_TABLE_NAME = os.environ["PIPELINE_TABLE_NAME"]

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}
PAYLOAD_BYTE_CAP = 261_120


def _get_header(headers, name):
    name_lower = name.lower()
    for key, value in headers.items():
        if key.lower() == name_lower:
            return value
    return None


def _verify_hmac_signature(raw_body, secret_arn, headers):
    """Verify HMAC SHA-256 signature for webhook requests.

    Fetches the signing secret from Secrets Manager, computes the expected
    signature over the raw request body, and compares it against the value
    in the configured signature header.  Supports current/previous secret
    rotation with a grace window.

    Returns (True, None) on success or (False, error_message) on failure.
    """
    try:
        secret_response = secretsmanager.get_secret_value(SecretId=secret_arn)
        secret_data = json.loads(secret_response["SecretString"])
    except Exception:
        return False, "Failed to retrieve signing secret"

    current = secret_data.get("current", {})
    previous = secret_data.get("previous", {})
    grace_until = secret_data.get("graceUntil")

    sig_header_name = current.get("signatureHeader", "X-Hub-Signature-256")
    signature_value = _get_header(headers, sig_header_name)
    if not signature_value:
        return False, "Missing signature header"

    # Strip optional "sha256=" prefix (GitHub-style)
    if signature_value.lower().startswith("sha256="):
        signature_value = signature_value[7:]

    body_bytes = raw_body.encode("utf-8") if isinstance(raw_body, str) else raw_body

    # Check against current secret
    current_secret = current.get("hmacSecret", "")
    if current_secret:
        expected = hmac_mod.new(
            current_secret.encode("utf-8"), body_bytes, hashlib.sha256
        ).hexdigest()
        if hmac_mod.compare_digest(expected, signature_value):
            return True, None

    # Check against previous secret within grace window
    if previous and grace_until:
        try:
            from datetime import timezone

            parsed = datetime.fromisoformat(grace_until.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < parsed:
                prev_secret = previous.get("hmacSecret", "")
                if prev_secret:
                    expected = hmac_mod.new(
                        prev_secret.encode("utf-8"), body_bytes, hashlib.sha256
                    ).hexdigest()
                    if hmac_mod.compare_digest(expected, signature_value):
                        return True, None
        except Exception:
            pass

    return False, "Invalid signature"


def lambda_handler(event, context):
    # 1. Extract pipelineId
    try:
        pipeline_id = event["pathParameters"]["pipelineId"]
    except (KeyError, TypeError):
        return {
            "statusCode": 400,
            "headers": CORS_HEADERS,
            "body": json.dumps(
                {"error": "Bad Request", "message": "Missing pipelineId"}
            ),
        }

    # 2. Content-Type check
    headers = event.get("headers") or {}
    content_type = _get_header(headers, "Content-Type")
    if not content_type or "application/json" not in content_type.lower():
        return {
            "statusCode": 415,
            "headers": CORS_HEADERS,
            "body": json.dumps(
                {
                    "error": "Unsupported Media Type",
                    "message": "Content-Type must be application/json",
                }
            ),
        }

    # 3. JSON parse
    try:
        raw_body = event.get("body") or ""
        if not raw_body:
            raise ValueError("empty body")
        parsed_body = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError):
        return {
            "statusCode": 400,
            "headers": CORS_HEADERS,
            "body": json.dumps(
                {"error": "Bad Request", "message": "Request body must be valid JSON"}
            ),
        }

    # 4. HMAC signature verification (if applicable)
    authorizer_context = (event.get("requestContext") or {}).get("authorizer") or {}
    auth_method = authorizer_context.get("authMethod")

    if auth_method == "hmac_sha256":
        secret_arn = authorizer_context.get("webhookSecretArn")
        if not secret_arn:
            return {
                "statusCode": 401,
                "headers": CORS_HEADERS,
                "body": json.dumps(
                    {
                        "error": "Unauthorized",
                        "message": "Missing signing configuration",
                    }
                ),
            }
        valid, err_msg = _verify_hmac_signature(raw_body, secret_arn, headers)
        if not valid:
            return {
                "statusCode": 401,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Unauthorized", "message": err_msg}),
            }

    # 5. Payload size cap
    if isinstance(raw_body, bytes):
        body_for_size = raw_body
    elif isinstance(raw_body, str):
        body_for_size = raw_body.encode("utf-8")
    else:
        body_for_size = str(raw_body).encode("utf-8")
    if len(body_for_size) > PAYLOAD_BYTE_CAP:
        return {
            "statusCode": 413,
            "headers": CORS_HEADERS,
            "body": json.dumps(
                {
                    "error": "Payload Too Large",
                    "message": "Request body exceeds maximum allowed size",
                }
            ),
        }

    # 6. Generate correlation ID
    webhook_request_id = str(uuid.uuid4())

    # 7. Idempotency-Key handling
    idempotency_key = _get_header(headers, "Idempotency-Key")
    table = None
    idempotency_pk = None

    if idempotency_key:
        idempotency_pk = f"WEBHOOK#{pipeline_id}#{idempotency_key}"
        table = dynamodb.Table(PIPELINE_TABLE_NAME)
        # Check for existing non-expired record with a completed eventId
        existing = table.get_item(Key={"id": idempotency_pk}).get("Item")
        if existing:
            now = int(time.time())
            if existing.get("expiresAt", 0) > now and existing.get("eventId"):
                return {
                    "statusCode": 200,
                    "headers": CORS_HEADERS,
                    "body": json.dumps(
                        {
                            "message": "Webhook accepted for async processing",
                            "webhookRequestId": existing["webhookRequestId"],
                            "eventId": existing["eventId"],
                        }
                    ),
                }
            # Expired or incomplete record — allow retry by deleting stale entry
            table.delete_item(Key={"id": idempotency_pk})

    # 8. EventBridge publish
    try:
        detail = {
            "pipelineId": pipeline_id,
            "webhookRequestId": webhook_request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": parsed_body,
        }
        response = events.put_events(
            Entries=[
                {
                    "Source": "medialake.webhook",
                    "DetailType": "WebhookTriggered",
                    "Detail": json.dumps(detail),
                    "EventBusName": PIPELINES_EVENT_BUS_NAME,
                }
            ]
        )
        entry = response["Entries"][0]
        if "ErrorCode" in entry:
            raise RuntimeError(entry.get("ErrorMessage", "EventBridge error"))
        event_id = entry["EventId"]
    except Exception:
        return {
            "statusCode": 502,
            "headers": CORS_HEADERS,
            "body": json.dumps(
                {"error": "Bad Gateway", "message": "Failed to process webhook"}
            ),
        }

    # 9. Write idempotency record only after successful publish
    if idempotency_pk and table:
        try:
            table.put_item(
                Item={
                    "id": idempotency_pk,
                    "webhookRequestId": webhook_request_id,
                    "eventId": event_id,
                    "expiresAt": int(time.time()) + 300,
                },
            )
        except Exception:
            pass  # Log but do not fail the request

    # 10. Return success
    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(
            {
                "message": "Webhook accepted for async processing",
                "webhookRequestId": webhook_request_id,
                "eventId": event_id,
            }
        ),
    }
