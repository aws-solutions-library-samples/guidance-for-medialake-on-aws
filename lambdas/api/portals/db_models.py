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


class PortalPageMap(MapAttribute):
    """One nested page inside PortalMetadataModel.pages.

    `elements` is a free-form list of {kind, fieldKey?} dicts. Kept as a raw
    ListAttribute so adding element kinds later needs no model change.
    """

    pageNumber = NumberAttribute()
    title = UnicodeAttribute(null=True)
    descriptionHtml = UnicodeAttribute(null=True)
    visibleIf = UnicodeAttribute(null=True)
    elements = ListAttribute(null=True)


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
    # When True (default), the portal shows a Submit step whose click marks the
    # session submitted (drives the formSubmissionComplete signal). When False,
    # the portal is upload-only (no Submit button) and formSubmissionComplete is
    # always false.
    formSubmissionEnabled = BooleanAttribute(default=True)
    isActive = BooleanAttribute(default=True)
    maxFileSizeBytes = NumberAttribute(null=True)
    maxFilesPerSession = NumberAttribute(null=True)
    automationTag = UnicodeAttribute(null=True)
    accessVersion = NumberAttribute(null=True)

    # Allowed upload file types (MIME patterns like "image/*" or extensions like
    # ".pdf"). Semantics are tri-state and intentional:
    #   - attribute ABSENT (None) → fall back to the default media allow-list
    #     (audio/video/image/...), preserving behavior for portals created
    #     before this field existed;
    #   - attribute == [] (empty)  → allow ANY file type (admin cleared it);
    #   - non-empty list           → restrict to exactly those types.
    allowedFileTypes = ListAttribute(null=True)

    # Appearance pass-through. MapAttribute with no inner schema so the entire
    # visual-editor appearance object round-trips verbatim (fixes the silent-drop
    # bug where no attribute existed). Mirrors the prePopulatedParams Map pattern.
    appearance = MapAttribute(null=True)

    # Nested pages (interpretation "B"). Replaces the implicit single page.
    # No migration: feature is unreleased.
    pages = ListAttribute(of=PortalPageMap, null=True)

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
    # Ties a destination to a page (matches a PortalPageMap.pageNumber).
    pageNumber = NumberAttribute(null=True)


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


class PortalThemeModel(Model):
    """PK=PORTALTHEME#{themeId}, SK=METADATA — appearance-only, reusable.

    A Theme is a named, reusable appearance configuration with no portal
    structure. Each theme is a single item keyed by its own PK, so we reuse the
    fixed ``METADATA`` sort key (``portal_utils.METADATA_SK``) just like the
    portal record. Listing is served by querying GSI1 with
    ``GSI1_PK == "PORTALTHEMES"`` (mirrors PortalMetadataModel's
    ``"UPLOADPORTALS"`` pattern); ``GSI1_SK`` carries ``createdAt`` for ordering.
    """

    class Meta:
        table_name = _TABLE_NAME
        region = _REGION

    PK = UnicodeAttribute(hash_key=True)
    SK = UnicodeAttribute(range_key=True)

    themeId = UnicodeAttribute()
    name = UnicodeAttribute()
    description = UnicodeAttribute(null=True)

    # Appearance pass-through. Schemaless MapAttribute so the entire
    # visual-editor appearance object round-trips verbatim, exactly like
    # PortalMetadataModel.appearance.
    appearance = MapAttribute(null=True)

    createdBy = UnicodeAttribute(null=True)
    createdAt = UnicodeAttribute(null=True)
    updatedAt = UnicodeAttribute(null=True)

    # GSI1 for listing all themes (GSI1_PK = "PORTALTHEMES").
    GSI1 = PortalGSI1()
    GSI1_PK = UnicodeAttribute(null=True)
    GSI1_SK = UnicodeAttribute(null=True)


class PortalTemplateModel(Model):
    """PK=PORTALTEMPLATE#{templateId}, SK=METADATA — full structure snapshot.

    A Template is a point-in-time snapshot of a full portal structure with no
    live link to portals created from it. Each template is a single item keyed
    by its own PK, so we reuse the fixed ``METADATA`` sort key
    (``portal_utils.METADATA_SK``) like the portal/theme records. Destinations
    are stored inline on this item (not as ``DEST#`` sort-key items) because a
    template is a snapshot, not a live portal; they are expanded into ``DEST#``
    items only when a real portal is created. Listing is served by querying GSI1
    with ``GSI1_PK == "PORTALTEMPLATES"``; ``GSI1_SK`` carries ``createdAt``.

    A template NEVER stores a passphrase (passphrases are per-portal secrets);
    there is intentionally no ``passphrase`` attribute on this model.
    """

    class Meta:
        table_name = _TABLE_NAME
        region = _REGION

    PK = UnicodeAttribute(hash_key=True)
    SK = UnicodeAttribute(range_key=True)

    templateId = UnicodeAttribute()
    name = UnicodeAttribute()
    description = UnicodeAttribute(null=True)
    themeId = UnicodeAttribute(null=True)  # optional bundled theme reference

    # Structure snapshot — same shapes as the portal record.
    pages = ListAttribute(of=PortalPageMap, null=True)
    metadataFields = ListAttribute(null=True)  # entries carry pageNumber
    destinations = ListAttribute(null=True)  # entries carry connectorId + pageNumber

    # Optional inline appearance snapshot (pass-through, like the portal record).
    appearance = MapAttribute(null=True)

    # Access settings + limits relevant to seeding a portal. No passphrase.
    accessMode = UnicodeAttribute(null=True)
    allowedGroups = ListAttribute(null=True)
    ipAllowlist = ListAttribute(null=True)
    tokenBypassesPassphrase = BooleanAttribute(default=False)
    structuredPathMode = BooleanAttribute(default=False)
    captchaEnabled = BooleanAttribute(default=False)
    formSubmissionEnabled = BooleanAttribute(default=True)
    maxFileSizeBytes = NumberAttribute(null=True)
    maxFilesPerSession = NumberAttribute(null=True)

    createdBy = UnicodeAttribute(null=True)
    createdAt = UnicodeAttribute(null=True)
    updatedAt = UnicodeAttribute(null=True)

    # GSI1 for listing all templates (GSI1_PK = "PORTALTEMPLATES").
    GSI1 = PortalGSI1()
    GSI1_PK = UnicodeAttribute(null=True)
    GSI1_SK = UnicodeAttribute(null=True)
