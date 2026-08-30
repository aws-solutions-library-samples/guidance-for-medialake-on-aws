"""
Coactive AI External Service Plugin
==================================
Deletes MediaLake assets from a Coactive dataset.

Coactive's documented deletion API is a single batch endpoint:

    POST https://api.coactive.ai/api/v0/delete/assets
    {"dataset_id": "<uuid>", "assets": [{"asset_type": "image|video",
                                         "identifier": "<coactive id|path>"}]}
    -> 202 {"org_id", "dataset_id", "assets": [{..., "delete_job_id"}]}

See https://docs.coactive.ai/api-reference/api-reference/ingestion/delete-assets

Two properties of that contract drive the design here:

* **Deletion is asynchronous.** A 202 means the deletion jobs were *enqueued*,
  not that the assets are gone. Each accepted asset comes back with a
  ``delete_job_id``, which is the only handle on the actual work, so the ids are
  logged rather than discarded.
* **At most 100 assets per request**, hence ``MAX_ASSETS_PER_REQUEST`` and the
  chunking in :meth:`_delete_identifiers`.

Failure policy: a Coactive failure never blocks MediaLake's own deletion — the
user should not be stuck because a third party is down. Instead every asset that
could not be removed is emitted as a single structured log line tagged
``COACTIVE_DELETE_ORPHAN`` carrying everything needed to replay the delete later.
To list outstanding orphans in CloudWatch Logs Insights:

    fields @timestamp, inventory_id, dataset_id, asset_type, identifier, reason
    | filter marker = "COACTIVE_DELETE_ORPHAN"
    | sort @timestamp desc

Replaying one is then a POST of ``{dataset_id, assets:[{asset_type,
identifier}]}`` to the endpoint above.
"""

import http.client
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import boto3
import requests
from botocore.exceptions import ClientError
from search_provider_models import AssetDeletionResult, ExternalServicePlugin

# Log marker for assets that MediaLake deleted but Coactive did not confirm.
# Kept as a module constant so the Logs Insights query above and the tests
# reference the same literal.
ORPHAN_MARKER = "COACTIVE_DELETE_ORPHAN"


class CoactivePlugin(ExternalServicePlugin):
    """Plugin for Coactive AI external service integration"""

    # Default endpoints. `delete` lives on api.coactive.ai/api/v0 — a different
    # host and version from the dataset-management API on app.coactive.ai/api/v1,
    # which is why it needs its own setting rather than being derived from
    # dataset_endpoint.
    DEFAULT_AUTH_ENDPOINT = "https://api.coactive.ai/api/v0/login"
    DEFAULT_SEARCH_ENDPOINT = "https://api.coactive.ai/api/v1/search/text-to-image"
    DEFAULT_DATASET_ENDPOINT = "https://app.coactive.ai/api/v1"
    DEFAULT_DELETE_ENDPOINT = "https://api.coactive.ai/api/v0/delete/assets"

    #: Hard limit from the API contract.
    MAX_ASSETS_PER_REQUEST = 100

    #: Coactive's `asset_type` enum.
    SUPPORTED_ASSET_TYPES = ("image", "video")

    REQUEST_TIMEOUT_SECONDS = 30
    MAX_ATTEMPTS = 3
    RETRY_BACKOFF_SECONDS = (1, 3)

    def __init__(self, config: Dict[str, Any], logger, metrics):
        super().__init__(config, logger, metrics)
        self.secrets_client = boto3.client("secretsmanager")
        self._api_key = None
        self._dataset_id = None
        # Cached for the lifetime of the plugin instance. Without this, deleting
        # N assets meant N login round trips.
        self._access_token = None

    # ── endpoint resolution ───────────────────────────────────────────────

    def _get_auth_endpoint(self) -> str:
        return self.config.get("auth_endpoint") or self.DEFAULT_AUTH_ENDPOINT

    def _get_search_endpoint(self) -> str:
        return self.config.get("search_endpoint") or self.DEFAULT_SEARCH_ENDPOINT

    def _get_dataset_endpoint(self) -> str:
        return self.config.get("dataset_endpoint") or self.DEFAULT_DATASET_ENDPOINT

    def _get_delete_endpoint(self) -> str:
        return self.config.get("delete_endpoint") or self.DEFAULT_DELETE_ENDPOINT

    def get_service_name(self) -> str:
        return "coactive"

    def is_available(self) -> bool:
        """Check if Coactive AI service is available and properly configured"""
        try:
            if not self.config.get("dataset_id"):
                self.logger.warning("Coactive dataset_id not configured")
                return False

            if not self.config.get("auth", {}).get("secret_arn"):
                self.logger.warning("Coactive API key not configured")
                return False

            if not self._get_api_key():
                self.logger.warning("Failed to retrieve Coactive API key")
                return False

            return True

        except Exception as e:
            self.logger.warning(f"Coactive availability check failed: {str(e)}")
            return False

    def supports_asset_type(self, asset_type: str) -> bool:
        return (asset_type or "").lower() in self.SUPPORTED_ASSET_TYPES

    # ── identifier resolution ─────────────────────────────────────────────

    @staticmethod
    def _stored_coactive_id(asset_record: Dict[str, Any]) -> Optional[str]:
        """Return the Coactive id recorded at ingestion, if present.

        The ingestion pipelines write ``{"coactive": "<id>"}`` into
        ``Metadata.ExternalIDs`` (see the status_get_response_mapping templates).
        """
        external_ids = asset_record.get("Metadata", {}).get("ExternalIDs") or []
        for entry in external_ids:
            if isinstance(entry, dict) and entry.get("coactive"):
                return str(entry["coactive"]).strip() or None
        return None

    @staticmethod
    def _s3_path(asset_record: Dict[str, Any]) -> Optional[str]:
        """Build the ``s3://bucket/key`` path for the asset's main representation.

        Coactive accepts either its own asset id or a path string as the
        identifier, so this is the fallback when ingestion never recorded an id
        (older assets, or a pipeline whose status callback did not land).
        """
        try:
            location = asset_record["DigitalSourceAsset"]["MainRepresentation"][
                "StorageInfo"
            ]["PrimaryLocation"]
            bucket = location.get("Bucket")
            key = (location.get("ObjectKey") or {}).get("FullPath")
            if bucket and key:
                return f"s3://{bucket}/{key.lstrip('/')}"
        except (KeyError, TypeError):
            pass
        return None

    def _resolve_identifier(
        self, asset_record: Dict[str, Any], inventory_id: str
    ) -> Tuple[Optional[str], str]:
        """Pick the identifier to delete by, preferring the recorded Coactive id.

        Returns ``(identifier, source)`` where source is ``"external_id"`` or
        ``"s3_path"`` for logging, or ``(None, "none")`` when neither is
        available.
        """
        coactive_id = self._stored_coactive_id(asset_record)
        if coactive_id:
            return coactive_id, "external_id"

        path = self._s3_path(asset_record)
        if path:
            self.logger.info(
                "No stored Coactive id; falling back to the S3 path identifier",
                extra={"inventory_id": inventory_id, "identifier": path},
            )
            return path, "s3_path"

        return None, "none"

    # ── public entry point ────────────────────────────────────────────────

    def delete_asset(
        self, asset_record: Dict[str, Any], inventory_id: str
    ) -> AssetDeletionResult:
        """Delete a single asset from the configured Coactive dataset."""
        try:
            asset_type = (
                asset_record.get("DigitalSourceAsset", {}).get("Type", "") or ""
            ).lower()

            if not self.supports_asset_type(asset_type):
                return AssetDeletionResult(
                    success=True,
                    message=f"Asset type '{asset_type}' not supported by Coactive",
                    deleted_count=0,
                )

            identifier, source = self._resolve_identifier(asset_record, inventory_id)
            if not identifier:
                # Nothing to delete by. Report failure rather than pretending:
                # the embedding may well still be in Coactive.
                reason = "no Coactive id recorded and no S3 path on the asset record"
                self._log_orphan(
                    inventory_id=inventory_id,
                    asset_type=asset_type,
                    identifier=None,
                    reason=reason,
                )
                return AssetDeletionResult(
                    success=False,
                    message=f"Cannot delete from Coactive: {reason}",
                    errors=[reason],
                )

            return self._delete_identifiers(
                [(asset_type, identifier)],
                inventory_id=inventory_id,
                identifier_source=source,
            )

        except Exception as e:
            self.logger.exception(
                "Coactive asset deletion failed",
                extra={"inventory_id": inventory_id},
            )
            self.metrics.add_metric(
                name="CoactiveDeletionErrors", unit="Count", value=1
            )
            self._log_orphan(
                inventory_id=inventory_id,
                asset_type=(
                    asset_record.get("DigitalSourceAsset", {}).get("Type", "") or ""
                ).lower(),
                identifier=self._stored_coactive_id(asset_record)
                or self._s3_path(asset_record),
                reason=f"unhandled exception: {e}",
            )
            return AssetDeletionResult(
                success=False,
                message=f"Coactive deletion failed: {str(e)}",
                errors=[str(e)],
            )

    def delete_assets(
        self, assets: List[Tuple[str, str]], inventory_id: str = "batch"
    ) -> AssetDeletionResult:
        """Delete many ``(asset_type, identifier)`` pairs, chunked to the API limit.

        Exposed for a future bulk-delete caller: the API accepts up to 100 assets
        per request, so a batch delete of N assets should be ceil(N/100) requests
        rather than N.
        """
        return self._delete_identifiers(assets, inventory_id=inventory_id)

    # ── HTTP ──────────────────────────────────────────────────────────────

    def _delete_identifiers(
        self,
        assets: List[Tuple[str, str]],
        inventory_id: str,
        identifier_source: str = "mixed",
    ) -> AssetDeletionResult:
        """POST the deletion request(s), chunked to MAX_ASSETS_PER_REQUEST."""
        dataset_id = self._get_dataset_id()
        if not dataset_id:
            reason = "Coactive dataset_id is not configured"
            self.logger.error(reason, extra={"inventory_id": inventory_id})
            return AssetDeletionResult(success=False, message=reason, errors=[reason])

        access_token = self._get_access_token()
        if not access_token:
            reason = "could not obtain a Coactive access token"
            for asset_type, identifier in assets:
                self._log_orphan(
                    inventory_id=inventory_id,
                    asset_type=asset_type,
                    identifier=identifier,
                    reason=reason,
                )
            return AssetDeletionResult(success=False, message=reason, errors=[reason])

        accepted = 0
        errors: List[str] = []
        job_ids: List[str] = []

        for start in range(0, len(assets), self.MAX_ASSETS_PER_REQUEST):
            chunk = assets[start : start + self.MAX_ASSETS_PER_REQUEST]
            payload = {
                "dataset_id": dataset_id,
                "assets": [
                    {"asset_type": asset_type, "identifier": identifier}
                    for asset_type, identifier in chunk
                ],
            }

            ok, detail, chunk_job_ids = self._post_delete(payload, access_token)

            if ok:
                accepted += len(chunk)
                job_ids.extend(chunk_job_ids)
            else:
                errors.append(detail)
                for asset_type, identifier in chunk:
                    self._log_orphan(
                        inventory_id=inventory_id,
                        asset_type=asset_type,
                        identifier=identifier,
                        reason=detail,
                    )

        if accepted:
            self.metrics.add_metric(
                name="CoactiveAssetsDeleted", unit="Count", value=accepted
            )
            # The job ids are the only handle on the asynchronous work, so keep
            # them in the log rather than dropping them on the floor.
            self.logger.info(
                "Coactive deletion jobs enqueued",
                extra={
                    "inventory_id": inventory_id,
                    "dataset_id": dataset_id,
                    "accepted_count": accepted,
                    "delete_job_ids": job_ids,
                    "identifier_source": identifier_source,
                },
            )

        if errors:
            self.metrics.add_metric(
                name="CoactiveDeletionErrors", unit="Count", value=len(errors)
            )

        message = (
            f"Enqueued Coactive deletion for {accepted} asset(s)"
            if accepted
            else "No Coactive deletions were accepted"
        )
        if errors:
            message += f"; {len(errors)} request(s) failed"

        return AssetDeletionResult(
            success=not errors,
            message=message,
            deleted_count=accepted,
            errors=errors,
        )

    def _post_delete(
        self, payload: Dict[str, Any], access_token: str
    ) -> Tuple[bool, str, List[str]]:
        """One delete request, with retries. Returns (ok, detail, delete_job_ids)."""
        endpoint = self._get_delete_endpoint()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "MediaLake/1.0",
        }

        last_detail = "no attempt made"

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                response = requests.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self.REQUEST_TIMEOUT_SECONDS,
                )
            except requests.exceptions.RequestException as e:
                last_detail = f"network error: {e}"
                if attempt < self.MAX_ATTEMPTS:
                    self._sleep_before_retry(attempt, last_detail)
                    continue
                return False, last_detail, []

            # 202 is the documented success; 200 accepted defensively in case the
            # API is ever tightened up to return it.
            if response.status_code in (200, 202):
                return True, "accepted", self._extract_job_ids(response)

            body = (response.text or "")[:500]

            if response.status_code == 422:
                # Unprocessable: a malformed request or an identifier Coactive
                # will not accept. Retrying cannot help.
                return (
                    False,
                    f"HTTP 422 unprocessable entity (identifier rejected): {body}",
                    [],
                )

            if response.status_code in (401, 403):
                # Token may have expired mid-run; drop it so the next call
                # re-authenticates, then retry once more.
                self._access_token = None
                last_detail = f"HTTP {response.status_code} auth rejected: {body}"
                if attempt < self.MAX_ATTEMPTS:
                    refreshed = self._get_access_token()
                    if refreshed:
                        headers["Authorization"] = f"Bearer {refreshed}"
                    self._sleep_before_retry(attempt, last_detail)
                    continue
                return False, last_detail, []

            if response.status_code == 429 or response.status_code >= 500:
                last_detail = f"HTTP {response.status_code}: {body}"
                if attempt < self.MAX_ATTEMPTS:
                    self._sleep_before_retry(attempt, last_detail)
                    continue
                return False, last_detail, []

            # Anything else — including 404 — is a genuine failure. A 404 used to
            # be reported as success here, which silently orphaned every asset
            # while the delete looked clean.
            return False, f"HTTP {response.status_code}: {body}", []

        return False, last_detail, []

    def _sleep_before_retry(self, attempt: int, detail: str) -> None:
        delay = self.RETRY_BACKOFF_SECONDS[
            min(attempt - 1, len(self.RETRY_BACKOFF_SECONDS) - 1)
        ]
        self.logger.warning(
            "Coactive delete attempt failed; retrying",
            extra={"attempt": attempt, "retry_in_seconds": delay, "detail": detail},
        )
        time.sleep(delay)

    @staticmethod
    def _extract_job_ids(response) -> List[str]:
        """Pull ``delete_job_id`` values out of a 202 body, tolerating surprises."""
        try:
            body = response.json()
        except ValueError:
            return []
        if not isinstance(body, dict):
            return []
        return [
            str(entry["delete_job_id"])
            for entry in body.get("assets") or []
            if isinstance(entry, dict) and entry.get("delete_job_id")
        ]

    # ── orphan logging ────────────────────────────────────────────────────

    def _log_orphan(
        self,
        inventory_id: str,
        asset_type: str,
        identifier: Optional[str],
        reason: str,
    ) -> None:
        """Record an asset MediaLake removed but Coactive did not confirm.

        One structured line per asset, carrying everything a replay needs. See
        the module docstring for the Logs Insights query and the replay request.
        """
        self.logger.error(
            "Coactive deletion could not be confirmed; asset may be orphaned",
            extra={
                "marker": ORPHAN_MARKER,
                "inventory_id": inventory_id,
                "dataset_id": self.config.get("dataset_id"),
                "asset_type": asset_type,
                "identifier": identifier,
                "reason": reason,
                "delete_endpoint": self._get_delete_endpoint(),
            },
        )
        self.metrics.add_metric(name="CoactiveOrphanedAssets", unit="Count", value=1)

    # ── auth / config ─────────────────────────────────────────────────────

    def _get_api_key(self) -> Optional[str]:
        """Get the Coactive personal token from AWS Secrets Manager"""
        if self._api_key:
            return self._api_key

        try:
            secret_arn = self.config.get("auth", {}).get("secret_arn")
            if not secret_arn:
                return None

            response = self.secrets_client.get_secret_value(SecretId=secret_arn)
            secret_data = json.loads(response["SecretString"])
            self._api_key = secret_data.get("x-api-key") or secret_data.get("api_key")
            return self._api_key

        except ClientError as e:
            self.logger.error(f"Failed to retrieve Coactive API key: {e}")
            return None

    def _get_dataset_id(self) -> Optional[str]:
        if self._dataset_id:
            return self._dataset_id
        self._dataset_id = self.config.get("dataset_id")
        return self._dataset_id

    def _get_access_token(self) -> Optional[str]:
        """Exchange the personal token for a short-lived access token.

        Same flow as ``system_search_put.create_coactive_dataset``: POST the
        login endpoint with ``grant_type: refresh_token`` and the personal token
        as the bearer. Cached on the instance so a multi-asset delete performs
        one login rather than one per asset.
        """
        if self._access_token:
            return self._access_token

        try:
            personal_token = self._get_api_key()
            if not personal_token:
                self.logger.error("No Coactive personal token available")
                return None

            parsed = urlparse(self._get_auth_endpoint())
            conn = http.client.HTTPSConnection(
                parsed.netloc, timeout=self.REQUEST_TIMEOUT_SECONDS
            )
            try:
                conn.request(
                    "POST",
                    parsed.path,
                    body=json.dumps({"grant_type": "refresh_token"}),
                    headers={
                        "Authorization": f"Bearer {personal_token}",
                        "Content-Type": "application/json",
                        "User-Agent": "MediaLake/1.0",
                    },
                )
                response = conn.getresponse()
                response_data = response.read().decode("utf-8")
                status = response.status
            finally:
                conn.close()

            if status != 200:
                self.logger.error(
                    "Coactive authentication failed",
                    extra={"status": status, "body": response_data[:500]},
                )
                return None

            access_token = (json.loads(response_data) or {}).get("access_token")
            if not access_token:
                self.logger.error("No access_token in the Coactive login response")
                return None

            self._access_token = access_token
            self.logger.info("Obtained Coactive access token")
            return access_token

        except Exception as e:
            self.logger.error(f"Failed to get Coactive access token: {str(e)}")
            return None
