"""
URL Utilities for MediaLake Lambda Functions

This module provides utilities for generating URLs for S3 objects, including:
1. CloudFront URL generation for public access
2. Presigned URL generation for secure access
3. Batch URL generation for performance optimization

Usage:
    from url_utils import generate_cloudfront_url, generate_cloudfront_urls_batch

    # Generate single CloudFront URL
    url = generate_cloudfront_url("my-bucket", "path/to/file.jpg")

    # Generate multiple CloudFront URLs
    requests = [
        {"bucket": "bucket1", "key": "file1.jpg", "request_id": "req1"},
        {"bucket": "bucket2", "key": "file2.jpg", "request_id": "req2"}
    ]
    urls = generate_cloudfront_urls_batch(requests)
"""

import os
import re
from typing import Dict, List, Optional
from urllib.parse import quote

import boto3
from aws_lambda_powertools import Logger
from botocore.config import Config

logger = Logger(service="url-utils")

# Signature style & virtual-host addressing are required for every region
_SIGV4_CFG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "virtual"},
)

_ENDPOINT_TMPL = "https://s3.{region}.amazonaws.com"
_S3_CLIENT_CACHE: Dict[str, boto3.client] = {}  # {region → client}
_CLOUDFRONT_DOMAIN_CACHE: Optional[str] = None
_SSM_CLIENT: Optional[boto3.client] = None


def _get_ssm_client() -> boto3.client:
    """Return a cached SSM client."""
    global _SSM_CLIENT
    if _SSM_CLIENT is None:
        _SSM_CLIENT = boto3.client("ssm")
    return _SSM_CLIENT


def _get_s3_client_for_bucket(bucket: str) -> boto3.client:
    """
    Return an S3 client **pinned to the bucket's actual region**.
    Clients are cached to reuse TCP connections across warm invocations.
    """
    generic = _S3_CLIENT_CACHE.setdefault(
        "us-east-1",
        boto3.client("s3", region_name="us-east-1", config=_SIGV4_CFG),
    )

    try:
        region = (
            generic.get_bucket_location(Bucket=bucket).get("LocationConstraint")
            or "us-east-1"
        )
    except generic.exceptions.NoSuchBucket:
        raise ValueError(f"S3 bucket {bucket!r} does not exist")

    if region not in _S3_CLIENT_CACHE:
        _S3_CLIENT_CACHE[region] = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=_ENDPOINT_TMPL.format(region=region),
            config=_SIGV4_CFG,
        )
    return _S3_CLIENT_CACHE[region]


def _get_cloudfront_domain() -> str:
    """
    Retrieve CloudFront domain from SSM parameter with caching.
    Returns the domain string for CloudFront URL generation.
    """
    global _CLOUDFRONT_DOMAIN_CACHE

    if _CLOUDFRONT_DOMAIN_CACHE is not None:
        return _CLOUDFRONT_DOMAIN_CACHE

    try:
        # Use CLOUDFRONT_DOMAIN_SSM_PARAM env var if set (preferred), otherwise fall back to convention
        ssm_parameter_name = os.environ.get("CLOUDFRONT_DOMAIN_SSM_PARAM")
        if not ssm_parameter_name:
            environment = os.environ.get("ENVIRONMENT", "dev")
            ssm_prefix = os.environ.get("SSM_PREFIX", f"/medialake/{environment}")
            ssm_parameter_name = f"{ssm_prefix}/cloudfront-distribution-domain"

        ssm_client = _get_ssm_client()
        response = ssm_client.get_parameter(
            Name=ssm_parameter_name, WithDecryption=True
        )
        raw = response["Parameter"]["Value"].strip()

        # Sanitize domain by removing scheme prefix and trailing slashes
        domain = re.sub(r"^https?://", "", raw)
        domain = domain.rstrip("/")

        _CLOUDFRONT_DOMAIN_CACHE = domain
        return domain
    except Exception as e:
        logger.error(f"Error retrieving CloudFront domain from SSM: {str(e)}")
        raise


def generate_presigned_url(
    bucket: str, key: str, expiration: int = 3600
) -> Optional[str]:
    """
    Generate a presigned URL for an S3 object with region-aware client.
    The URL is signed in the bucket's own region, preventing
    SignatureDoesNotMatch errors outside us-east-1.
    """
    try:
        # Use region-aware S3 client
        s3_client = _get_s3_client_for_bucket(bucket)
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ResponseContentDisposition": "inline",
            },
            ExpiresIn=expiration,
        )

        logger.debug(
            "Generated presigned URL for s3://%s/%s (region %s)",
            bucket,
            key,
            s3_client.meta.region_name,
        )

        return url
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        return None


def generate_cloudfront_url(bucket: str, key: str) -> Optional[str]:
    """
    Generate a CloudFront URL for an S3 object.
    Format: https://{cloudfront_domain}/media/{bucket}/{key}
    """
    try:
        cloudfront_domain = _get_cloudfront_domain()

        # Strip leading slash from key if present
        clean_key = key.lstrip("/")

        # URL-encode bucket and key, preserving slashes in key
        encoded_bucket = quote(bucket, safe="")
        encoded_key = quote(clean_key, safe="/")

        return f"https://{cloudfront_domain}/media/{encoded_bucket}/{encoded_key}"
    except Exception as e:
        logger.error(
            f"Error generating CloudFront URL for s3://{bucket}/{key}: {str(e)}"
        )
        return None


def generate_cloudfront_urls_batch(
    url_requests: List[Dict[str, str]],
) -> Dict[str, Optional[str]]:
    """
    Generate multiple CloudFront URLs for better performance.

    Args:
        url_requests: List of dicts with 'bucket', 'key', and 'request_id' keys

    Returns:
        Dict mapping request_id to CloudFront URL (or None if failed)
    """
    # Prefetch CloudFront domain once for all URLs
    try:
        cloudfront_domain = _get_cloudfront_domain()
    except Exception:
        return {request["request_id"]: None for request in url_requests}

    results = {}
    for request in url_requests:
        try:
            clean_key = request["key"].lstrip("/")
            encoded_bucket = quote(request["bucket"], safe="")
            encoded_key = quote(clean_key, safe="/")
            results[request["request_id"]] = (
                f"https://{cloudfront_domain}/media/{encoded_bucket}/{encoded_key}"
            )
        except Exception:
            results[request["request_id"]] = None

    return results


def generate_presigned_urls_batch(
    url_requests: List[Dict[str, str]], expiration: int = 3600
) -> Dict[str, Optional[str]]:
    """
    Generate multiple presigned URLs in parallel for better performance.

    Args:
        url_requests: List of dicts with 'bucket', 'key', and 'request_id' keys
        expiration: URL expiration time in seconds

    Returns:
        Dict mapping request_id to presigned URL (or None if failed)
    """
    import concurrent.futures
    import time

    start_time = time.time()
    logger.info(
        f"[PERF] Starting batch presigned URL generation for {len(url_requests)} URLs"
    )

    def generate_single_url(request):
        try:
            return {
                "request_id": request["request_id"],
                "url": generate_presigned_url(
                    request["bucket"], request["key"], expiration
                ),
            }
        except Exception as e:
            logger.warning(
                f"Failed to generate presigned URL for {request['request_id']}: {str(e)}"
            )
            return {"request_id": request["request_id"], "url": None}

    results = {}

    # Use ThreadPoolExecutor for I/O-bound operations
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_request = {
            executor.submit(generate_single_url, request): request
            for request in url_requests
        }

        for future in concurrent.futures.as_completed(future_to_request):
            try:
                result = future.result()
                results[result["request_id"]] = result["url"]
            except Exception as e:
                request = future_to_request[future]
                logger.warning(
                    f"Exception generating presigned URL for {request['request_id']}: {str(e)}"
                )
                results[request["request_id"]] = None

    batch_time = time.time() - start_time
    logger.info(f"[PERF] Batch presigned URL generation completed in {batch_time:.3f}s")

    return results
