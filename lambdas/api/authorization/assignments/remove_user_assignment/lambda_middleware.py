# middleware.py
import copy
import json
import os
import time
import uuid
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Callable, Dict, Optional, TypeVar

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.middleware_factory import lambda_handler_decorator

R = TypeVar("R")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _json_default(o):
    if isinstance(o, Decimal):
        return int(o) if o % 1 == 0 else float(o)
    raise TypeError


def safe_pop(d: Any, key: str, default: Any = "") -> Any:
    if isinstance(d, Mapping):
        return d.pop(key, default)
    return default


def _pick_pipeline_ids(ev: Dict[str, Any]) -> tuple[str, str]:
    """
    Extract pipelineExecutionId / pipelineId from any wrapper shape.
    Priority:
        1. Explicit keys already present (pipelineExecutionId, pipelineId)
        2. Step‑Functions fields   (executionName, stateMachineArn)
    """
    exec_id = ev.get("pipelineExecutionId") or ev.get("executionName") or ""
    pipe_id = ev.get("pipelineId") or ev.get("stateMachineArn") or ""
    return exec_id, pipe_id


# ──────────────────────────────────────────────────────────────────────────────
# Middleware
# ──────────────────────────────────────────────────────────────────────────────
class LambdaMiddleware:
    """
    Normalises *any* incoming event into
        {metadata, payload:{data, assets, map:{item}}}
    and guarantees that metadata.pipelineExecutionId / metadata.pipelineId
    survive every hop (Step Functions wrappers, Map iterators, etc.).
    """

    # --------------------------------------------------------------------- init
    def __init__(
        self,
        event_bus_name: Optional[str] = None,
        max_response_size: int = 240 * 1024,
        external_payload_bucket: Optional[str] = None,
        max_retries: int = 3,
        assets_table_name: Optional[str] = None,
    ):
        self.event_bus_name = event_bus_name or os.getenv("EVENT_BUS_NAME")
        if not self.event_bus_name:
            raise ValueError("EVENT_BUS_NAME env‑var (or arg) required")

        self.external_payload_bucket = external_payload_bucket or os.getenv(
            "EXTERNAL_PAYLOAD_BUCKET"
        )
        if not self.external_payload_bucket:
            raise ValueError("EXTERNAL_PAYLOAD_BUCKET env‑var required")

        self.max_response_size = max_response_size
        self.max_retries = max_retries

        self.eb = boto3.client("events")
        self.s3 = boto3.client("s3")

        # Service metadata
        self.service = os.getenv("SERVICE", "undefined_service")
        self.step_name = os.getenv("STEP_NAME", "undefined_step")
        self.pipe_name = os.getenv("PIPELINE_NAME", "undefined_pipeline")
        self.is_first = os.getenv("IS_FIRST", "false").lower() == "true"
        self.is_last = os.getenv("IS_LAST", "false").lower() == "true"

        # Observability
        self.logger = Logger(service=self.service)
        self.metrics = Metrics(namespace="MediaLake", service=self.service)
        self.tracer = Tracer(service=self.service)

        # DynamoDB (optional)
        self.assets_table_name = assets_table_name or os.getenv("MEDIALAKE_ASSET_TABLE")
        if self.assets_table_name:
            self.ddb = boto3.resource("dynamodb")
            self.assets_table = self.ddb.Table(self.assets_table_name)
        else:
            self.ddb = self.assets_table = None

    # ---------------------------------------------------------- private helpers
    @staticmethod
    def _true_original(ev: Dict[str, Any]) -> Dict[str, Any]:
        cur = ev.get("originalEvent", ev)
        while (
            isinstance(cur, dict)
            and isinstance(cur.get("payload"), dict)
            and isinstance(cur["payload"].get("event"), dict)
        ):
            cur = cur["payload"]["event"]
        return cur

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # DDB asset fetch
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def _fetch_asset_record(self, inventory_id: str) -> Optional[Dict[str, Any]]:
        if not self.assets_table:
            return None
        try:
            resp = self.assets_table.get_item(Key={"InventoryID": inventory_id})
            return resp.get("Item")
        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"DDB lookup failed for {inventory_id}: {exc}")
            return None

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Input standardisation
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def _standardize_input(self, ev: Dict[str, Any]) -> Dict[str, Any]:
        # ── Handle external payload offload ─────────────────────────────────
        meta = ev.get("metadata", {})
        if meta.get("stepExternalPayload") == "True":
            print("external")
            loc = meta.get("stepExternalPayloadLocation", {})
            bucket = loc.get("bucket")
            key = loc.get("key")
            data = {}

            if bucket and key:
                # pull the actual payload from S3
                obj = self.s3.get_object(Bucket=bucket, Key=key)
                body = obj["Body"].read().decode("utf-8")
                parsed = json.loads(body)

                if isinstance(parsed, list):
                    # prepare for Map: one entry per list item
                    data = [
                        {"s3_bucket": bucket, "s3_key": key, "index": idx}
                        for idx in range(len(parsed))
                    ]
                else:
                    # single object, pass straight through
                    data = parsed

            return {
                "metadata": meta,
                "payload": {
                    "data": data,
                    "assets": ev.get("payload", {}).get("assets", []),
                },
            }
        self.logger.info("Original input event", extra={"event": ev})

        # ── 0) Step‑Functions top‑level wrapper (payload present) ─────────────
        if (
            isinstance(ev.get("executionName"), str)
            and isinstance(ev.get("stateMachineArn"), str)
            and isinstance(ev.get("payload"), dict)
        ):
            exec_id, pipe_id = _pick_pipeline_ids(ev)

            inner_event = copy.deepcopy(ev["payload"])
            std_inner = self._standardize_input(inner_event)

            std_inner.setdefault("metadata", {})
            std_inner["metadata"]["pipelineExecutionId"] = exec_id
            std_inner["metadata"]["pipelineId"] = pipe_id
            return std_inner
        # ───────────────────────────────────────────────────────────────────────

        # ── 1) Map/Task wrapper containing inventory_id ───────────────────────────
        if isinstance(ev.get("item"), dict) and ev["item"].get("inventory_id"):
            # mutable copy of the incoming item
            item_obj = copy.deepcopy(ev["item"])
            inventory_id = item_obj["inventory_id"]

            # extract any offload flags and the map index
            step_ext = item_obj.pop("stepExternalPayload", False)
            step_ext_loc = item_obj.pop("stepExternalPayloadLocation", {})
            item_index = item_obj.get("index", 0)

            # ---- external-payload placeholder path ----
            if step_ext:
                bucket = step_ext_loc.get("bucket")
                key = step_ext_loc.get("key")
                data = None

                if bucket and key:
                    # pull the actual payload from S3
                    obj = self.s3.get_object(Bucket=bucket, Key=key)
                    body = obj["Body"].read().decode("utf-8")
                    parsed = json.loads(body)

                    if isinstance(parsed, list):
                        # select just the one entry at item_index
                        try:
                            data = parsed[item_index]
                        except (IndexError, TypeError):
                            # fallback to empty dict if index is bad
                            data = {}
                    else:
                        # single object, pass straight through
                        data = parsed

                # rebuild metadata exactly as your top‐level offload branch
                meta = {
                    "service": self.service,
                    "stepName": self.step_name,
                    "pipelineName": self.pipe_name,
                    "pipelineTraceId": str(uuid.uuid4()),
                    "stepExternalPayload": "True",
                    "stepExternalPayloadLocation": step_ext_loc,
                }
                return {
                    "metadata": meta,
                    "payload": {
                        "data": {"item": data},
                        "assets": ev.get("payload", {}).get("assets", []),
                    },
                }

            # ---- normal Map/Task path ----
            asset_rec = self._fetch_asset_record(inventory_id)
            exec_id, pipe_id = _pick_pipeline_ids(ev)

            meta = {
                "service": self.service,
                "stepName": self.step_name,
                "pipelineName": self.pipe_name,
                "pipelineTraceId": str(uuid.uuid4()),
                "pipelineExecutionId": exec_id,
                "pipelineId": pipe_id,
            }
            return {
                "metadata": meta,
                "payload": {
                    "data": item_obj,
                    "assets": [asset_rec] if asset_rec else [],
                    "map": {"item": item_obj},
                },
            }

        # ── 2) Already‑standardised top‑level object ──────────────────────────
        if (
            isinstance(ev, dict)
            and isinstance(ev.get("metadata"), dict)
            and isinstance(ev.get("payload"), dict)
            and "data" in ev["payload"]
            and "assets" in ev["payload"]
        ):
            return ev

        # ── 2b) EventBridge envelope whose detail is already standardised ────
        if isinstance(ev.get("detail"), dict):
            detail = ev["detail"]
            if (
                isinstance(detail.get("metadata"), dict)
                and isinstance(detail.get("payload"), dict)
                and "data" in detail["payload"]
                and "assets" in detail["payload"]
            ):
                exec_id, pipe_id = _pick_pipeline_ids(ev)
                detail.setdefault("pipelineExecutionId", exec_id)
                detail.setdefault("pipelineId", pipe_id)
                return detail

        # ── 3) Plain EventBridge envelope (detail *not* standardised) ─────────
        if (
            isinstance(ev.get("detail"), dict)
            and not ev.get("payload")
            and not ev.get("assets")
        ):
            exec_id, pipe_id = _pick_pipeline_ids(ev)
            meta = {
                "service": self.service,
                "stepName": self.step_name,
                "pipelineName": self.pipe_name,
                "pipelineTraceId": str(uuid.uuid4()),
                "pipelineExecutionId": exec_id,
                "pipelineId": pipe_id,
            }
            return {
                "metadata": meta,
                "payload": {
                    "data": {},
                    "assets": [copy.deepcopy(ev["detail"])],
                },
            }

        # ── 4) Fallback – wrap full event, still keep IDs if present ──────────
        exec_id, pipe_id = _pick_pipeline_ids(ev)
        meta = {
            "service": self.service,
            "stepName": self.step_name,
            "pipelineName": self.pipe_name,
            "pipelineTraceId": ev.get("metadata", {}).get(
                "pipelineTraceId", str(uuid.uuid4())
            ),
            "pipelineExecutionId": exec_id,
            "pipelineId": pipe_id,
        }
        payload: Dict[str, Any] = {"data": ev, "assets": []}

        if isinstance(ev.get("payload"), dict) and isinstance(
            ev["payload"].get("assets"), list
        ):
            payload["assets"] = copy.deepcopy(ev["payload"]["assets"])
        elif isinstance(ev.get("assets"), list):
            payload["assets"] = copy.deepcopy(ev["assets"])

        if isinstance(ev.get("payload"), dict) and isinstance(
            ev["payload"].get("map"), dict
        ):
            payload["map"] = copy.deepcopy(ev["payload"]["map"])
        elif isinstance(ev.get("map"), dict):
            payload["map"] = copy.deepcopy(ev["map"])

        return {"metadata": meta, "payload": payload}

    # ---------------------------------------------------------------- make_out
    def _make_output(
        self, result: Any, orig: Dict[str, Any], step_start: float
    ) -> Dict[str, Any]:
        """
        Construct and publish the standardized output event, handling large payloads by offloading
        to S3 and embedding or listing external payload references for downstream Map states.
        """
        now = time.time()
        data = result

        # Extract external job fields
        ext_id = safe_pop(data, "externalJobId") or orig.get("metadata", {}).get(
            "externalJobId", ""
        )
        ext_st = safe_pop(data, "externalJobStatus") or orig.get("metadata", {}).get(
            "externalJobStatus", ""
        )
        ext_rs = safe_pop(data, "externalJobResult") or orig.get("metadata", {}).get(
            "externalJobResult", ""
        )

        prev_meta = orig.get("metadata", {})
        status_is_complete = self.is_last and (
            ext_st == "" or ext_st.lower() == "completed"
        )

        # Build metadata
        meta = {
            "service": self.service,
            "stepName": self.step_name,
            "stepStatus": "Completed",
            "stepResult": "Success",
            "pipelineTraceId": prev_meta.get("pipelineTraceId", str(uuid.uuid4())),
            "stepExecutionStartTime": prev_meta.get(
                "stepExecutionStartTime", step_start
            ),
            "stepExecutionEndTime": now,
            "stepExecutionDuration": round(now - step_start, 3),
            "pipelineExecutionStartTime": orig.get("pipelineExecutionStartTime", ""),
            "pipelineExecutionEndTime": now if self.is_last else "",
            "pipelineName": self.pipe_name,
            "pipelineStatus": (
                "Started"
                if self.is_first
                else "Completed" if status_is_complete else "InProgress"
            ),
            "pipelineId": prev_meta.get("pipelineId", ""),
            "pipelineExecutionId": prev_meta.get("pipelineExecutionId", ""),
            "externalJobResult": ext_rs,
            "externalJobId": ext_id,
            "externalJobStatus": ext_st,
            "stepExternalPayload": "False",
            "stepExternalPayloadLocation": {},
        }

        # Gather previous assets
        def _inner_assets(obj: Any) -> list:
            if (
                isinstance(obj, dict)
                and isinstance(obj.get("metadata"), dict)
                and isinstance(obj.get("payload"), dict)
                and isinstance(obj["payload"].get("assets"), list)
            ):
                return copy.deepcopy(obj["payload"]["assets"])
            return [copy.deepcopy(obj)]

        if isinstance(result, dict) and "updatedAsset" in result:
            assets = [copy.deepcopy(result.pop("updatedAsset"))]
        else:
            asset_from_detail = (
                orig.get("input", {}).get("detail")
                if isinstance(orig, dict) and "input" in orig
                else orig.get("detail") if isinstance(orig, dict) else orig
            )
            prev_assets = []
            if isinstance(orig, dict):
                if isinstance(orig.get("payload"), dict) and isinstance(
                    orig["payload"].get("assets"), list
                ):
                    prev_assets = copy.deepcopy(orig["payload"]["assets"])
                elif isinstance(orig.get("assets"), list):
                    prev_assets = copy.deepcopy(orig["assets"])
            assets = prev_assets + (
                _inner_assets(asset_from_detail) if asset_from_detail else []
            )

        # Preserve map block if present
        map_block = None
        if isinstance(orig.get("payload"), dict) and isinstance(
            orig["payload"].get("map"), dict
        ):
            map_block = copy.deepcopy(orig["payload"]["map"])

        # Prepare payload
        payload: Dict[str, Any] = {"data": data, "assets": assets}
        if map_block:
            payload["map"] = map_block

        # Serialize and offload if too large
        raw = json.dumps(payload["data"], default=_json_default).encode()
        if len(raw) > self.max_response_size:
            key = f"{meta['pipelineExecutionId']}"
            self.s3.put_object(Bucket=self.external_payload_bucket, Key=key, Body=raw)
            meta["stepExternalPayload"] = "True"
            meta["stepExternalPayloadLocation"] = {
                "bucket": self.external_payload_bucket,
                "key": key,
            }
            payload["data"] = {}

            # pull inventory_id from the first asset, if present
            assets = orig.get("payload", {}).get("assets", [])
            inventory_id = None
            if isinstance(assets, list) and assets:
                inventory_id = assets[0].get("InventoryID")

            # Fetch external list file references
            loc = meta["stepExternalPayloadLocation"]
            try:
                resp = self.s3.get_object(Bucket=loc["bucket"], Key=loc["key"])
                body_text = resp["Body"].read().decode("utf-8")
                external_json = json.loads(body_text)

                payload["data"] = [
                    {
                        "inventory_id": inventory_id,
                        "stepExternalPayload": True,
                        "stepExternalPayloadLocation": loc,
                        "index": idx,
                    }
                    for idx in range(len(external_json))
                ]
            except Exception as exc:
                self.logger.error(f"Failed to fetch external payload: {exc}")

        return {"metadata": meta, "payload": payload}

    # ---------------------------------------------------------------- publish
    def _publish(self, out: Dict[str, Any]):
        try:
            self.eb.put_events(
                Entries=[
                    {
                        "Source": self.service,
                        "DetailType": f"{self.step_name}Output",
                        "Detail": json.dumps(out),
                        "EventBusName": self.event_bus_name,
                    }
                ]
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"EventBridge publish failed: {exc}")

    # ----------------------------------------------------------------- caller
    def __call__(self, handler: Callable[..., R]) -> Callable[..., R]:
        @lambda_handler_decorator
        def wrap(inner, event, ctx):
            raw = self._true_original(event)
            standard_event = self._standardize_input(copy.deepcopy(raw))

            start = time.time()
            retries = 0
            while True:
                try:
                    result = inner(standard_event, ctx)
                    break
                except Exception:  # noqa: BLE001
                    if retries < self.max_retries:
                        retries += 1
                        time.sleep(min(2**retries, 30))
                        continue
                    raise

            out = self._make_output(result, standard_event, start)
            self._publish(out)
            return out

        return wrap(handler)


# ──────────────────────────────────────────────────────────────────────────────
# Factory helper
# ──────────────────────────────────────────────────────────────────────────────
def lambda_middleware(**kw):
    mw = LambdaMiddleware(**kw)
    return lambda handler: mw(handler)
