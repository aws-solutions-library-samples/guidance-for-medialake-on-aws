import boto3
from botocore.exceptions import ClientError
from requests import request
import json
import os
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import time
from lambda_utils import logger, lambda_handler_decorator

VECTOR_DIMENSION = 1024  # Twelve Labs embeddings dimension

def create_index_with_retry(
    host, index_name, payload, headers, credentials, service, region, max_retries=5
):
    """
    Create an OpenSearch index with retry logic and exponential backoff
    
    Args:
        host: OpenSearch host endpoint
        index_name: Name of the index to create
        payload: Index configuration payload
        headers: HTTP headers for the request
        credentials: AWS credentials for SigV4 signing
        service: AWS service name for SigV4 signing
        region: AWS region for SigV4 signing
        max_retries: Maximum number of retry attempts
        
    Returns:
        bool: True if index creation was successful, False otherwise
    """
    url = f"{host}/{index_name}"
    logger.info(f"Creating OpenSearch index", extra={"url": url, "index_name": index_name})

    for attempt in range(max_retries):
        try:
            req = AWSRequest(
                method="PUT", url=url, data=json.dumps(payload), headers=headers
            )
            req.headers["X-Amz-Content-SHA256"] = SigV4Auth(
                credentials, service, region
            ).payload(req)
            SigV4Auth(credentials, service, region).add_auth(req)
            req = req.prepare()

            logger.info("Sending request to OpenSearch", extra={
                "method": req.method,
                "url": req.url,
                "attempt": attempt + 1,
                "max_retries": max_retries
            })
            
            response = request(
                method=req.method, url=req.url, headers=req.headers, data=req.body
            )

            if response.status_code == 200:
                logger.info(
                    "Index creation successful",
                    extra={
                        "index_name": index_name,
                        "status_code": response.status_code,
                        "response": response.text
                    }
                )
                return True
            else:
                if (
                    response.json()["error"]["root_cause"][0]["type"]
                    == "resource_already_exists_exception"
                ):
                    error_message = f"Index '{index_name}' already exists - cannot proceed with creation"
                    logger.error(
                        "Index already exists - failing lambda execution",
                        extra={
                            "index_name": index_name,
                            "status_code": response.status_code,
                            "full_response": response.text,
                            "error_details": response.json(),
                            "operation": "create_index"
                        }
                    )
                    raise Exception(error_message)
                
                logger.error(
                    "Failed to create OpenSearch index",
                    extra={
                        "index_name": index_name,
                        "status_code": response.status_code,
                        "response": response.text,
                        "attempt": attempt + 1,
                        "max_retries": max_retries
                    }
                )

        except Exception as e:
            logger.error(
                "Error creating OpenSearch index",
                extra={
                    "index_name": index_name,
                    "error": str(e),
                    "attempt": attempt + 1,
                    "max_retries": max_retries
                },
                exc_info=True
            )

        # Exponential backoff
        backoff_time = 2**attempt
        logger.info(
            "Retrying index creation after backoff",
            extra={
                "index_name": index_name,
                "attempt": attempt + 1,
                "max_retries": max_retries,
                "backoff_seconds": backoff_time
            }
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

    if event["RequestType"] == "Create":
        host = os.environ["COLLECTION_ENDPOINT"]
        logger.info("Retrieved collection endpoint", extra={"host": host})

        index_names = os.environ["INDEX_NAMES"]
        logger.info("Retrieved index names", extra={"index_names": index_names})

        headers = {
            "content-type": "application/json",
            "accept": "application/json",
        }      

        payload = {
            "settings": {
                "index": {
                    "knn": True,
                    "mapping.total_fields.limit": 6000
                }
            },
            "mappings": {
                "properties": {
                "type":             {"type": "text"},
                "document_id":      {"type": "text"},
                "InventoryID":      {"type": "text"},
                "FileHash":         {"type": "text"},
                "StoragePath":      {"type": "text"}, 
                "start_timecode":   {"type": "keyword"},
                "end_timecode":     {"type": "keyword"},
                "embedding_scope":  {"type": "keyword"},
                "embedding": {
                    "type":      "knn_vector",
                    "dimension": 1024,
                    "method": {
                    "name":       "hnsw",
                    "space_type": "cosinesimil",
                    "engine":     "nmslib"
                    }
                },   
                "DerivedRepresentations": {
                "type": "nested", 
                "properties": {
                    "Format":    { "type": "text"  },
                    "ID":        { "type": "text"  },
                    "Purpose":   { "type": "text"  },
                    "Type":      { "type": "text"  },
                    "ImageSpec": {
                        "type": "object",
                        "properties": {
                            "Resolution": {
                                "properties": {
                                    "Height": { "type": "integer" },
                                    "Width": { "type": "integer" }
                                }
                            }
                        }
                    },
                    "StorageInfo": {
                        "type": "object",
                        "properties": {
                            "PrimaryLocation": {
                                "properties": {
                                    "Bucket": { "type": "text" },
                                    "Status": { "type": "text" },
                                    "Provider": { "type": "text" },
                                    "StorageType": { "type": "text" },
                                    "FileInfo": {
                                        "properties": {
                                            "Size": { "type": "long" }
                                        }
                                    },
                                    "ObjectKey": {
                                        "properties": {
                                            "FullPath": { "type": "text" },
                                            "Name": { "type": "text" },
                                            "Path": { "type": "text" }
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
                        "CreateDate": { "type": "date" },
                        "ID": { "type": "keyword" },
                        "IngestedAt": { "type": "date" },
                        "lastModifiedDate": { "type": "date" },
                        "originalIngestDate": { "type": "date" },
                        "Type": { "type": "text" },
                        "MainRepresentation": {
                            "type": "object",
                            "properties": {
                                "Format": { "type": "text" },
                                "ID": { "type": "text" },
                                "Purpose": { "type": "text" },
                                "Type": { "type": "text" },
                                "StorageInfo": {
                                    "type": "object",
                                    "properties": {
                                        "PrimaryLocation": {
                                            "properties": {
                                                "Bucket": { "type": "text" },
                                                "Status": { "type": "text" },
                                                "StorageType": { "type": "text" },
                                                "FileInfo": {
                                                    "properties": {
                                                        "CreateDate": { "type": "date" },
                                                        "Size": { "type": "long" },
                                                        "Hash": {
                                                            "properties": {
                                                                "Algorithm": { "type": "keyword" },
                                                                "MD5Hash": { "type": "keyword" },
                                                                "Value": { "type": "keyword" }
                                                            }
                                                        }
                                                    }
                                                },
                                                "ObjectKey": {
                                                    "properties": {
                                                        "FullPath": { "type": "text" },
                                                        "Name": { "type": "text" },
                                                        "Path": { "type": "text" }
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
                    "type": "object",
                    "dynamic": True,
                    "properties": {
                        "CustomMetadata": {
                            "type": "object",
                            "dynamic": True
                        }
                    }
                },
                "DigitalAsset": {
                    "type": "nested",
                    "properties": {
                        "asset_id":         { "type": "keyword" },
                        "start_timecode":   { "type": "keyword" },
                        "end_timecode":     { "type": "keyword" },
                        "embedding_scope":  { "type": "keyword" },
                        "embedding": {
                            "type":      "knn_vector",
                            "dimension": 1024,
                            "method": {
                                "name":       "hnsw",
                                "space_type": "cosinesimil",
                                "engine":     "nmslib"
                            }
                        },
                        "EmbeddedMetadata": { "type": "object", "dynamic": True }
                        }
                    }
                }
            }
        }


        region = os.environ["REGION"]
        service = os.environ["SCOPE"]
        credentials = boto3.Session().get_credentials()

        logger.info(
            "Preparing to create indexes",
            extra={
                "region": region,
                "service": service,
                "vector_dimension": VECTOR_DIMENSION
            }
        )

        indexes = index_names.split(",")
        logger.info(f"Creating {len(indexes)} indexes", extra={"indexes": indexes})
        
        for index_name in indexes:
            logger.info(f"Processing index", extra={"index_name": index_name})
            success = create_index_with_retry(
                host, index_name, payload, headers, credentials, service, region
            )
            if not success:
                error_msg = f"Failed to create index {index_name} after multiple retries"
                logger.error(error_msg)
                raise Exception(error_msg)
            
        logger.info("Successfully created all indexes")
        return {"statusCode": 200, "body": "All indexes created successfully"}
    else:
        logger.info(f"Skipping non-Create request type", extra={"RequestType": event["RequestType"]})
        return {"statusCode": 200, "body": f"Skipped {event['RequestType']} request"}
