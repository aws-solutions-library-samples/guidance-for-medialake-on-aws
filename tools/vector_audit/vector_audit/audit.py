"""Core S3 Vectors filterability audit logic.

The bug this checks for: vectors written into a freshly-created S3 Vectors index
under concurrent bulk load can have their ``embedding_option`` metadata silently
registered as non-filterable. When that happens a semantic-search filter of
``embedding_option = visual`` returns nothing for the affected asset, so it never
ranks. This module verifies, per asset, that such a filter returns at least one
hit (the binary PASS signal).
"""

from __future__ import annotations

import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# query-vectors caps results per call; also our filterable lower bound.
QUERY_CAP = 100

_ASSET_RE = re.compile(r"(asset:uuid:[0-9a-f-]+)")
_OPTIONS = ("visual", "audio", "transcription", "image")


@dataclass
class AssetCounts:
    """Per-asset clip counts by embedding type (from vector keys)."""

    inventory_id: str
    visual: int = 0
    audio: int = 0
    transcription: int = 0
    total: int = 0


@dataclass
class AssetResult:
    """Filterability outcome for one asset."""

    inventory_id: str
    counts: AssetCounts
    filterable: int | None  # None when not probed (no visual clips)
    probe_seconds: float | None
    verdict: str  # ok | BROKEN | ERROR | no-visual | NO-VECTORS
    name: str | None = None


def make_client(profile: str | None, region: str):
    """Return an s3vectors client with adaptive retries for throttling."""
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    config = Config(retries={"max_attempts": 6, "mode": "adaptive"})
    return session.client("s3vectors", region_name=region, config=config)


def make_dynamodb(profile: str | None, region: str):
    """Return a DynamoDB client (used only for --names)."""
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    return session.client("dynamodb", region_name=region)


def region_from_bucket(bucket: str) -> str | None:
    """Infer the AWS region from a bucket name.

    Bucket pattern: ``<prefix>-vectors-<account>-<region>-<env>``.
    """
    match = re.search(r"-vectors-\d+-([a-z]+-[a-z]+-\d+)-", bucket)
    return match.group(1) if match else None


def asset_table_from_bucket(bucket: str) -> str | None:
    """Infer the asset DynamoDB table name from a bucket name."""
    match = re.match(r"(.+)-vectors-\d+-[a-z]+-[a-z]+-\d+-(.+)$", bucket)
    if not match:
        return None
    return f"{match.group(1)}-asset-table-{match.group(2)}"


def _key_type(key: str) -> str:
    """Classify a vector key by its embedding type token."""
    for opt in _OPTIONS:
        if f"_{opt}_" in key or key.endswith(f"_{opt}"):
            return "visual" if opt == "image" else opt
    return "other"


def collect_counts(client, bucket: str, index: str) -> tuple[int, dict]:
    """Page through all vectors and tally per-asset clip counts by type.

    Returns ``(total_vectors, {inventory_id: AssetCounts})``.
    """
    counts: dict[str, AssetCounts] = {}
    total = 0
    paginator = client.get_paginator("list_vectors")
    for page in paginator.paginate(
        vectorBucketName=bucket, indexName=index
    ):
        for vector in page.get("vectors", []):
            key = vector["key"]
            match = _ASSET_RE.match(key)
            if match is None:
                continue
            total += 1
            inv = match.group(1)
            entry = counts.setdefault(inv, AssetCounts(inventory_id=inv))
            kind = _key_type(key)
            if kind == "visual":
                entry.visual += 1
            elif kind == "audio":
                entry.audio += 1
            elif kind == "transcription":
                entry.transcription += 1
            entry.total += 1
    return total, counts


def _random_query_vector(dimension: int = 512) -> list[float]:
    """A random unit-ish query vector; filter + topK returns matches."""
    return [round(random.uniform(-1, 1), 6) for _ in range(dimension)]


def probe_filterable(
    client, bucket: str, index: str, inventory_id: str, query_vector: list
) -> int | None:
    """Count visual clips returned by an ``embedding_option=visual`` filter.

    Returns the count (<= QUERY_CAP), or ``None`` on an API error after retries.
    A non-filterable (buggy) asset returns exactly ``0``.
    """
    try:
        response = client.query_vectors(
            vectorBucketName=bucket,
            indexName=index,
            queryVector={"float32": query_vector},
            topK=QUERY_CAP,
            filter={
                "$and": [
                    {"inventory_id": {"$eq": inventory_id}},
                    {"embedding_option": {"$eq": "visual"}},
                ]
            },
        )
    except ClientError:
        return None
    return len(response.get("vectors", []))


def lookup_name(dynamodb, table: str, inventory_id: str) -> str | None:
    """Return the asset's object-key filename, or None if unavailable."""
    try:
        item = dynamodb.get_item(
            TableName=table,
            Key={"InventoryID": {"S": inventory_id}},
        ).get("Item")
    except ClientError:
        return None
    if not item:
        return None
    try:
        return (
            item["DigitalSourceAsset"]["M"]["MainRepresentation"]["M"][
                "StorageInfo"
            ]["M"]["PrimaryLocation"]["M"]["ObjectKey"]["M"]["Name"]["S"]
        )
    except (KeyError, TypeError):
        return None


def audit_asset(
    client, bucket: str, index: str, counts: AssetCounts, query_vector: list
) -> AssetResult:
    """Probe one asset and classify its filterability."""
    if counts.visual == 0:
        return AssetResult(
            inventory_id=counts.inventory_id,
            counts=counts,
            filterable=None,
            probe_seconds=None,
            verdict="no-visual",
        )
    start = time.monotonic()
    filterable = probe_filterable(
        client, bucket, index, counts.inventory_id, query_vector
    )
    elapsed = time.monotonic() - start
    if filterable is None:
        verdict = "ERROR"
    elif filterable == 0:
        verdict = "BROKEN"
    else:
        verdict = "ok"
    return AssetResult(
        inventory_id=counts.inventory_id,
        counts=counts,
        filterable=filterable,
        probe_seconds=elapsed,
        verdict=verdict,
    )


def audit_assets(
    client,
    bucket: str,
    index: str,
    asset_counts: list[AssetCounts],
    concurrency: int,
) -> tuple[list[AssetResult], float]:
    """Probe all assets, preserving input order. Returns (results, seconds)."""
    query_vector = _random_query_vector()
    start = time.monotonic()
    if concurrency <= 1:
        results = [
            audit_asset(client, bucket, index, c, query_vector)
            for c in asset_counts
        ]
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            results = list(
                pool.map(
                    lambda c: audit_asset(
                        client, bucket, index, c, query_vector
                    ),
                    asset_counts,
                )
            )
    return results, time.monotonic() - start
