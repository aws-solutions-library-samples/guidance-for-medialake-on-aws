# middleware.py
import os
import json
import time
import uuid
import copy
import boto3
from typing import Any, Dict, Callable, Optional, TypeVar
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.middleware_factory import lambda_handler_decorator

R = TypeVar("R")


class LambdaMiddleware:
    """
    • Builds the exact output schema
    • Publishes to EventBridge (bus = EVENT_BUS_NAME)
    • Standardizes incoming events into {metadata, payload:{data,assets}}
      - if already in that shape, leaves it untouched
      - if it looks like an EventBridge event (has top-level 'detail'),
        it pulls detail into assets and empties data
    """

    def __init__(
        self,
        event_bus_name: Optional[str] = None,
        max_response_size: int = 240 * 1024,
        external_payload_bucket: Optional[str] = None,
        max_retries: int = 3,
    ):
        self.event_bus_name = event_bus_name or os.getenv("EVENT_BUS_NAME")
        if not self.event_bus_name:
            raise ValueError("EVENT_BUS_NAME env-var (or arg) required")

        self.external_payload_bucket = external_payload_bucket or os.getenv(
            "EXTERNAL_PAYLOAD_BUCKET"
        )
        if not self.external_payload_bucket:
            raise ValueError("EXTERNAL_PAYLOAD_BUCKET env-var required")

        self.max_response_size = max_response_size
        self.max_retries = max_retries

        self.eb = boto3.client("events")
        self.s3 = boto3.client("s3")

        self.service = os.getenv("SERVICE", "undefined_service")
        self.step_name = os.getenv("STEP_NAME", "undefined_step")
        self.pipe_name = os.getenv("PIPELINE_NAME", "undefined_pipeline")
        self.is_first = os.getenv("IS_FIRST", "false").lower() == "true"
        self.is_last = os.getenv("IS_LAST", "false").lower() == "true"

        self.logger = Logger(service=self.service)
        self.metrics = Metrics(namespace="MediaLake", service=self.service)
        self.tracer = Tracer(service=self.service)

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

    def _standardize_input(self, ev: Dict[str, Any]) -> Dict[str, Any]:
        # ── 1) Top-level object already standardised ──────────────────────────────
        if (
            isinstance(ev, dict)
            and isinstance(ev.get("metadata"), dict)
            and isinstance(ev.get("payload"), dict)
            and "data" in ev["payload"]
            and "assets" in ev["payload"]
        ):
            return ev

        # ── 1b) EventBridge envelope **whose `detail` is already standardised** ───
        #     (this is the case that was being double-wrapped)
        if isinstance(ev.get("detail"), dict):
            detail = ev["detail"]
            if (
                isinstance(detail.get("metadata"), dict)
                and isinstance(detail.get("payload"), dict)
                and "data" in detail["payload"]
                and "assets" in detail["payload"]
            ):
                # Bubble up execution / pipeline IDs if they were set on the envelope
                detail.setdefault(
                    "pipelineExecutionId", ev.get("pipelineExecutionId", "")
                )
                detail.setdefault("pipelineId", ev.get("pipelineId", ""))
                return detail

        # ── 2) Plain EventBridge envelope (detail *not* standardised) ─────────────
        if (
            isinstance(ev.get("detail"), dict)
            and not ev.get("payload")
            and not ev.get("assets")
        ):
            meta = {
                "service": self.service,
                "stepName": self.step_name,
                "pipelineName": self.pipe_name,
                "pipelineTraceId": str(uuid.uuid4()),
                "pipelineExecutionId": ev.get("pipelineExecutionId", ""),
                "pipelineId": ev.get("pipelineId", ""),
            }
            return {
                "metadata": meta,
                "payload": {
                    "data": {},
                    "assets": [copy.deepcopy(ev["detail"])],
                },
            }

        # ── 3) Fallback: wrap entire event in `data`, carry over any existing assets
        meta = {
            "service": self.service,
            "stepName": self.step_name,
            "pipelineName": self.pipe_name,
            "pipelineTraceId": ev.get("metadata", {}).get(
                "pipelineTraceId", str(uuid.uuid4())
            ),
            "pipelineExecutionId": ev.get("pipelineExecutionId", ""),
            "pipelineId": ev.get("pipelineId", ""),
        }
        payload: Dict[str, Any] = {"data": ev, "assets": []}
        if isinstance(ev.get("payload"), dict) and isinstance(
            ev["payload"].get("assets"), list
        ):
            payload["assets"] = copy.deepcopy(ev["payload"]["assets"])
        elif isinstance(ev.get("assets"), list):
            payload["assets"] = copy.deepcopy(ev["assets"])

        return {"metadata": meta, "payload": payload}

    def _make_output(
        self, result: Any, orig: Dict[str, Any], step_start: float
    ) -> Dict[str, Any]:
        """
        Build the outbound {metadata, payload:{data,assets}} object that the current
        Lambda step will publish.  Key points:

        • Preserves the incoming pipeline trace ID (or creates a new one)
        • Collapses any nested {metadata,payload} object that arrived in
        EventBridge `detail` so we don’t double-wrap
        • Optionally accepts a handler-supplied  `updatedAsset` that replaces the
        implicit aggregation logic
        • Spills `payload` to S3 if it would exceed `self.max_response_size`
        """
        now = time.time()
        data = result if isinstance(result, dict) else {"value": result}

        # ── strip external-job keys from `data`  ────────────────────────────────
        ext_id = data.pop("externalJobId", "")
        ext_st = data.pop("externalJobStatus", "")
        ext_rs = data.pop("externalJobResult", "")
        if not ext_id:
            ext_id = orig.get("metadata", {}).get("externalJobId", "")

        # ── build outbound metadata  ────────────────────────────────────────────
        prev_meta = orig.get("metadata", {})
        status_is_completed = self.is_last and (
            ext_st == "" or ext_st.lower() == "completed"
        )  # ← new rule
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
                else "Completed" if status_is_completed else "InProgress"
            ),
            "pipelineId": orig.get("pipelineId", ""),
            "pipelineExecutionId": orig.get("pipelineExecutionId", ""),
            "externalJobResult": ext_rs,
            "externalJobId": ext_id,
            "externalJobStatus": ext_st,
            "stepExternalPayload": "False",
            "stepExternalPayloadLocation": {},
        }

        # ── utility: flatten a standardised object to its inner assets ──────────
        def _inner_assets(obj: Any) -> list:
            """
            If *obj* is already in {metadata,payload:{data,assets}} form,
            return a deep copy of payload.assets; otherwise return [deepcopy(obj)].
            """
            if (
                isinstance(obj, dict)
                and isinstance(obj.get("metadata"), dict)
                and isinstance(obj.get("payload"), dict)
                and isinstance(obj["payload"].get("assets"), list)
            ):
                return copy.deepcopy(obj["payload"]["assets"])
            return [copy.deepcopy(obj)]

        # ── assemble `assets`  ──────────────────────────────────────────────────
        if isinstance(result, dict) and "updatedAsset" in result:
            # handler explicitly replaced / created a single asset
            assets = [copy.deepcopy(result.pop("updatedAsset"))]

        else:
            # asset that arrived inside EventBridge.detail (may be None)
            asset_from_detail = (
                orig.get("input", {}).get("detail")
                if isinstance(orig, dict) and "input" in orig
                else orig.get("detail") if isinstance(orig, dict) else orig
            )

            # assets already present on the incoming event, if any
            prev_assets: list = []
            if isinstance(orig, dict):
                if isinstance(orig.get("payload"), dict) and isinstance(
                    orig["payload"].get("assets"), list
                ):
                    prev_assets = copy.deepcopy(orig["payload"]["assets"])
                elif isinstance(orig.get("assets"), list):
                    prev_assets = copy.deepcopy(orig["assets"])

            # flatten to avoid double-wrapping and concatenate
            assets = prev_assets + (
                _inner_assets(asset_from_detail) if asset_from_detail else []
            )

        payload = {"data": data, "assets": assets}

        # ── off-load to S3 if payload is too large ──────────────────────────────
        raw = json.dumps(payload).encode()
        if len(raw) > self.max_response_size:
            key = f"{meta['pipelineExecutionId'] or 'unknown'}/{uuid.uuid4()}-payload.json"
            self.s3.put_object(Bucket=self.external_payload_bucket, Key=key, Body=raw)
            meta["stepExternalPayload"] = "True"
            meta["stepExternalPayloadLocation"] = {
                "bucket": self.external_payload_bucket,
                "key": key,
            }
            payload["data"] = {}

        return {"metadata": meta, "payload": payload}

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
        except Exception as e:
            self.logger.error(f"EventBridge publish failed: {e}")

    def __call__(self, handler: Callable[..., R]) -> Callable[..., R]:
        @lambda_handler_decorator
        def wrap(inner, event, ctx):
            raw = self._true_original(event)
            orig = copy.deepcopy(raw)

            # only wrap/unwrap if needed
            standard_event = self._standardize_input(orig)

            start = time.time()
            retries = 0
            while True:
                try:
                    result = inner(standard_event, ctx)
                    break
                except Exception:
                    if retries < self.max_retries:
                        retries += 1
                        time.sleep(min(2**retries, 30))
                        continue
                    raise

            out = self._make_output(result, orig, start)
            self._publish(out)
            return out

        return wrap(handler)


# factory
def lambda_middleware(**kw):
    mw = LambdaMiddleware(**kw)
    return lambda handler: mw(handler)
