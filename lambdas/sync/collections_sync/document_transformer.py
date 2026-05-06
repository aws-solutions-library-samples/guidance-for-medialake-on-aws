"""Document transformer for DynamoDB items to OpenSearch documents.

Transforms collection and collection group metadata items from DynamoDB
format into OpenSearch-compatible documents per the field mapping tables
in the design document.
"""

from aws_lambda_powertools import Logger

logger = Logger(service="collections-sync-transformer")


def extract_entity_id(pk: str) -> str:
    """Extract the entity ID from a PK value.

    Args:
        pk: DynamoDB PK value (e.g., 'COLL#abc' or 'GROUP#xyz')

    Returns:
        The entity ID with the prefix stripped (e.g., 'abc' or 'xyz')
    """
    if "#" in pk:
        return pk.split("#", 1)[1]
    return pk


def transform_collection(dynamodb_item: dict) -> dict | None:
    """Transform a DynamoDB collection METADATA item to an OpenSearch document.

    Args:
        dynamodb_item: Deserialized DynamoDB item dict with collection attributes

    Returns:
        OpenSearch document dict with mapped fields, or None if PK is invalid
    """
    entity_id = extract_entity_id(dynamodb_item.get("PK", ""))
    if not entity_id:
        logger.warning(
            "Skipping collection with empty/invalid PK",
            extra={"pk": dynamodb_item.get("PK", "")},
        )
        return None

    raw_status = dynamodb_item.get("status", "")
    status = raw_status if raw_status else "unknown"

    doc = {
        "id": entity_id,
        "name": dynamodb_item.get("name", ""),
        "description": dynamodb_item.get("description"),
        "ownerId": dynamodb_item.get("ownerId", ""),
        "status": status,
        "isPublic": dynamodb_item.get("isPublic", False),
        "collectionTypeId": dynamodb_item.get("collectionTypeId"),
        "tags": dynamodb_item.get("tags"),
        "childCollectionCount": dynamodb_item.get("childCollectionCount", 0),
        "itemCount": dynamodb_item.get("itemCount", 0),
        "sharedWithUserIds": dynamodb_item.get("sharedWithUserIds", []),
        "createdAt": dynamodb_item.get("createdAt", ""),
        "updatedAt": dynamodb_item.get("updatedAt", ""),
        "thumbnailType": dynamodb_item.get("thumbnailType"),
        "thumbnailValue": dynamodb_item.get("thumbnailValue"),
        "thumbnailS3Key": dynamodb_item.get("thumbnailS3Key"),
        "customMetadata": dynamodb_item.get("customMetadata"),
        "expiresAt": dynamodb_item.get("expiresAt"),
        "documentType": "collection",
    }
    # Only include parentId when it has a value — omitting it entirely
    # ensures OpenSearch's "exists" query correctly identifies root collections
    parent_id = dynamodb_item.get("parentId")
    if parent_id:
        doc["parentId"] = parent_id
    return doc


def transform_collection_group(dynamodb_item: dict) -> dict:
    """Transform a DynamoDB collection group METADATA item to an OpenSearch document.

    Args:
        dynamodb_item: Deserialized DynamoDB item dict with group attributes

    Returns:
        OpenSearch document dict with mapped fields
    """
    return {
        "id": extract_entity_id(dynamodb_item.get("PK", "")),
        "name": dynamodb_item.get("name", ""),
        "description": dynamodb_item.get("description"),
        "ownerId": dynamodb_item.get("ownerId", ""),
        "isPublic": dynamodb_item.get("isPublic", False),
        "collectionIds": dynamodb_item.get("collectionIds", []),
        "createdAt": dynamodb_item.get("createdAt", ""),
        "updatedAt": dynamodb_item.get("updatedAt", ""),
        "documentType": "collection_group",
    }
