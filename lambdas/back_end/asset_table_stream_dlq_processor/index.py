import json
import os
from decimal import Decimal
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Tracer
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.helpers import bulk
from requests_aws4auth import AWS4Auth

logger = Logger(service="ddb-dlq-processor")
tracer = Tracer()

# OpenSearch configuration
REGION = os.environ["OS_DOMAIN_REGION"]
HOST = os.environ["OPENSEARCH_ENDPOINT"].split("://")[-1]
INDEX = os.environ["OPENSEARCH_INDEX"]

# Initialize AWS credentials and clients
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    "es",
    session_token=credentials.token,
)

opensearch_client = OpenSearch(
    hosts=[{"host": HOST, "port": 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    timeout=30,
    max_retries=3,
    retry_on_timeout=True,
)


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Decimal objects from DynamoDB."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)


def prepare_bulk_action(record: Dict[str, Any], message_type: str) -> Dict[str, Any]:
    """
    Prepare a single bulk action from a DLQ message.

    Args:
        record: The asset record from DLQ
        message_type: Type of operation (Insert/Modify/Delete)

    Returns:
        Bulk action dict for OpenSearch
    """
    document_id = record.get("InventoryID")

    if not document_id:
        raise ValueError("Record missing InventoryID")

    if "Delete" in message_type:
        return {
            "_op_type": "delete",
            "_index": INDEX,
            "_id": document_id,
        }
    elif "Insert" in message_type:
        return {
            "_op_type": "index",
            "_index": INDEX,
            "_id": document_id,
            "_source": record,
        }
    else:  # Modify
        return {
            "_op_type": "update",
            "_index": INDEX,
            "_id": document_id,
            "doc": record,
            "doc_as_upsert": True,
        }


@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """
    Process messages from the DLQ and attempt to reindex them in OpenSearch.

    This Lambda can be triggered manually or on a schedule to process failed messages.
    """
    logger.info(
        "DLQ Processor invoked",
        extra={
            "aws_request_id": context.aws_request_id,
            "record_count": len(event.get("Records", [])),
        },
    )

    bulk_actions = []
    failed_records = []

    for sqs_record in event.get("Records", []):
        try:
            # Parse SQS message body
            body = json.loads(sqs_record["body"])

            # Get message attributes
            message_attrs = sqs_record.get("messageAttributes", {})
            message_type = message_attrs.get("MessageType", {}).get(
                "stringValue", "Insert the Index"
            )

            failure_reason = message_attrs.get("FailureReason", {}).get(
                "stringValue", "Unknown"
            )
            event_name = message_attrs.get("EventName", {}).get(
                "stringValue", "Unknown"
            )
            inventory_id = message_attrs.get("InventoryID", {}).get(
                "stringValue", body.get("InventoryID", "unknown")
            )

            # Skip internal LOCK records - they should never be indexed
            if inventory_id.startswith("LOCK#"):
                logger.info(
                    f"Skipping LOCK record from DLQ",
                    extra={
                        "inventory_id": inventory_id,
                        "message_id": sqs_record.get("messageId"),
                    },
                )
                continue

            error_status = message_attrs.get("ErrorStatus", {}).get("stringValue")
            error_type = message_attrs.get("ErrorType", {}).get("stringValue")
            error_reason = message_attrs.get("ErrorReason", {}).get("stringValue")
            error_index = message_attrs.get("ErrorIndex", {}).get("stringValue")
            opensearch_error = message_attrs.get("OpenSearchError", {}).get(
                "stringValue"
            )

            log_extra = {
                "message_type": message_type,
                "inventory_id": inventory_id,
                "failure_reason": failure_reason,
                "event_name": event_name,
            }

            if error_status:
                log_extra.update(
                    {
                        "error_status": error_status,
                        "error_type": error_type,
                        "error_reason": error_reason,
                        "error_index": error_index,
                    }
                )

                if opensearch_error:
                    log_extra["opensearch_error"] = opensearch_error

            logger.info(
                f"Processing DLQ message with detailed error information",
                extra=log_extra,
            )

            # Prepare bulk action
            action = prepare_bulk_action(body, message_type)
            bulk_actions.append(action)

        except Exception as e:
            logger.error(
                f"Failed to prepare bulk action from DLQ message",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "message_id": sqs_record.get("messageId"),
                },
            )
            failed_records.append(sqs_record)

    # Process bulk actions in smaller batches
    batch_size = 100
    total_success = 0
    total_failed = 0

    for i in range(0, len(bulk_actions), batch_size):
        batch = bulk_actions[i : i + batch_size]

        try:
            logger.info(
                f"Processing batch {i//batch_size + 1} with {len(batch)} actions"
            )

            success, failed = bulk(
                opensearch_client,
                batch,
                stats_only=False,
                raise_on_error=False,
                raise_on_exception=False,
            )

            total_success += success
            total_failed += len(failed)

            if failed:
                logger.warning(
                    f"Batch had {len(failed)} failures",
                    extra={
                        "batch_number": i // batch_size + 1,
                        "failures": len(failed),
                    },
                )

                for item in failed:
                    error_info = item.get(
                        "index", item.get("update", item.get("delete", {}))
                    )
                    error_details = error_info.get("error", {})

                    logger.error(
                        "Failed to reprocess item from DLQ",
                        extra={
                            "item_id": error_info.get("_id"),
                            "status": error_info.get("status"),
                            "error_type": (
                                error_details.get("type")
                                if isinstance(error_details, dict)
                                else "unknown"
                            ),
                            "error_reason": (
                                error_details.get("reason")
                                if isinstance(error_details, dict)
                                else str(error_details)
                            ),
                            "full_error": error_details,
                        },
                    )

        except Exception as e:
            logger.error(
                f"Failed to process batch",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "batch_number": i // batch_size + 1,
                },
            )
            total_failed += len(batch)

    logger.info(
        "DLQ processing completed",
        extra={
            "total_messages": len(event.get("Records", [])),
            "total_success": total_success,
            "total_failed": total_failed,
            "preparation_failures": len(failed_records),
        },
    )

    return {
        "statusCode": 200 if total_failed == 0 else 207,
        "body": json.dumps(
            {
                "message": "DLQ processing completed",
                "total_messages": len(event.get("Records", [])),
                "success": total_success,
                "failed": total_failed,
                "preparation_failures": len(failed_records),
            }
        ),
    }
