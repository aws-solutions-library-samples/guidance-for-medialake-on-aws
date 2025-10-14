"""Test helper functions for Settings API tests."""

from typing import Any, Dict


def seed_collection_type(table, type_data: Dict[str, Any]):
    """Helper function to seed a collection type in DynamoDB."""
    item = {
        "PK": "SYSTEM",
        "SK": f"COLLTYPE#{type_data['id']}",
        "name": type_data["name"],
        "description": type_data.get("description"),
        "color": type_data["color"],
        "icon": type_data["icon"],
        "isActive": type_data["isActive"],
        "isSystem": type_data.get("isSystem", False),
        "createdAt": type_data["createdAt"],
        "updatedAt": type_data["updatedAt"],
    }
    table.put_item(Item=item)
    return item


def seed_collection(table, collection_id: str, type_id: str):
    """Helper function to seed a collection in DynamoDB."""
    item = {
        "PK": f"COLLECTION#{collection_id}",
        "SK": "METADATA#",
        "name": "Test Collection",
        "collectionTypeId": type_id,
        "ownerId": "test-user-id",
        "status": "active",
        "itemCount": 0,
        "childCollectionCount": 0,
        "isPublic": False,
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-01-01T00:00:00Z",
    }
    table.put_item(Item=item)
    return item
