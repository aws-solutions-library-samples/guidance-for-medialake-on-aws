"""
Bulk Download – Assess Scale  ●  Optimised (no LARGE_JOB_THRESHOLD_MB)

 * Retrieves asset metadata (parallel BatchGetItem, up to 100 keys/request)
 * Computes total size & file mix
 * Decides job type: SMALL | LARGE_INDIVIDUAL | MIXED | SINGLE_FILE
 * Updates the job item
 * Emits metrics & structured logs (Powertools)
"""

from __future__ import annotations

import os, json, random, time
from datetime import datetime
from typing import Any, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext


# ─── Powertools ────────────────────────────────────────────────────────────────
logger   = Logger(service="bulk-download-assess-scale")
tracer   = Tracer(service="bulk-download-assess-scale")
metrics  = Metrics(namespace="BulkDownloadService",
                   service="bulk-download-assess-scale")

# ─── AWS resources ─────────────────────────────────────────────────────────────
dynamodb            = boto3.resource("dynamodb")
bulk_download_table = dynamodb.Table(os.environ["BULK_DOWNLOAD_TABLE"])
asset_table_name    = os.environ["ASSET_TABLE"]

dynamo_client       = dynamodb.meta.client             # single client, thread-safe

# ─── Configuration ─────────────────────────────────────────────────────────────
SMALL_FILE_THRESHOLD_MB    = int(os.getenv("SMALL_FILE_THRESHOLD_MB", "1024"))
SMALL_FILE_THRESHOLD_BYTES = SMALL_FILE_THRESHOLD_MB * 1024 * 1024
SINGLE_FILE_CHECK          = os.getenv("SINGLE_FILE_CHECK", "false").lower() == "true"

MAX_BATCH_SIZE = 100                                   # DynamoDB hard limit
MAX_WORKERS    = int(os.getenv("PARALLEL_BATCH_WORKERS", "4"))

MB = 1024 * 1024

# ─── Helpers ───────────────────────────────────────────────────────────────────
def _extract_file_size(asset: Dict[str, Any]) -> int:
    return (
        asset.get("DigitalSourceAsset", {})
             .get("MainRepresentation", {})
             .get("StorageInfo", {})
             .get("PrimaryLocation", {})
             .get("FileInfo", {})
             .get("Size", 0)
    )

@tracer.capture_method
def get_job(job_id: str) -> Dict[str, Any]:
    resp = bulk_download_table.get_item(Key={"jobId": job_id}, ConsistentRead=True)
    if "Item" not in resp:
        raise KeyError(f"Job {job_id} not found")
    return resp["Item"]

@tracer.capture_method
def fetch_assets(asset_ids: List[str]) -> List[Dict[str, Any]]:
    """Batch-read asset records in parallel and return the items found."""
    def _one_batch(keys: List[str]) -> List[Dict[str, Any]]:
        request_items = {asset_table_name: {"Keys": [{"InventoryID": k} for k in keys]}}
        retries, max_retries = 0, 4
        items: List[Dict[str, Any]] = []
        unprocessed: Dict[str, Any] | None = None

        while True:
            res = dynamo_client.batch_get_item(
                RequestItems=request_items if unprocessed is None else unprocessed
            )
            items.extend(res.get("Responses", {}).get(asset_table_name, []))
            unprocessed = res.get("UnprocessedKeys")
            if not unprocessed or retries >= max_retries:
                break
            retries += 1
            time.sleep((2 ** retries + random.random()) * 0.1)  # back-off with jitter
        if unprocessed:
            logger.warning(
                "Unprocessed keys after retries",
                extra={"count": len(unprocessed[asset_table_name]["Keys"])}
            )
        return items

    batches = [asset_ids[i:i + MAX_BATCH_SIZE] for i in range(0, len(asset_ids), MAX_BATCH_SIZE)]
    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(batches))) as pool:
        for f in as_completed(pool.submit(_one_batch, b) for b in batches):
            results.extend(f.result())

    return results

def classify_job(total_bytes: int, small_cnt: int, large_cnt: int) -> str:
    """Return jobType string based on file mix."""
    file_count = small_cnt + large_cnt
    if file_count == 1:
        return "SINGLE_FILE" if SINGLE_FILE_CHECK else (
            "SMALL" if large_cnt == 0 else "LARGE_INDIVIDUAL"
        )
    if large_cnt == 0:
        return "SMALL"
    if small_cnt == 0:
        return "LARGE_INDIVIDUAL"
    return "MIXED" if small_cnt > 1 else "LARGE_INDIVIDUAL"

@tracer.capture_method
def compute_sizes(assets: List[Dict[str, Any]]) -> Tuple[int, int, int]:
    total = small = large = 0
    for a in assets:
        sz = _extract_file_size(a)
        total += sz
        if sz <= SMALL_FILE_THRESHOLD_BYTES:
            small += 1
        else:
            large += 1
    return total, small, large

@tracer.capture_method
def update_job(job_id: str,
               total: int,
               small: int,
               large: int,
               job_type: str,
               found: List[str],
               missing: List[str]) -> None:
    try:
        bulk_download_table.update_item(
            Key={"jobId": job_id},
            UpdateExpression="""
                SET #s = :st, #ts = :sz, #sc = :sc, #lc = :lc,
                    #jt = :jt, #fa = :fa, #ma = :ma, #u = :u
            """,
            ExpressionAttributeNames={
                "#s": "status", "#ts": "totalSize", "#sc": "smallFilesCount",
                "#lc": "largeFilesCount", "#jt": "jobType",
                "#fa": "foundAssets", "#ma": "missingAssets", "#u": "updatedAt"
            },
            ExpressionAttributeValues={
                ":st": "ASSESSED", ":sz": total, ":sc": small, ":lc": large,
                ":jt": job_type, ":fa": found, ":ma": missing,
                ":u": datetime.utcnow().isoformat()
            }
        )
    except ClientError as e:
        logger.error("Failed updating job", extra={"jobId": job_id, "err": str(e)})
        raise

# ─── Lambda entrypoint ─────────────────────────────────────────────────────────
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    job_id = event.get("jobId")
    if not job_id:
        raise ValueError("event missing jobId")

    logger.info("Assessing bulk download", extra={"jobId": job_id})

    try:
        job    = get_job(job_id)
        ids    = job.get("assetIds", [])
        assets = fetch_assets(ids)

        found_ids    = [a["InventoryID"] for a in assets]
        missing_ids  = [x for x in ids if x not in found_ids]

        total, small_cnt, large_cnt = compute_sizes(assets)
        job_type = classify_job(total, small_cnt, large_cnt)

        update_job(job_id, total, small_cnt, large_cnt, job_type, found_ids, missing_ids)

        metrics.add_metric("JobsAssessed", MetricUnit.Count, 1)
        metrics.add_metric("TotalDownloadSize", MetricUnit.Megabytes, total / MB)

        # Build per-file payloads only when needed
        small_files, large_files = [], []
        if job_type not in ("SINGLE_FILE", "LARGE_INDIVIDUAL"):
            for a in assets:
                target = (
                    small_files
                    if _extract_file_size(a) <= SMALL_FILE_THRESHOLD_BYTES
                    else large_files
                )
                target.append({
                    "jobId":   job_id,
                    "userId":  job.get("userId"),
                    "assetId": a["InventoryID"],
                    "options": job.get("options", {})
                })

        return {
            "jobId": job_id,
            "userId": job.get("userId"),
            "jobType": job_type,
            "totalSize": total,
            "smallFilesCount": small_cnt,
            "largeFilesCount": large_cnt,
            "foundAssets": found_ids,
            "missingAssets": missing_ids,
            "options": job.get("options", {}),
            "smallFiles": small_files,
            "largeFiles": large_files,
        }

    except Exception as e:
        logger.exception("Assessment failed", extra={"jobId": job_id})
        metrics.add_metric("JobAssessmentErrors", MetricUnit.Count, 1)

        # best-effort status update
        try:
            bulk_download_table.update_item(
                Key={"jobId": job_id},
                UpdateExpression="SET #s = :st, #e = :err, #u = :u",
                ExpressionAttributeNames={"#s": "status", "#e": "error", "#u": "updatedAt"},
                ExpressionAttributeValues={
                    ":st": "FAILED",
                    ":err": f"{type(e).__name__}: {e}",
                    ":u": datetime.utcnow().isoformat()
                }
            )
        except Exception as inner:
            logger.error("Secondary update failed", extra={"inner": str(inner)})

        raise
