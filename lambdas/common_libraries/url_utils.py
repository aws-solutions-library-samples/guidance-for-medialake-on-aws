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
        logger.info(
            f"[URL_DEBUG] Using cached CloudFront domain: '{_CLOUDFRONT_DOMAIN_CACHE}'"
        )
        return _CLOUDFRONT_DOMAIN_CACHE

    try:
        # Get environment from environment variable or default to 'dev'
        environment = os.environ.get("ENVIRONMENT", "dev")
        ssm_parameter_name = f"/medialake/{environment}/cloudfront-distribution-domain"

        logger.info(
            f"[URL_DEBUG] Retrieving CloudFront domain from SSM parameter: {ssm_parameter_name}"
        )
        ssm_client = boto3.client("ssm")
        response = ssm_client.get_parameter(
            Name=ssm_parameter_name, WithDecryption=True
        )
        raw = response["Parameter"]["Value"].strip()
        logger.info(f"[URL_DEBUG] Raw SSM parameter value: '{raw}'")

        # Sanitize domain by removing scheme prefix and trailing slashes
        domain = re.sub(r"^https?://", "", raw)
        domain = domain.rstrip("/")
        logger.info(f"[URL_DEBUG] Sanitized domain: '{domain}'")

        _CLOUDFRONT_DOMAIN_CACHE = domain
        logger.info(f"[URL_DEBUG] Cached CloudFront domain: '{domain}'")
        return domain
    except Exception as e:
        logger.error(
            f"[URL_DEBUG] Error retrieving CloudFront domain from SSM: {str(e)}"
        )
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
        logger.info(
            f"[URL_DEBUG] Generating CloudFront URL for bucket: '{bucket}', key: '{key}'"
        )

        cloudfront_domain = _get_cloudfront_domain()
        logger.info(f"[URL_DEBUG] Retrieved CloudFront domain: '{cloudfront_domain}'")

        # Strip leading slash from key if present
        clean_key = key.lstrip("/")
        logger.info(f"[URL_DEBUG] Cleaned key: '{clean_key}'")

        # URL-encode bucket and key, preserving slashes in key
        encoded_bucket = quote(bucket, safe="")
        encoded_key = quote(clean_key, safe="/")
        logger.info(
            f"[URL_DEBUG] Encoded bucket: '{encoded_bucket}', encoded key: '{encoded_key}'"
        )

        url = f"https://{cloudfront_domain}/media/{encoded_bucket}/{encoded_key}"
        logger.info(f"[URL_DEBUG] Generated CloudFront URL: '{url}'")

        return url
    except Exception as e:
        logger.error(
            f"[URL_DEBUG] Error generating CloudFront URL for s3://{bucket}/{key}: {str(e)}"
        )
        return None


def generate_cloudfront_urls_batch(
    url_requests: List[Dict[str, str]],
) -> Dict[str, Optional[str]]:
    """
    Generate multiple CloudFront URLs in parallel for better performance.

    Args:
        url_requests: List of dicts with 'bucket', 'key', and 'request_id' keys

    Returns:
        Dict mapping request_id to CloudFront URL (or None if failed)
    """
    import concurrent.futures
    import time

    start_time = time.time()
    logger.info(
        f"[URL_DEBUG] Starting batch CloudFront URL generation for {len(url_requests)} URLs"
    )
    logger.info(f"[URL_DEBUG] URL requests: {url_requests}")

    # Prefetch CloudFront domain to prevent thundering herd on SSM
    try:
        cloudfront_domain = _get_cloudfront_domain()
        logger.info(
            f"[URL_DEBUG] Successfully prefetched CloudFront domain: '{cloudfront_domain}'"
        )
    except Exception as e:
        logger.error(f"[URL_DEBUG] Failed to prefetch CloudFront domain: {str(e)}")
        # Return all failed results
        return {request["request_id"]: None for request in url_requests}

    def generate_single_url(request):
        try:
            logger.info(f"[URL_DEBUG] Processing single URL request: {request}")

            # Strip leading slash from key if present
            clean_key = request["key"].lstrip("/")
            logger.info(
                f"[URL_DEBUG] Cleaned key for {request['request_id']}: '{clean_key}'"
            )

            # URL-encode bucket and key, preserving slashes in key
            encoded_bucket = quote(request["bucket"], safe="")
            encoded_key = quote(clean_key, safe="/")
            logger.info(
                f"[URL_DEBUG] Encoded for {request['request_id']} - bucket: '{encoded_bucket}', key: '{encoded_key}'"
            )

            url = f"https://{cloudfront_domain}/media/{encoded_bucket}/{encoded_key}"
            logger.info(
                f"[URL_DEBUG] Generated URL for {request['request_id']}: '{url}'"
            )

            return {
                "request_id": request["request_id"],
                "url": url,
            }
        except Exception as e:
            logger.warning(
                f"[URL_DEBUG] Failed to generate CloudFront URL for {request['request_id']}: {str(e)}"
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
                logger.info(
                    f"[URL_DEBUG] Collected result for {result['request_id']}: {result['url']}"
                )
            except Exception as e:
                request = future_to_request[future]
                logger.warning(
                    f"[URL_DEBUG] Exception generating CloudFront URL for {request['request_id']}: {str(e)}"
                )
                results[request["request_id"]] = None

    batch_time = time.time() - start_time
    logger.info(
        f"[URL_DEBUG] Batch CloudFront URL generation completed in {batch_time:.3f}s"
    )
    logger.info(f"[URL_DEBUG] Final results: {results}")

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
