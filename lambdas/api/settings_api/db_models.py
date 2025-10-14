"""
PynamoDB models for Collections API - Single Table Design.

All collections data uses a single DynamoDB table with the following access patterns:
- Collections metadata: PK=COLL#{id}, SK=METADATA
- Child references: PK=COLL#{parent_id}, SK=CHILD#{child_id}
- User relationships: PK=USER#{user_id}, SK=COLL#{collection_id}
- Collection items: PK=COLL#{collection_id}, SK=ASSET#{asset_id} or ITEM#{item_id}
- Shares: PK=COLL#{collection_id}, SK=PERM#{user_id}
- Rules: PK=COLL#{collection_id}, SK=RULE#{rule_id}
- Collection types: PK=SYSTEM, SK=COLLTYPE#{type_id}
"""

import os

from pynamodb.attributes import (
    BooleanAttribute,
    ListAttribute,
    MapAttribute,
    NumberAttribute,
    UnicodeAttribute,
)
from pynamodb.models import Model


class CollectionModel(Model):
    """
    Collection metadata model.
    PK=COLL#{collection_id}, SK=METADATA
    """

    class Meta:
        table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
        region = os.environ.get("AWS_REGION", "us-east-1")

    # Primary keys
    PK = UnicodeAttribute(hash_key=True)  # COLL#{collection_id}
    SK = UnicodeAttribute(range_key=True)  # METADATA

    # Collection attributes
    name = UnicodeAttribute()
    description = UnicodeAttribute(null=True)
    ownerId = UnicodeAttribute()
    status = UnicodeAttribute()
    itemCount = NumberAttribute(default=0)
    childCollectionCount = NumberAttribute(default=0)
    isPublic = BooleanAttribute(default=False)
    collectionTypeId = UnicodeAttribute(null=True)
    parentId = UnicodeAttribute(null=True)
    tags = ListAttribute(null=True)
    customMetadata = MapAttribute(null=True)
    createdAt = UnicodeAttribute()
    updatedAt = UnicodeAttribute()
    expiresAt = UnicodeAttribute(null=True)

    # GSI1 - User collections (PK=USER#{user_id}, SK=COLL#{collection_id})
    GSI1_PK = UnicodeAttribute(null=True)
    GSI1_SK = UnicodeAttribute(null=True)

    # GSI2 - Item collections (not used for metadata)
    GSI2_PK = UnicodeAttribute(null=True)
    GSI2_SK = UnicodeAttribute(null=True)

    # GSI3 - Collection type index
    GSI3_PK = UnicodeAttribute(null=True)
    GSI3_SK = UnicodeAttribute(null=True)

    # GSI4 - Child-parent relationship (not used for metadata)
    GSI4_PK = UnicodeAttribute(null=True)
    GSI4_SK = UnicodeAttribute(null=True)

    # GSI5 - All collections index
    GSI5_PK = UnicodeAttribute(null=True)  # "COLLECTIONS"
    GSI5_SK = UnicodeAttribute(null=True)  # timestamp for sorting


class ChildReferenceModel(Model):
    """
    Child collection reference model.
    PK=COLL#{parent_id}, SK=CHILD#{child_id}
    """

    class Meta:
        table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
        region = os.environ.get("AWS_REGION", "us-east-1")

    # Primary keys
    PK = UnicodeAttribute(hash_key=True)  # COLL#{parent_id}
    SK = UnicodeAttribute(range_key=True)  # CHILD#{child_id}

    # Child reference attributes
    childCollectionId = UnicodeAttribute()
    childCollectionName = UnicodeAttribute(null=True)
    addedAt = UnicodeAttribute()
    addedBy = UnicodeAttribute(null=True)
    type = UnicodeAttribute(default="CHILD_COLLECTION")

    # GSI4 - Reverse lookup from child to parent
    GSI4_PK = UnicodeAttribute(null=True)  # CHILD#{child_id}
    GSI4_SK = UnicodeAttribute(null=True)  # COLL#{parent_id}


class UserRelationshipModel(Model):
    """
    User-collection relationship model.
    PK=USER#{user_id}, SK=COLL#{collection_id}
    """

    class Meta:
        table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
        region = os.environ.get("AWS_REGION", "us-east-1")

    # Primary keys
    PK = UnicodeAttribute(hash_key=True)  # USER#{user_id}
    SK = UnicodeAttribute(range_key=True)  # COLL#{collection_id}

    # Relationship attributes
    relationship = UnicodeAttribute()  # OWNER, EDITOR, VIEWER
    addedAt = UnicodeAttribute()
    lastAccessed = UnicodeAttribute(null=True)
    isFavorite = BooleanAttribute(default=False)

    # GSI1 - User's collections sorted by access time
    GSI1_PK = UnicodeAttribute()  # USER#{user_id}
    GSI1_SK = UnicodeAttribute()  # timestamp or collection_id

    # GSI2 - Collection's users
    GSI2_PK = UnicodeAttribute()  # COLL#{collection_id}
    GSI2_SK = UnicodeAttribute()  # USER#{user_id}


class CollectionItemModel(Model):
    """
    Collection item model.
    PK=COLL#{collection_id}, SK=ASSET#{asset_id} or ITEM#{item_id}
    """

    class Meta:
        table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
        region = os.environ.get("AWS_REGION", "us-east-1")

    # Primary keys
    PK = UnicodeAttribute(hash_key=True)  # COLL#{collection_id}
    SK = UnicodeAttribute(range_key=True)  # ASSET#{asset_id} or ITEM#{item_id}

    # Item attributes
    itemType = UnicodeAttribute()  # asset, workflow, collection
    assetId = UnicodeAttribute(null=True)
    itemId = UnicodeAttribute(null=True)
    clipBoundary = MapAttribute(null=True)
    sortOrder = NumberAttribute(default=0)
    metadata = MapAttribute(null=True)
    addedAt = UnicodeAttribute()
    addedBy = UnicodeAttribute()

    # GSI2 - Item to collections reverse lookup
    GSI2_PK = UnicodeAttribute(null=True)  # ITEM#{item_id} or ASSET#{asset_id}
    GSI2_SK = UnicodeAttribute(null=True)  # COLL#{collection_id}


class ShareModel(Model):
    """
    Collection sharing permissions model.
    PK=COLL#{collection_id}, SK=PERM#{user_id}
    """

    class Meta:
        table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
        region = os.environ.get("AWS_REGION", "us-east-1")

    # Primary keys
    PK = UnicodeAttribute(hash_key=True)  # COLL#{collection_id}
    SK = UnicodeAttribute(range_key=True)  # PERM#{user_id}

    # Permission attributes
    targetType = UnicodeAttribute()  # user, group
    targetId = UnicodeAttribute()
    role = UnicodeAttribute()  # READ, WRITE, DELETE
    grantedBy = UnicodeAttribute()
    grantedAt = UnicodeAttribute()
    message = UnicodeAttribute(null=True)


class RuleModel(Model):
    """
    Collection rule model.
    PK=COLL#{collection_id}, SK=RULE#{rule_id}
    """

    class Meta:
        table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
        region = os.environ.get("AWS_REGION", "us-east-1")

    # Primary keys
    PK = UnicodeAttribute(hash_key=True)  # COLL#{collection_id}
    SK = UnicodeAttribute(range_key=True)  # RULE#{rule_id}

    # Rule attributes
    name = UnicodeAttribute()
    description = UnicodeAttribute(null=True)
    ruleType = UnicodeAttribute()
    criteria = MapAttribute()
    isActive = BooleanAttribute(default=True)
    priority = NumberAttribute(default=0)
    matchCount = NumberAttribute(default=0)
    createdAt = UnicodeAttribute()
    updatedAt = UnicodeAttribute()


class CollectionTypeModel(Model):
    """
    Collection type model.
    PK=SYSTEM, SK=COLLTYPE#{type_id}
    """

    class Meta:
        table_name = os.environ.get("COLLECTIONS_TABLE_NAME", "collections_table_dev")
        region = os.environ.get("AWS_REGION", "us-east-1")

    # Primary keys
    PK = UnicodeAttribute(hash_key=True)  # SYSTEM
    SK = UnicodeAttribute(range_key=True)  # COLLTYPE#{type_id}

    # Type attributes
    name = UnicodeAttribute()
    description = UnicodeAttribute(null=True)
    color = UnicodeAttribute()  # Hex color format: #RRGGBB
    icon = UnicodeAttribute()  # Material-UI icon name
    isActive = BooleanAttribute(default=True)
    isSystem = BooleanAttribute(default=False)  # True for default types
    allowedItemTypes = ListAttribute(null=True)
    schema = MapAttribute(null=True)
    createdAt = UnicodeAttribute()
    updatedAt = UnicodeAttribute()
