"""Item-specific Pydantic models."""

import logging
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# Upper bound on assets accepted in one bulk request.
#
# This is a transport bound, not a product limit: a user may select any number of assets in
# the bin, and the client splits a larger selection across requests (see the spec). Adding is
# synchronous — one conditional DynamoDB write per resolved item — behind API Gateway's 29s
# response limit, so a single request has to stay comfortably inside that window.
#
# The cap alone cannot guarantee that: it bounds the item count, not the time per write. The
# handler also stops before the Lambda deadline and reports whatever it did not attempt, which
# is what actually prevents a request being killed mid-loop. The cap keeps a pathological
# request from getting that far.
#
# It counts *resolved* items too (see the handler): addAllClips expands one asset into one
# item per clip, so a small request can still resolve to a large write batch.
def _env_int(name: str, default: int) -> int:
    """Parse a positive int from the environment, falling back on anything unusable.

    Evaluated at import time, so raising would fail the Lambda during cold start and every
    request with it — a misconfigured tuning value must not be able to do that.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        logging.getLogger(__name__).warning(
            "Invalid %s=%r; falling back to %s", name, raw, default
        )
        return default
    if value < 1:
        logging.getLogger(__name__).warning(
            "Invalid %s=%r; falling back to %s", name, raw, default
        )
        return default
    return value


MAX_ITEMS_PER_REQUEST = _env_int("MAX_ITEMS_PER_REQUEST", 250)


def _validate_clip_boundary_shape(
    v: Optional[Dict[str, str]],
) -> Optional[Dict[str, str]]:
    """Shared clip-boundary validation for the single and bulk request shapes."""
    if v:
        if "startTime" in v and "endTime" in v:
            # Basic format validation for HH:MM:SS:FF
            for key in ["startTime", "endTime"]:
                parts = v[key].split(":")
                if len(parts) != 4:
                    raise ValueError(f"{key} must be in HH:MM:SS:FF format")
        elif v:  # Non-empty dict but missing required fields
            raise ValueError("clipBoundary must contain both startTime and endTime")
    return v


class AddCollectionItemSpec(BaseModel):
    """One asset to add, with its own optional clip boundary.

    The bulk form needs a boundary *per asset* rather than one for the whole request: the
    bin can hold several clips of different assets, and each selected clip must land in the
    collection as that clip.
    """

    assetId: str = Field(..., description="Asset ID to add")
    clipBoundary: Optional[Dict[str, str]] = Field(
        None,
        description="Clip boundary with startTime and endTime in HH:MM:SS:FF format",
    )
    addAllClips: bool = Field(
        default=False, description="Whether to add all clips for this asset"
    )

    @field_validator("clipBoundary")
    @classmethod
    def validate_clip_boundary(
        cls, v: Optional[Dict[str, str]]
    ) -> Optional[Dict[str, str]]:
        return _validate_clip_boundary_shape(v)


class AddItemToCollectionRequest(BaseModel):
    """Request model for adding one or more items to a collection.

    Two mutually exclusive shapes are accepted:

    * ``assetId`` (+ optional ``clipBoundary`` / ``addAllClips``) — the original
      single-asset form. Unchanged, so existing callers keep working.
    * ``items`` — a list of :class:`AddCollectionItemSpec`, each with its own clip
      boundary. Added so a multi-asset selection can be submitted in one request rather
      than one request per asset.

    ``sortOrder`` and ``metadata`` stay request-level and apply to every item, matching
    their previous behaviour.
    """

    assetId: Optional[str] = Field(
        None, description="Asset ID to add (single-asset form)"
    )
    items: Optional[List[AddCollectionItemSpec]] = Field(
        None,
        description="Assets to add, each with an optional clip boundary (bulk form)",
    )
    clipBoundary: Optional[Dict[str, str]] = Field(
        None,
        description=(
            "Clip boundary with startTime and endTime in HH:MM:SS:FF format. "
            "Only meaningful with assetId; use items[].clipBoundary for the bulk form."
        ),
    )
    addAllClips: bool = Field(
        default=False, description="Whether to add all clips for the asset"
    )
    sortOrder: Optional[int] = Field(None, description="Sort order within collection")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Custom metadata")

    @field_validator("clipBoundary")
    @classmethod
    def validate_clip_boundary(
        cls, v: Optional[Dict[str, str]]
    ) -> Optional[Dict[str, str]]:
        """Validate clip boundary format."""
        return _validate_clip_boundary_shape(v)

    @model_validator(mode="after")
    def exactly_one_shape(self) -> "AddItemToCollectionRequest":
        """Require exactly one of assetId or items.

        Rejecting both together keeps the request unambiguous — otherwise it would be
        unclear whether the request-level clipBoundary applied to the items as well.
        """
        if self.assetId and self.items:
            raise ValueError("Provide either assetId or items, not both")
        # Checked before the "neither" case below, so an explicitly empty list gets its own
        # message rather than the misleading "either assetId or items is required".
        if self.items is not None and len(self.items) == 0:
            raise ValueError("items must not be empty")
        if not self.assetId and not self.items:
            raise ValueError("Either assetId or items is required")
        # The bulk form reads the clip fields from each item, so request-level values would
        # be silently dropped. Rejecting is the safer failure: a caller that meant to add a
        # clip would otherwise get the whole asset stored instead, with a success response.
        if self.items is not None:
            if self.clipBoundary is not None:
                raise ValueError(
                    "clipBoundary must be set per item in the bulk form, "
                    "not on the request"
                )
            if self.addAllClips:
                raise ValueError(
                    "addAllClips must be set per item in the bulk form, "
                    "not on the request"
                )
        if self.items is not None and len(self.items) > MAX_ITEMS_PER_REQUEST:
            raise ValueError(
                f"items must not exceed {MAX_ITEMS_PER_REQUEST} entries per request; "
                f"got {len(self.items)}"
            )
        return self

    def resolved_items(self) -> List[AddCollectionItemSpec]:
        """Normalise both shapes to a list, so handlers only deal with one form."""
        if self.items:
            return self.items
        return [
            AddCollectionItemSpec(
                assetId=self.assetId,
                clipBoundary=self.clipBoundary,
                addAllClips=self.addAllClips,
            )
        ]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"assetId": "asset:uuid:123", "addAllClips": True},
                {
                    "assetId": "asset:uuid:456",
                    "clipBoundary": {
                        "startTime": "00:00:10:00",
                        "endTime": "00:00:20:00",
                    },
                },
                {
                    "items": [
                        {"assetId": "asset:uuid:123"},
                        {
                            "assetId": "asset:uuid:456",
                            "clipBoundary": {
                                "startTime": "00:00:10:00",
                                "endTime": "00:00:20:00",
                            },
                        },
                    ]
                },
            ]
        }
    )


class CollectionItem(BaseModel):
    """Collection item model."""

    id: str = Field(..., description="Item ID")
    itemType: str = Field(..., description="Item type (asset, workflow, etc.)")
    assetId: Optional[str] = Field(None, description="Asset ID if type is asset")
    clipBoundary: Optional[Dict[str, str]] = Field(
        None, description="Clip boundary if applicable"
    )
    sortOrder: int = Field(default=0, description="Sort order")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Item metadata")
    addedAt: str = Field(..., description="When item was added")
    addedBy: str = Field(..., description="User who added the item")

    model_config = ConfigDict(populate_by_name=True)
