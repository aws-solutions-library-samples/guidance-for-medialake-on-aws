"""PynamoDB models for Upload Portals — Single Table Design on System Settings table."""

import os

from pynamodb.attributes import (
    BooleanAttribute,
    ListAttribute,
    MapAttribute,
    NumberAttribute,
    UnicodeAttribute,
)
from pynamodb.indexes import AllProjection, GlobalSecondaryIndex
from pynamodb.models import Model

_TABLE_NAME = os.environ.get("SYSTEM_SETTINGS_TABLE_NAME", "system-settings-dev")
_REGION = os.environ.get("AWS_REGION", "us-east-1")


class PortalGSI1(GlobalSecondaryIndex):
    """GSI1 for listing all portals: GSI1_PK / GSI1_SK."""

    class Meta:
        index_name = "GSI1"
        projection = AllProjection()

    GSI1_PK = UnicodeAttribute(hash_key=True)
    GSI1_SK = UnicodeAttribute(range_key=True)


class PortalMetadataModel(Model):
    """PK=UPLOADPORTAL#{portalId}, SK=METADATA"""

    class Meta:
        table_name = _TABLE_NAME
        region = _REGION

    PK = UnicodeAttribute(hash_key=True)
    SK = UnicodeAttribute(range_key=True)

    portalId = UnicodeAttribute()
    slug = UnicodeAttribute()
    name = UnicodeAttribute()
    description = UnicodeAttribute(null=True)
    logoS3Key = UnicodeAttribute(null=True)
    bannerS3Key = UnicodeAttribute(null=True)
    faviconS3Key = UnicodeAttribute(null=True)
    accessMode = UnicodeAttribute(null=True)
    createdBy = UnicodeAttribute(null=True)
    createdAt = UnicodeAttribute(null=True)
    updatedAt = UnicodeAttribute(null=True)
    expiresAt = UnicodeAttribute(null=True)
    allowedGroups = ListAttribute(null=True)
    ipAllowlist = ListAttribute(null=True)
    metadataFields = ListAttribute(null=True)
    passphrase = UnicodeAttribute(null=True)
    tokenBypassesPassphrase = BooleanAttribute(default=False)
    structuredPathMode = BooleanAttribute(default=False)
    captchaEnabled = BooleanAttribute(default=False)
    isActive = BooleanAttribute(default=True)
    maxFileSizeBytes = NumberAttribute(null=True)
    maxFilesPerSession = NumberAttribute(null=True)
    accessVersion = NumberAttribute(null=True)

    # GSI1 for listing all portals
    GSI1 = PortalGSI1()
    GSI1_PK = UnicodeAttribute(null=True)
    GSI1_SK = UnicodeAttribute(null=True)


class PortalDestinationModel(Model):
    """PK=UPLOADPORTAL#{portalId}, SK=DEST#{destinationId}"""

    class Meta:
        table_name = _TABLE_NAME
        region = _REGION

    PK = UnicodeAttribute(hash_key=True)
    SK = UnicodeAttribute(range_key=True)

    destinationId = UnicodeAttribute()
    friendlyName = UnicodeAttribute()
    connectorId = UnicodeAttribute()
    rootPath = UnicodeAttribute()
    allowBrowsing = BooleanAttribute(default=False)
    allowFolderCreation = BooleanAttribute(default=False)
    order = NumberAttribute()
    pathSegments = ListAttribute(null=True)


class PortalTokenModel(Model):
    """PK=UPLOADPORTAL#{portalId}, SK=TOKEN#{tokenId}"""

    class Meta:
        table_name = _TABLE_NAME
        region = _REGION

    PK = UnicodeAttribute(hash_key=True)
    SK = UnicodeAttribute(range_key=True)

    tokenId = UnicodeAttribute()
    tokenHash = UnicodeAttribute()
    associatedEmail = UnicodeAttribute()
    createdAt = UnicodeAttribute()
    expiresAt = UnicodeAttribute(null=True)
    isRevoked = BooleanAttribute(default=False)
    prePopulatedParams = MapAttribute(null=True)


class PortalSlugIndexModel(Model):
    """PK=UPLOADPORTAL_SLUG#{slug}, SK=INDEX"""

    class Meta:
        table_name = _TABLE_NAME
        region = _REGION

    PK = UnicodeAttribute(hash_key=True)
    SK = UnicodeAttribute(range_key=True)

    portalId = UnicodeAttribute()
