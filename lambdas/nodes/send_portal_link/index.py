"""Send an upload portal link via email using SES."""

import os

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambda_middleware import lambda_middleware

logger = Logger()
tracer = Tracer()

ses_client = boto3.client("ses")
SES_FROM_ARN = os.environ.get("SES_FROM_ARN", "")
SES_FROM_EMAIL = os.environ.get("SES_FROM_EMAIL", "")


def _mask_email(email: str) -> str:
    """Return a masked email suitable for logs.

    ``"alice@example.com"`` → ``"a***@example.com"``. Falls back to
    ``"<redacted>"`` when the input doesn't look like an email.
    """
    if not email or "@" not in email:
        return "<redacted>"
    local, _, domain = email.partition("@")
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def _resolve_param(name, data, payload_history, env_key):
    """Resolve a parameter from data, then payload_history, then env var."""
    val = data.get(name)
    if val:
        return val
    val = payload_history.get(name)
    if val:
        return val
    return os.environ.get(env_key, "")


@lambda_middleware(event_bus_name=os.getenv("EVENT_BUS_NAME", "default-event-bus"))
@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    logger.info("Incoming event", extra={"event": event})

    payload = event.get("payload", {})
    data = payload.get("data", {})
    payload_history = payload.get("payload_history", {})

    # Resolve parameters: data → payload_history → env vars
    recipient_email = _resolve_param(
        "recipientEmail", data, payload_history, "RECIPIENT_EMAIL"
    )
    portal_url = _resolve_param("portalUrl", data, payload_history, "PORTAL_URL")
    portal_name = _resolve_param("portalName", data, payload_history, "PORTAL_NAME")
    dataset_name = _resolve_param("datasetName", data, payload_history, "DATASET_NAME")
    expires_at = _resolve_param("expiresAt", data, payload_history, "EXPIRES_AT")

    # Short-circuit before we ask SES to send to an empty address or an
    # empty URL — either would produce a user-facing broken email.
    if not recipient_email:
        raise ValueError(
            "recipientEmail is required (pass via data, payload_history, "
            "or RECIPIENT_EMAIL env var)."
        )
    if not portal_url:
        raise ValueError(
            "portalUrl is required (pass via data, payload_history, "
            "or PORTAL_URL env var)."
        )

    if not SES_FROM_ARN or not SES_FROM_EMAIL:
        raise ValueError(
            "SES_FROM_ARN and SES_FROM_EMAIL must be configured. "
            "Set ses_from_address in config.json."
        )

    # Build email — mirrors _send_token_email from portals_ID_tokens_post.py
    subject = f"You've been invited to upload to {portal_name}"

    dataset_line = (
        f"<p><strong>Dataset:</strong> {dataset_name}</p>" if dataset_name else ""
    )
    expires_line = (
        f"<p><strong>Expires:</strong> {expires_at}</p>" if expires_at else ""
    )

    html_body = (
        f"<h2>Upload Portal Invitation</h2>"
        f"<p>You have been invited to upload files to <strong>{portal_name}</strong>.</p>"
        f"{dataset_line}"
        f"{expires_line}"
        f'<p><a href="{portal_url}">Click here to upload</a></p>'
    )

    text_body = (
        f"Upload Portal Invitation\n\n"
        f"You have been invited to upload files to {portal_name}.\n"
        f"{'Dataset: ' + dataset_name + chr(10) if dataset_name else ''}"
        f"{'Expires: ' + expires_at + chr(10) if expires_at else ''}"
        f"Upload URL: {portal_url}\n"
    )

    ses_client.send_email(
        Source=SES_FROM_EMAIL,
        SourceArn=SES_FROM_ARN,
        Destination={"ToAddresses": [recipient_email]},
        Message={
            "Subject": {"Data": subject},
            "Body": {
                "Html": {"Data": html_body},
                "Text": {"Data": text_body},
            },
        },
    )

    logger.info(f"Portal link email sent to {_mask_email(recipient_email)}")

    return {
        "statusCode": 200,
        "recipientEmail": recipient_email,
        "portalUrl": portal_url,
        "emailSent": True,
    }
