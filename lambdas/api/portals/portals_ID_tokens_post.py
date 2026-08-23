"""POST /settings/portals/{id}/tokens — Create a token and optionally email it."""

import hashlib
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode, urlparse

import boto3
from aws_lambda_powertools import Logger, Tracer
from custom_exceptions import ForbiddenError
from db_models import PortalMetadataModel, PortalTokenModel
from permission_utils import check_admin_permission, extract_user_context
from portal_utils import METADATA_SK, get_portal_pk, get_token_sk
from response_utils import create_error_response, create_success_response, now_iso

logger = Logger(
    service="portals-id-tokens-post", level=os.environ.get("LOG_LEVEL", "INFO")
)
tracer = Tracer(service="portals-id-tokens-post")

CLOUDFRONT_DOMAIN = os.environ.get("CLOUDFRONT_DOMAIN", "")
SES_FROM_ARN = os.environ.get("SES_FROM_ARN", "")
SES_FROM_EMAIL = os.environ.get("SES_FROM_EMAIL", "")

# Optional comma-separated extra domains allowed to appear in shareable
# URLs. CLOUDFRONT_DOMAIN is always included implicitly.
ALLOWED_SHAREABLE_DOMAINS = [
    d.strip().lower()
    for d in os.environ.get("ALLOWED_SHAREABLE_DOMAINS", "").split(",")
    if d.strip()
]

ses_client = boto3.client("ses")

# BUG-11 — CLOUDFRONT_DOMAIN is set at CDK deploy time from props.cloudfront_domain,
# but on first-time and stack-order-sensitive deploys this can synthesize to an
# empty string (the UI stack that resolves the domain runs after this stack).
# When the env var is empty we look up the SSM parameter at request time, cache
# it on the module for the life of the Lambda container, and fall back to that.
# Without this fallback `shareableUrl` is returned empty, which forces recipients
# into the broken passphrase gate (BUG-10) — see QA pass-2 report.
_SSM_RESOLVED_CLOUDFRONT_DOMAIN: Optional[str] = None
_ssm_client = None


def _get_ssm_client():
    global _ssm_client
    if _ssm_client is None:
        _ssm_client = boto3.client("ssm")
    return _ssm_client


def _cloudfront_domain_from_ssm() -> str:
    """Resolve the CloudFront domain from SSM Parameter Store.

    Uses the same convention as ``lambdas/common_libraries/url_utils.py``:
    ``CLOUDFRONT_DOMAIN_SSM_PARAM`` env var if set, otherwise
    ``{SSM_PREFIX}/cloudfront-distribution-domain`` (with a sensible default
    prefix). Cached on the module after the first successful call.
    """
    global _SSM_RESOLVED_CLOUDFRONT_DOMAIN
    if _SSM_RESOLVED_CLOUDFRONT_DOMAIN is not None:
        return _SSM_RESOLVED_CLOUDFRONT_DOMAIN
    ssm_parameter_name = os.environ.get("CLOUDFRONT_DOMAIN_SSM_PARAM")
    if not ssm_parameter_name:
        environment = os.environ.get("ENVIRONMENT", "dev")
        ssm_prefix = os.environ.get("SSM_PREFIX", f"/medialake/{environment}")
        ssm_parameter_name = f"{ssm_prefix}/cloudfront-distribution-domain"
    try:
        response = _get_ssm_client().get_parameter(
            Name=ssm_parameter_name, WithDecryption=True
        )
        raw = response["Parameter"]["Value"].strip()
        domain = re.sub(r"^https?://", "", raw).rstrip("/")
        _SSM_RESOLVED_CLOUDFRONT_DOMAIN = domain
        return domain
    except Exception as exc:  # noqa: BLE001 — logged and treated as unresolved
        logger.warning(
            "Failed to resolve CloudFront domain from SSM",
            extra={
                "ssm_parameter_name": ssm_parameter_name,
                "error": str(exc),
            },
        )
        return ""


def _mask_email(email: str) -> str:
    """Return a masked email suitable for logs.

    Keeps the first character of the local part and the domain so support
    staff can still correlate logs with user reports without exposing the
    full address. ``"alice@example.com"`` → ``"a***@example.com"``.
    """
    if not email or "@" not in email:
        return "<redacted>"
    local, _, domain = email.partition("@")
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def _resolved_cloudfront_domain() -> str:
    """Return the deployed CloudFront domain, resolving via SSM if needed."""
    if CLOUDFRONT_DOMAIN:
        return CLOUDFRONT_DOMAIN
    return _cloudfront_domain_from_ssm()


def _allowed_shareable_domains() -> set:
    """Return the lowercase set of domains we'll trust for shareable URLs."""
    allowed = set(ALLOWED_SHAREABLE_DOMAINS)
    resolved = _resolved_cloudfront_domain()
    if resolved:
        allowed.add(resolved.strip().lower())
    return allowed


def _get_shareable_domain(app) -> str:
    """Return the domain for shareable URLs.

    Client-supplied headers (Origin/Referer/X-Forwarded-Host/Host) are
    only honored when they match a configured allowlist; otherwise they're
    ignored to prevent a request-header-controlled phishing vector. When
    nothing matches we fall back to CLOUDFRONT_DOMAIN (if set) and log a
    warning.
    """
    allowed = _allowed_shareable_domains()

    def _check(candidate: str) -> str:
        """Return ``candidate`` if it's in the allowlist, else empty string."""
        if not candidate:
            return ""
        netloc = candidate.strip().lower()
        # Drop any port for the allowlist comparison; permit it in output.
        bare = netloc.split(":", 1)[0]
        if netloc in allowed or bare in allowed:
            return candidate
        logger.warning(
            "Ignoring shareable-domain candidate not in allowlist",
            extra={"candidate_domain": bare},
        )
        return ""

    headers = app.current_event.headers or {}

    for hdr in ("Origin", "origin"):
        raw = headers.get(hdr) or ""
        if raw:
            netloc = urlparse(raw).netloc
            accepted = _check(netloc)
            if accepted:
                return accepted

    for hdr in ("Referer", "referer"):
        raw = headers.get(hdr) or ""
        if raw:
            netloc = urlparse(raw).netloc
            accepted = _check(netloc)
            if accepted:
                return accepted

    forwarded = headers.get("X-Forwarded-Host") or headers.get("x-forwarded-host") or ""
    accepted = _check(forwarded)
    if accepted:
        return accepted

    host = headers.get("Host") or headers.get("host") or ""
    accepted = _check(host)
    if accepted:
        return accepted

    if CLOUDFRONT_DOMAIN:
        return CLOUDFRONT_DOMAIN

    # BUG-11 fallback: env var was empty, but the deployment does have a
    # CloudFront domain — read it from SSM. This handles the CDK deploy-order
    # case where props.cloudfront_domain synthesized to "".
    resolved = _cloudfront_domain_from_ssm()
    if resolved:
        return resolved

    logger.warning(
        "No allowlisted Origin, Referer, X-Forwarded-Host, or Host headers "
        "present, CLOUDFRONT_DOMAIN env var is unset, and the SSM parameter "
        "did not resolve; shareable URLs will be empty. Set cloudfront_domain "
        "in config, populate /{prefix}/{env}/cloudfront-distribution-domain in "
        "SSM, or configure ALLOWED_SHAREABLE_DOMAINS."
    )
    return ""


def _portal_path_for(portal) -> str:
    """Return the URL path prefix for a portal based on its access mode.

    ``"/p/"`` for public portals, ``"/upload/"`` for everything else
    (including the legacy case where ``accessMode`` is missing). Keeping
    this in a named function makes the behavior easy to reuse in tests
    instead of duplicating the ternary.
    """
    return "/p/" if getattr(portal, "accessMode", None) == "public" else "/upload/"


def build_shareable_url(
    portal, raw_token: str, domain: str, pre_populated_params=None
) -> str:
    """Assemble the full shareable URL for a portal token.

    Returns an empty string when ``domain`` is empty so callers can
    short-circuit the email path gracefully.
    """
    if not domain:
        return ""
    url = f"https://{domain}{_portal_path_for(portal)}{portal.slug}?token={raw_token}"
    if isinstance(pre_populated_params, dict) and pre_populated_params:
        url += "&" + urlencode(pre_populated_params)
    return url


def register_route(app):
    @app.post("/settings/portals/<portal_id>/tokens")
    @tracer.capture_method
    def portals_id_tokens_post(portal_id: str):
        request_id = app.current_event.request_context.request_id
        try:
            user_context = extract_user_context(app.current_event.raw_event)
            check_admin_permission(user_context)

            pk = get_portal_pk(portal_id)

            # Verify portal exists and get slug/name
            try:
                portal = PortalMetadataModel.get(pk, METADATA_SK)
            except PortalMetadataModel.DoesNotExist:
                return create_error_response(
                    code="NOT_FOUND",
                    message=f"Portal {portal_id} not found",
                    status_code=404,
                    request_id=request_id,
                )

            body = app.current_event.json_body or {}
            associated_email = body.get("associatedEmail", "")
            if not associated_email:
                return create_error_response(
                    code="VALIDATION_ERROR",
                    message="associatedEmail is required",
                    status_code=400,
                    request_id=request_id,
                )

            now = now_iso()
            token_id = str(uuid.uuid4())
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

            # Determine expiry
            expires_at = body.get("expiresAt")
            if not expires_at:
                expires_at = (
                    (datetime.now(timezone.utc) + timedelta(days=7))
                    .isoformat()
                    .replace("+00:00", "Z")
                )

            pre_populated_params = body.get("prePopulatedParams")

            # Write token record
            token = PortalTokenModel()
            token.PK = pk
            token.SK = get_token_sk(token_id)
            token.tokenId = token_id
            token.tokenHash = token_hash
            token.associatedEmail = associated_email
            token.createdAt = now
            token.expiresAt = expires_at
            token.isRevoked = False
            if pre_populated_params:
                token.prePopulatedParams = pre_populated_params
            token.save()

            domain = _get_shareable_domain(app)
            shareable_url = build_shareable_url(
                portal, raw_token, domain, pre_populated_params
            )

            # Send email if a valid sender address is configured
            if SES_FROM_ARN and SES_FROM_EMAIL:
                _send_token_email(
                    portal_name=portal.name,
                    description=getattr(portal, "description", None),
                    associated_email=associated_email,
                    shareable_url=shareable_url,
                    expires_at=expires_at,
                    pre_populated_params=pre_populated_params,
                )

            response_data = {
                "tokenId": token_id,
                "associatedEmail": associated_email,
                "createdAt": now,
                "expiresAt": expires_at,
                "isRevoked": False,
                "rawToken": raw_token,
                "shareableUrl": shareable_url,
            }

            return create_success_response(
                data=response_data, status_code=201, request_id=request_id
            )

        except ForbiddenError:
            raise
        except Exception as e:
            logger.exception("Error creating token", exc_info=e)
            return create_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                status_code=500,
                request_id=request_id,
            )


def _send_token_email(
    portal_name,
    description,
    associated_email,
    shareable_url,
    expires_at,
    pre_populated_params,
):
    """Send token invitation email via SES. Failures are logged but do not raise."""
    try:
        dataset_name = ""
        if pre_populated_params and isinstance(pre_populated_params, dict):
            dataset_name = pre_populated_params.get("datasetName", "")

        subject = f"You've been invited to upload to {portal_name}"

        desc_line = f"<p>{description}</p>" if description else ""
        dataset_line = (
            f"<p><strong>Dataset:</strong> {dataset_name}</p>" if dataset_name else ""
        )

        html_body = (
            f"<h2>Upload Portal Invitation</h2>"
            f"<p>You have been invited to upload files to <strong>{portal_name}</strong>.</p>"
            f"{desc_line}"
            f"{dataset_line}"
            f"<p><strong>Expires:</strong> {expires_at}</p>"
            f'<p><a href="{shareable_url}">Click here to upload</a></p>'
        )

        text_body = (
            f"Upload Portal Invitation\n\n"
            f"You have been invited to upload files to {portal_name}.\n"
            f"{'Description: ' + description + chr(10) if description else ''}"
            f"{'Dataset: ' + dataset_name + chr(10) if dataset_name else ''}"
            f"Expires: {expires_at}\n"
            f"Upload URL: {shareable_url}\n"
        )

        send_kwargs = {
            "Source": SES_FROM_EMAIL,
            "Destination": {"ToAddresses": [associated_email]},
            "Message": {
                "Subject": {"Data": subject},
                "Body": {
                    "Html": {"Data": html_body},
                    "Text": {"Data": text_body},
                },
            },
        }
        if SES_FROM_ARN:
            send_kwargs["SourceArn"] = SES_FROM_ARN

        ses_client.send_email(**send_kwargs)
        logger.info(f"Token email sent to {_mask_email(associated_email)}")
    except Exception:
        logger.warning(
            f"Failed to send token email to {_mask_email(associated_email)}",
            exc_info=True,
        )
