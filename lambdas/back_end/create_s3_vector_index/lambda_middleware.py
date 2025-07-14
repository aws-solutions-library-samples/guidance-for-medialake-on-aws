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
from botocore.exceptions import ClientError  # already imported? keep just once

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
        """
        Normalise any incoming event into the {metadata, payload:{data,assets}} shape
        and, when stepExternalPayload=True, download the *entire* off-loaded JSON
        so downstream code can simply read event["payload"]["data"].
        """

        # ── 0. Was the entire payload off-loaded to S3? ─────────────────────
        meta = ev.get("metadata", {})
        if meta.get("stepExternalPayload") == "True":
            loc = meta.get("stepExternalPayloadLocation", {})
            bucket = loc.get("bucket")
            key = loc.get("key")

            data: Any = {}
            if bucket and key:
                obj = self.s3.get_object(Bucket=bucket, Key=key)
                body = obj["Body"].read().decode("utf-8")
                data = json.loads(body)  # dict OR list – keep as-is

            return {
                "metadata": meta,
                "payload": {
                    "data": data,
                    "assets": ev.get("payload", {}).get("assets", []),
                },
            }

        self.logger.info("Original input event", extra={"event": ev})

        # ── 1. Step-Functions top-level wrapper (payload present) ───────────
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
        # ────────────────────────────────────────────────────────────────────

        # ── 2. Map/Task wrapper containing inventory_id ─────────────────────
        if isinstance(ev.get("item"), dict) and ev["item"].get("inventory_id"):
            item_obj = copy.deepcopy(ev["item"])
            inventory_id = item_obj["inventory_id"]

            # did the Map placeholder indicate off-load?
            step_ext = item_obj.pop("stepExternalPayload", False)
            step_ext_loc = item_obj.pop("stepExternalPayloadLocation", {})

            if step_ext:
                bucket = step_ext_loc.get("bucket")
                key = step_ext_loc.get("key")
                data = {}

                if bucket and key:
                    obj = self.s3.get_object(Bucket=bucket, Key=key)
                    body = obj["Body"].read().decode("utf-8")
                    data = json.loads(body)

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
                        "data": data,  # full JSON (dict OR list)
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
    # ---------------------------------------------------------------- make_out
    # ---------------------------------------------------------------- make_out
    def _make_output(
        self, result: Any, orig: Dict[str, Any], step_start: float
    ) -> Dict[str, Any]:

        # ───────────────────────── 0. Metadata build (unchanged) ─────────────────────────
        now = time.time()
        data = result

        if isinstance(data, dict):
            ext_id = data.get("externalJobId") or orig.get("metadata", {}).get(
                "externalJobId", ""
            )
            ext_st = data.get("externalJobStatus") or orig.get("metadata", {}).get(
                "externalJobStatus", ""
            )
            ext_rs = data.get("externalJobResult") or orig.get("metadata", {}).get(
                "externalJobResult", ""
            )
        else:
            ext_id = orig.get("metadata", {}).get("externalJobId", "")
            ext_st = orig.get("metadata", {}).get("externalJobStatus", "")
            ext_rs = orig.get("metadata", {}).get("externalJobResult", "")

        prev_meta = orig.get("metadata", {})
        status_is_complete = self.is_last and (
            ext_st == "" or (ext_st and ext_st.lower() == "completed")
        )

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

        # ───────────────────────── 1. Assets gather (unchanged) ─────────────────────────
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

        # map-block passthrough
        map_block = None
        if isinstance(orig.get("payload"), dict) and isinstance(
            orig["payload"].get("map"), dict
        ):
            map_block = copy.deepcopy(orig["payload"]["map"])

        # initial payload
        payload: Dict[str, Any] = {"data": data, "assets": assets}
        if map_block:
            payload["map"] = map_block

        # ───────────────────────── 2. Off-load logic ─────────────────────────
        candidate_raw = json.dumps(
            {"metadata": meta, "payload": payload}, default=_json_default
        ).encode()
        if len(candidate_raw) > self.max_response_size:

            # a) off-load only DATA blob
            key = meta["pipelineExecutionId"]
            self.s3.put_object(
                Bucket=self.external_payload_bucket,
                Key=key,
                Body=json.dumps(payload["data"], default=_json_default).encode(),
                ContentType="application/json",
            )
            self.logger.info(
                "[middleware] Off-loaded data to S3",
                extra={"bucket": self.external_payload_bucket, "key": key},
            )

            # b) create lightweight placeholders
            assets_from_orig = orig.get("payload", {}).get("assets", [])
            inv_id = (
                assets_from_orig[0].get("InventoryID")
                if isinstance(assets_from_orig, list) and assets_from_orig
                else None
            )

            placeholder_list = [
                {
                    "inventory_id": inv_id,
                    "stepExternalPayload": True,
                    "stepExternalPayloadLocation": {
                        "bucket": self.external_payload_bucket,
                        "key": key,
                    },
                }
            ]

            # c) shrink inline payload
            payload["data"] = placeholder_list
            payload["assets"] = []  # drop heavy assets
            payload.pop("map", None)  # drop map block entirely

            meta["stepExternalPayload"] = "True"
            meta["stepExternalPayloadLocation"] = {
                "bucket": self.external_payload_bucket,
                "key": key,
            }

        # ───────────────────────── 3. Return ─────────────────────────
        final_out = {"metadata": meta, "payload": payload}
        final_size = len(json.dumps(final_out, default=_json_default).encode())
        self.logger.info(
            "[middleware] Final output size (bytes)", extra={"bytes": final_size}
        )
        print(final_out)
        return final_out

    # ---------------------------------------------------------------- publish
    def _publish(self, out: Dict[str, Any]):
        try:
            self.eb.put_events(
                Entries=[
                    {
                        "Source": self.service,
                        "DetailType": f"{self.step_name}Output",
                        "Detail": json.dumps(out, default=_json_default),
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


def is_lambda_warmer_event(event: dict) -> bool:
    """
    Returns True if the event is a lambda warmer event (
                                                            e.g.,
                                                            triggered by the EventBridge rule for warming
                                                        ).
    Usage (at the top of your lambda):
        if is_lambda_warmer_event(event):
            return {"warmed": True}
    """
    # Check for a custom key or recognizable pattern
    if isinstance(event, dict):
        if event.get("lambda_warmer") is True:
            return True
        # Optionally, check for EventBridge scheduled event pattern
        if (
            event.get("source") == "aws.events"
            and event.get("detail-type") == "Scheduled Event"
        ):
            # Optionally, check for a custom resource or id
            if event.get("resources") and any(
                "lambda-warmer" in r for r in event["resources"]
            ):
                return True
    return False
