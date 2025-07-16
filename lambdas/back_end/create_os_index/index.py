import json
import os
import time

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from lambda_utils import lambda_handler_decorator, logger
from requests import request

VECTOR_DIMENSION = 1024  # Twelve Labs embeddings dimension


def index_exists(
    host: str, index_name: str, credentials, service: str, region: str
) -> bool:
    """
    HEAD /{index} – returns True if index already exists.
    """
    url = f"{host}/{index_name}"
    req = AWSRequest(method="HEAD", url=url, headers={})
    # required for SigV4
    req.headers["X-Amz-Content-SHA256"] = SigV4Auth(
        credentials, service, region
    ).payload(req)
    SigV4Auth(credentials, service, region).add_auth(req)
    prepared = req.prepare()

    logger.info(
        "Checking if index exists",
        extra={"method": prepared.method, "url": prepared.url},
    )
    resp = request(
        method=prepared.method,
        url=prepared.url,
        headers=prepared.headers,
        data=prepared.body,
    )
    return resp.status_code == 200


def delete_index(
    host: str, index_name: str, credentials, service: str, region: str
) -> None:
    """
    DELETE /{index}.  Ignores 404s.
    """
    url = f"{host}/{index_name}"
    req = AWSRequest(method="DELETE", url=url, headers={})
    req.headers["X-Amz-Content-SHA256"] = SigV4Auth(
        credentials, service, region
    ).payload(req)
    SigV4Auth(credentials, service, region).add_auth(req)
    prepared = req.prepare()

    resp = request(
        method=prepared.method,
        url=prepared.url,
        headers=prepared.headers,
        data=prepared.body,
    )
    if resp.status_code not in (200, 404):
        raise Exception(
            f"Unexpected status deleting index {index_name}: "
            f"{resp.status_code} – {resp.text}"
        )
    logger.info(
        "Index deleted (or did not exist)",
        extra={"index_name": index_name, "status_code": resp.status_code},
    )


def wait_for_deletion(
    host: str,
    index_name: str,
    credentials,
    service: str,
    region: str,
    timeout: int = 60,
    interval: int = 2,
) -> None:
    """
    Poll until HEAD /{index} returns 404, or timeout expires.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not index_exists(host, index_name, credentials, service, region):
            logger.info("Index confirmed gone", extra={"index_name": index_name})
            return
        time.sleep(interval)
    raise TimeoutError(f"Index {index_name} still exists after {timeout}s")


def create_index_with_retry(
    host, index_name, payload, headers, credentials, service, region, max_retries=5
):
    """
    Create an OpenSearch index with retry logic and exponential backoff.
    If the index already exists, delete it and wait for deletion before creating.
    """
    # If it already exists, drop & recreate
    if index_exists(host, index_name, credentials, service, region):
        logger.info(
            "Index exists – deleting before recreation",
            extra={"index_name": index_name},
        )
        delete_index(host, index_name, credentials, service, region)
        wait_for_deletion(host, index_name, credentials, service, region)

    url = f"{host}/{index_name}"
    logger.info(
        "Creating OpenSearch index", extra={"url": url, "index_name": index_name}
    )

    for attempt in range(max_retries):
        try:
            req = AWSRequest(
                method="PUT", url=url, data=json.dumps(payload), headers=headers
            )
            req.headers["X-Amz-Content-SHA256"] = SigV4Auth(
                credentials, service, region
            ).payload(req)
            SigV4Auth(credentials, service, region).add_auth(req)
            prepared = req.prepare()

            logger.info(
                "Sending request to OpenSearch",
                extra={
                    "method": prepared.method,
                    "url": prepared.url,
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                },
            )

            response = request(
                method=prepared.method,
                url=prepared.url,
                headers=prepared.headers,
                data=prepared.body,
            )

            if response.status_code == 200:
                logger.info(
                    "Index creation successful",
                    extra={
                        "index_name": index_name,
                        "status_code": response.status_code,
                        "response": response.text,
                    },
                )
                return True
            else:
                # If it somehow reappeared in the meantime
                error = (
                    response.json()
                    .get("error", {})
                    .get("root_cause", [{}])[0]
                    .get("type")
                )
                if error == "resource_already_exists_exception":
                    logger.info(
                        "Index already exists",
                        extra={
                            "index_name": index_name,
                            "status_code": response.status_code,
                        },
                    )
                    return True

                logger.error(
                    "Failed to create OpenSearch index",
                    extra={
                        "index_name": index_name,
                        "status_code": response.status_code,
                        "response": response.text,
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                    },
                )

        except Exception as e:
            logger.error(
                "Error creating OpenSearch index",
                extra={
                    "index_name": index_name,
                    "error": str(e),
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                },
                exc_info=True,
            )

        # Exponential backoff
        backoff_time = 2**attempt
        logger.info(
            "Retrying index creation after backoff",
            extra={
                "index_name": index_name,
                "attempt": attempt + 1,
                "max_retries": max_retries,
                "backoff_seconds": backoff_time,
            },
        )
        time.sleep(backoff_time)

    return False


@lambda_handler_decorator(cors=True)
def handler(event, context):
    """
    Lambda handler for creating OpenSearch indexes

    Args:
        event: Lambda event
        context: Lambda context

    Returns:
        dict: Response indicating success or failure
    """
    logger.info("Received event", extra={"event": event})

    req_type = event.get("RequestType")
    if req_type != "Create":
        logger.info("Skipping non-Create request", extra={"RequestType": req_type})
        return {"statusCode": 200, "body": f"Skipped {req_type} request"}

    host = os.environ["COLLECTION_ENDPOINT"]
    index_names = os.environ["INDEX_NAMES"]
    region = os.environ["REGION"]
    service = os.environ["SCOPE"]
    credentials = boto3.Session().get_credentials()

    logger.info(
        "Environment",
        extra={
            "host": host,
            "indexes": index_names,
            "region": region,
            "service": service,
        },
    )

    headers = {
        "content-type": "application/json",
        "accept": "application/json",
    }

    payload = {
        "settings": {"index": {"knn": True, "mapping.total_fields.limit": 6000}},
        "mappings": {
            "properties": {
                "type": {"type": "text"},
                "document_id": {"type": "text"},
                "InventoryID": {"type": "text"},
                "FileHash": {"type": "text"},
                "StoragePath": {"type": "text"},
                "start_timecode": {"type": "keyword"},
                "end_timecode": {"type": "keyword"},
                "embedding_scope": {"type": "keyword"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
                "DerivedRepresentations": {
                    "type": "nested",
                    "properties": {
                        "Format": {"type": "text"},
                        "ID": {"type": "text"},
                        "Purpose": {"type": "text"},
                        "Type": {"type": "text"},
                        "ImageSpec": {
                            "type": "object",
                            "properties": {
                                "Resolution": {
                                    "properties": {
                                        "Height": {"type": "integer"},
                                        "Width": {"type": "integer"},
                                    }
                                }
                            },
                        },
                        "StorageInfo": {
                            "type": "object",
                            "properties": {
                                "PrimaryLocation": {
                                    "properties": {
                                        "Bucket": {"type": "text"},
                                        "Status": {"type": "text"},
                                        "Provider": {"type": "text"},
                                        "StorageType": {"type": "text"},
                                        "FileInfo": {
                                            "properties": {"Size": {"type": "long"}}
                                        },
                                        "ObjectKey": {
                                            "properties": {
                                                "FullPath": {"type": "text"},
                                                "Name": {"type": "text"},
                                                "Path": {"type": "text"},
                                            }
                                        },
                                    }
                                }
                            },
                        },
                    },
                },
                "DigitalSourceAsset": {
                    "type": "object",
                    "properties": {
                        "CreateDate": {"type": "date"},
                        "ID": {"type": "keyword"},
                        "IngestedAt": {"type": "date"},
                        "lastModifiedDate": {"type": "date"},
                        "originalIngestDate": {"type": "date"},
                        "Type": {"type": "keyword"},
                        "MainRepresentation": {
                            "type": "object",
                            "properties": {
                                "Format": {"type": "keyword"},
                                "ID": {"type": "text"},
                                "Purpose": {"type": "text"},
                                "Type": {"type": "text"},
                                "StorageInfo": {
                                    "type": "object",
                                    "properties": {
                                        "PrimaryLocation": {
                                            "properties": {
                                                "Bucket": {"type": "text"},
                                                "Status": {"type": "text"},
                                                "StorageType": {"type": "text"},
                                                "FileInfo": {
                                                    "properties": {
                                                        "CreateDate": {"type": "date"},
                                                        "Size": {"type": "long"},
                                                        "Hash": {
                                                            "properties": {
                                                                "Algorithm": {
                                                                    "type": "keyword"
                                                                },
                                                                "MD5Hash": {
                                                                    "type": "keyword"
                                                                },
                                                                "Value": {
                                                                    "type": "keyword"
                                                                },
                                                            }
                                                        },
                                                    }
                                                },
                                                "ObjectKey": {
                                                    "properties": {
                                                        "FullPath": {"type": "text"},
                                                        "Name": {"type": "text"},
                                                        "Path": {"type": "text"},
                                                    }
                                                },
                                            }
                                        }
                                    },
                                },
                            },
                        },
                    },
                },
                "Metadata": {
                    "type": "object",
                    "dynamic": True,
                    "properties": {
                        "CustomMetadata": {"type": "object", "dynamic": True}
                    },
                },
                "DigitalAsset": {
                    "type": "nested",
                    "properties": {
                        "asset_id": {"type": "keyword"},
                        "start_timecode": {"type": "keyword"},
                        "end_timecode": {"type": "keyword"},
                        "embedding_scope": {"type": "keyword"},
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": 1024,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "nmslib",
                            },
                        },
                        "EmbeddedMetadata": {"type": "object", "dynamic": True},
                    },
                },
            }
        },
    }

    logger.info(
        "Preparing to create indexes",
        extra={
            "region": region,
            "service": service,
            "vector_dimension": VECTOR_DIMENSION,
        },
    )

    indexes = index_names.split(",")
    logger.info(f"Creating {len(indexes)} indexes", extra={"indexes": indexes})

    for index_name in indexes:
        logger.info("Processing index", extra={"index_name": index_name})
        success = create_index_with_retry(
            host, index_name.strip(), payload, headers, credentials, service, region
        )
        if not success:
            msg = f"Failed to create index {index_name} after multiple retries"
            logger.error(msg)
            raise Exception(msg)

    logger.info("Successfully created all indexes")
    return {"statusCode": 200, "body": "All indexes created successfully"}
