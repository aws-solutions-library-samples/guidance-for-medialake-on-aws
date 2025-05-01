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

        self.external_payload_bucket = (
            external_payload_bucket or os.getenv("EXTERNAL_PAYLOAD_BUCKET")
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
        # 1) Already standardized?
        if (
            isinstance(ev, dict)
            and isinstance(ev.get("metadata"), dict)
            and isinstance(ev.get("payload"), dict)
            and "data" in ev["payload"]
            and "assets" in ev["payload"]
        ):
            return ev

        # 2) EventBridge envelope?
        if isinstance(ev.get("detail"), dict) and not ev.get("payload") and not ev.get("assets"):
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

        # 3) Fallback: wrap entire event in data, carry any existing assets
        meta = {
            "service": self.service,
            "stepName": self.step_name,
            "pipelineName": self.pipe_name,
            "pipelineTraceId": ev.get("metadata", {}).get("pipelineTraceId", str(uuid.uuid4())),
            "pipelineExecutionId": ev.get("pipelineExecutionId", ""),
            "pipelineId": ev.get("pipelineId", ""),
        }
        payload: Dict[str, Any] = {"data": ev, "assets": []}
        if isinstance(ev.get("payload"), dict) and isinstance(ev["payload"].get("assets"), list):
            payload["assets"] = copy.deepcopy(ev["payload"]["assets"])
        elif isinstance(ev.get("assets"), list):
            payload["assets"] = copy.deepcopy(ev["assets"])

        return {"metadata": meta, "payload": payload}

    def _make_output(
        self, result: Any, orig: Dict[str, Any], step_start: float
    ) -> Dict[str, Any]:
        now = time.time()
        data = result if isinstance(result, dict) else {"value": result}

        # strip external-job fields
        ext_id = data.pop("externalJobId", "")
        ext_st = data.pop("externalJobStatus", "")
        ext_rs = data.pop("externalJobResult", "")
        if not ext_id:
            ext_id = orig.get("metadata", {}).get("externalJobId", "")

        prev_meta = orig.get("metadata", {})
        meta = {
            "service": self.service,
            "stepName": self.step_name,
            "stepStatus": "Completed",
            "stepResult": "Success",
            "pipelineTraceId": prev_meta.get("pipelineTraceId", str(uuid.uuid4())),
            "stepExecutionStartTime": prev_meta.get("stepExecutionStartTime", step_start),
            "stepExecutionEndTime": now,
            "stepExecutionDuration": round(now - step_start, 3),
            "pipelineExecutionStartTime": orig.get("pipelineExecutionStartTime", ""),
            "pipelineExecutionEndTime": now if self.is_last else "",
            "pipelineName": self.pipe_name,
            "pipelineStatus": (
                "Started" if self.is_first else ("Completed" if self.is_last else "InProgress")
            ),
            "pipelineId": orig.get("pipelineId", ""),
            "pipelineExecutionId": orig.get("pipelineExecutionId", ""),
            "externalJobResult": ext_rs,
            "externalJobId": ext_id,
            "externalJobStatus": ext_st,
            "stepExternalPayload": "False",
            "stepExternalPayloadLocation": {},
        }

        # if handler returned updatedAsset, use that alone
        if isinstance(result, dict) and "updatedAsset" in result:
            assets = [copy.deepcopy(result.pop("updatedAsset"))]
        else:
            # otherwise aggregate from orig
            asset = (
                orig.get("input", {}).get("detail")
                if isinstance(orig, dict) and "input" in orig
                else orig.get("detail") if isinstance(orig, dict)
                else orig
            )
            prev_assets = []
            if isinstance(orig, dict):
                if (
                    isinstance(orig.get("payload"), dict)
                    and isinstance(orig["payload"].get("assets"), list)
                ):
                    prev_assets = copy.deepcopy(orig["payload"]["assets"])
                elif isinstance(orig.get("assets"), list):
                    prev_assets = copy.deepcopy(orig["assets"])
            assets = prev_assets + ([copy.deepcopy(asset)] if asset else [])

        payload = {"data": data, "assets": assets}

        # off-load if too big
        raw = json.dumps(payload).encode()
        if len(raw) > self.max_response_size:
            key = f"{meta['pipelineExecutionId'] or 'unknown'}/{uuid.uuid4()}-payload.json"
            self.s3.put_object(Bucket=self.external_payload_bucket, Key=key, Body=raw)
            meta["stepExternalPayload"] = "True"
            meta["stepExternalPayloadLocation"] = {"bucket": self.external_payload_bucket, "key": key}
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
                        time.sleep(min(2 ** retries, 30))
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
