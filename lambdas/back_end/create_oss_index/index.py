#!/usr/bin/env python3
import os
import json
import time
import boto3
from botocore.awsrequest import AWSRequest
from botocore.auth import SigV4Auth
from requests import request, RequestException
from botocore.exceptions import ClientError
from lambda_utils import logger, lambda_handler_decorator

VECTOR_DIMENSION    = 1024         # Twelve-Labs embedding dim
MAX_RETRIES         = 5            # creation retries
POLL_INTERVAL       = 2            # sec between “index gone?” checks
POLL_TIMEOUT        = 60           # sec max to wait for deletion

# --------------------------------------------------------------------------- #
#  low-level helpers
# --------------------------------------------------------------------------- #
def send_signed_request(method: str,
                        url: str,
                        credentials,
                        service: str,
                        region: str,
                        headers: dict | None = None,
                        body: str | None = None):
    """
    Sign & fire an HTTP request to OpenSearch using SigV4.
    Returns the `requests.Response` object.
    """
    headers = headers or {}
    req     = AWSRequest(method=method, url=url, data=body, headers=headers)

    # compute SHA-256 payload hash header (required for SigV4)
    req.headers["X-Amz-Content-SHA256"] = SigV4Auth(
        credentials, service, region
    ).payload(req)

    SigV4Auth(credentials, service, region).add_auth(req)
    prepared = req.prepare()

    logger.debug("Signed request",
                 extra={"method": method, "url": url, "headers": prepared.headers})

    return request(method=prepared.method,
                   url=prepared.url,
                   headers=prepared.headers,
                   data=prepared.body)


def index_exists(host: str,
                 index_name: str,
                 credentials,
                 service: str,
                 region: str) -> bool:
    """HEAD /{index} – returns True if index already exists."""
    url  = f"{host}/{index_name}"
    resp = send_signed_request("HEAD", url, credentials, service, region)
    return resp.status_code == 200


def delete_index(host: str,
                 index_name: str,
                 credentials,
                 service: str,
                 region: str) -> None:
    """DELETE /{index}.  Ignores 404s."""
    url  = f"{host}/{index_name}"
    resp = send_signed_request("DELETE", url, credentials, service, region)
    if resp.status_code not in (200, 404):
        raise Exception(f"Unexpected status deleting index {index_name}: "
                        f"{resp.status_code} – {resp.text}")
    logger.info("Index deleted (or did not exist)",
                extra={"index_name": index_name, "status_code": resp.status_code})


def wait_for_deletion(host: str,
                      index_name: str,
                      credentials,
                      service: str,
                      region: str,
                      timeout=POLL_TIMEOUT,
                      interval=POLL_INTERVAL) -> None:
    """Poll until `HEAD /{index}` returns 404, or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not index_exists(host, index_name, credentials, service, region):
            logger.debug("Index confirmed gone", extra={"index_name": index_name})
            return
        time.sleep(interval)
    raise TimeoutError(f"Index {index_name} still exists after {timeout}s")


# --------------------------------------------------------------------------- #
#  create with retry + delete-then-recreate logic
# --------------------------------------------------------------------------- #
def create_index_with_retry(host,
                            index_name,
                            payload,
                            headers,
                            credentials,
                            service,
                            region,
                            max_retries=MAX_RETRIES) -> bool:
    """
    Create an OpenSearch index.  
    If it already exists, delete & recreate it once;
    otherwise retry (exponential back-off) on transient failures.
    """
    url = f"{host}/{index_name}"
    logger.info("Creating OpenSearch index",
                extra={"url": url, "index_name": index_name})

    # First, if it already exists, drop it.
    if index_exists(host, index_name, credentials, service, region):
        logger.info("Index exists – deleting before recreation",
                    extra={"index_name": index_name})
        delete_index(host, index_name, credentials, service, region)
        wait_for_deletion(host, index_name, credentials, service, region)

    # Now try to create, with retries for transient issues
    body = json.dumps(payload)

    for attempt in range(max_retries):
        try:
            response = send_signed_request("PUT", url, credentials,
                                           service, region,
                                           headers=headers,
                                           body=body)

            if response.status_code == 200:
                logger.info("Index creation successful",
                            extra={"index_name": index_name})
                return True

            logger.error("Failed to create index",
                         extra={"index_name": index_name,
                                "status_code": response.status_code,
                                "body": response.text,
                                "attempt": attempt + 1,
                                "max_retries": max_retries})

        except RequestException as e:
            logger.error("Request error during index creation",
                         extra={"index_name": index_name,
                                "error": str(e),
                                "attempt": attempt + 1,
                                "max_retries": max_retries},
                         exc_info=True)

        # exponential back-off
        backoff = 2 ** attempt
        logger.debug("Retrying after back-off",
                     extra={"index_name": index_name,
                            "seconds": backoff,
                            "attempt": attempt + 1})
        time.sleep(backoff)

    return False

# --------------------------------------------------------------------------- #
#  Lambda entry-point
# --------------------------------------------------------------------------- #
@lambda_handler_decorator(cors=True)
def handler(event, context):
    """
    Custom-resource style Lambda – handles Create / Update / Delete.
    Only “Create” actually builds the indexes.
    """
    logger.info("Received event", extra={"event": event})

    req_type = event.get("RequestType")
    if req_type != "Create":
        logger.info("Skipping non-Create request",
                    extra={"RequestType": req_type})
        return {"statusCode": 200,
                "body": f"Skipped {req_type} request"}

    # -- env
    host         = os.environ["COLLECTION_ENDPOINT"]
    index_names  = os.environ["INDEX_NAMES"]
    region       = os.environ["REGION"]
    service      = os.environ["SCOPE"]          # usually “es”
    credentials  = boto3.Session().get_credentials()

    logger.info("Environment",
                extra={"host": host,
                       "indexes": index_names,
                       "region": region,
                       "service": service})

    headers = {
        "content-type": "application/json",
        "accept": "application/json"
    }

    # -- index template / mappings
    payload = {
        "settings": {
            "index": {
                "knn": True,
                "mapping.total_fields.limit": 6000
            }
        },
        "mappings": {
            "properties": {
                "type":            {"type": "text"},
                "document_id":     {"type": "text"},
                "InventoryID":     {"type": "text"},
                "FileHash":        {"type": "text"},
                "StoragePath":     {"type": "text"},
                "start_timecode":  {"type": "keyword"},
                "end_timecode":    {"type": "keyword"},
                "embedding_scope": {"type": "keyword"},
                "embedding": {
                    "type":      "knn_vector",
                    "dimension": VECTOR_DIMENSION,
                    "method": {
                        "name":       "hnsw",
                        "space_type": "cosinesimil",
                        "engine":     "nmslib"
                    }
                },
                "audio_embedding": {
                    "type":      "knn_vector",
                    "dimension": VECTOR_DIMENSION,
                    "method": {
                        "name":       "hnsw",
                        "space_type": "cosinesimil",
                        "engine":     "nmslib"
                    }
                },
                "DerivedRepresentations": {
                    "type": "nested",
                    "properties": {
                        "Format":  {"type": "text"},
                        "ID":      {"type": "text"},
                        "Purpose": {"type": "text"},
                        "Type":    {"type": "text"},
                        "ImageSpec": {
                            "type": "object",
                            "properties": {
                                "Resolution": {
                                    "properties": {
                                        "Height": {"type": "integer"},
                                        "Width":  {"type": "integer"}
                                    }
                                }
                            }
                        },
                        "StorageInfo": {
                            "type": "object",
                            "properties": {
                                "PrimaryLocation": {
                                    "properties": {
                                        "Bucket":      {"type": "text"},
                                        "Status":      {"type": "text"},
                                        "Provider":    {"type": "text"},
                                        "StorageType": {"type": "text"},
                                        "FileInfo": {
                                            "properties": {
                                                "Size": {"type": "long"}
                                            }
                                        },
                                        "ObjectKey": {
                                            "properties": {
                                                "FullPath": {"type": "text"},
                                                "Name":     {"type": "text"},
                                                "Path":     {"type": "text"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "DigitalSourceAsset": {
                    "type": "object",
                    "properties": {
                        "CreateDate":        {"type": "date"},
                        "ID":                {"type": "keyword"},
                        "IngestedAt":        {"type": "date"},
                        "lastModifiedDate":  {"type": "date"},
                        "originalIngestDate":{"type": "date"},
                        "Type":              {"type": "text"},
                        "MainRepresentation": {
                            "type": "object",
                            "properties": {
                                "Format": {"type": "text"},
                                "ID":     {"type": "text"},
                                "Purpose":{"type": "text"},
                                "Type":   {"type": "text"},
                                "StorageInfo": {
                                    "type": "object",
                                    "properties": {
                                        "PrimaryLocation": {
                                            "properties": {
                                                "Bucket":      {"type": "text"},
                                                "Status":      {"type": "text"},
                                                "StorageType": {"type": "text"},
                                                "FileInfo": {
                                                    "properties": {
                                                        "CreateDate": {"type": "date"},
                                                        "Size":       {"type": "long"},
                                                        "Hash": {
                                                            "properties": {
                                                                "Algorithm": {"type": "keyword"},
                                                                "MD5Hash":   {"type": "keyword"},
                                                                "Value":     {"type": "keyword"}
                                                            }
                                                        }
                                                    }
                                                },
                                                "ObjectKey": {
                                                    "properties": {
                                                        "FullPath": {"type": "text"},
                                                        "Name":     {"type": "text"},
                                                        "Path":     {"type": "text"}
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "Metadata": {
                    "type":   "object",
                    "dynamic": True,
                    "properties": {
                        "CustomMetadata": {
                            "type":   "object",
                            "dynamic": True
                        }
                    }
                },
                "DigitalAsset": {
                    "type": "nested",
                    "properties": {
                        "asset_id":        {"type": "keyword"},
                        "start_timecode":  {"type": "keyword"},
                        "end_timecode":    {"type": "keyword"},
                        "embedding_scope": {"type": "keyword"},
                        "embedding": {
                            "type":      "knn_vector",
                            "dimension": VECTOR_DIMENSION,
                            "method": {
                                "name":       "hnsw",
                                "space_type": "cosinesimil",
                                "engine":     "nmslib"
                            }
                        },
                        "audio_embedding": {
                            "type":      "knn_vector",
                            "dimension": VECTOR_DIMENSION,
                            "method": {
                                "name":       "hnsw",
                                "space_type": "cosinesimil",
                                "engine":     "nmslib"
                            }
                        },
                        "EmbeddedMetadata": {"type": "object", "dynamic": True}
                    }
                }
            }
        }
    }

    # -- create (or recreate) each index
    failures = []
    for index_name in index_names.split(","):
        logger.info("Processing index", extra={"index_name": index_name})
        ok = create_index_with_retry(host, index_name.strip(), payload, headers,
                                     credentials, service, region)
        if not ok:
            failures.append(index_name)

    if failures:
        msg = f"Failed to create indexes: {', '.join(failures)}"
        logger.error(msg)
        raise Exception(msg)

    logger.info("All indexes created successfully")
    return {"statusCode": 200, "body": "All indexes created successfully"}
