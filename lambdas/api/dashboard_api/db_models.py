"""
PynamoDB models for Dashboard API - Single Table Design.

All dashboard data uses a single DynamoDB table with the following access patterns:
- User Layout:    PK=USER#{userId}  SK=LAYOUT#active
- User Preset:    PK=USER#{userId}  SK=PRESET#{presetId}
- System Default: PK=SYSTEM         SK=LAYOUT#default
"""

import json
import os

from pynamodb.attributes import (
    NumberAttribute,
    UnicodeAttribute,
)
from pynamodb.models import Model

# Key prefixes for single-table design
USER_PK_PREFIX = "USER#"
SYSTEM_PK = "SYSTEM"
LAYOUT_SK_ACTIVE = "LAYOUT#active"
LAYOUT_SK_DEFAULT = "LAYOUT#default"
PRESET_SK_PREFIX = "PRESET#"


class JSONAttribute(UnicodeAttribute):
    """
    Custom attribute for storing JSON data as a string.
    Automatically serializes/deserializes Python objects to/from JSON.
    """

    def serialize(self, value):
        """Convert Python object to JSON string for storage."""
        if value is None:
            return None
        return json.dumps(value)

    def deserialize(self, value):
        """Convert JSON string back to Python object."""
        if value is None or value == "":
            return None
        return json.loads(value)


class DashboardLayoutModel(Model):
    """
    User dashboard layout or system default.

    Access Patterns:
    - User's active layout: PK=USER#{userId}, SK=LAYOUT#active
    - System default layout: PK=SYSTEM, SK=LAYOUT#default
    """

    class Meta:
        table_name = os.environ.get("DASHBOARD_TABLE_NAME", "dashboard_table_dev")
        region = os.environ.get("AWS_REGION", "us-east-1")

    # Primary keys
    PK = UnicodeAttribute(hash_key=True)  # USER#{userId} or SYSTEM
    SK = UnicodeAttribute(range_key=True)  # LAYOUT#active or LAYOUT#default

    # Layout attributes
    userId = UnicodeAttribute(null=True)  # Null for system default
    layoutVersion = NumberAttribute(default=1)
    widgets = JSONAttribute()  # List of WidgetInstance dicts (stored as JSON)
    layouts = JSONAttribute()  # {lg: [], md: [], sm: []} (stored as JSON)
    createdAt = UnicodeAttribute()
    updatedAt = UnicodeAttribute()


class DashboardPresetModel(Model):
    """
    Saved layout preset.

    Access Pattern:
    - User's presets: PK=USER#{userId}, SK=PRESET#{presetId}
    - Query all presets: Query PK=USER#{userId}, SK begins_with PRESET#
    """

    class Meta:
        table_name = os.environ.get("DASHBOARD_TABLE_NAME", "dashboard_table_dev")
        region = os.environ.get("AWS_REGION", "us-east-1")

    # Primary keys
    PK = UnicodeAttribute(hash_key=True)  # USER#{userId}
    SK = UnicodeAttribute(range_key=True)  # PRESET#{presetId}

    # Preset attributes
    presetId = UnicodeAttribute()
    userId = UnicodeAttribute()
    name = UnicodeAttribute()
    description = UnicodeAttribute(null=True)
    widgets = JSONAttribute()  # List of WidgetInstance dicts (stored as JSON)
    layouts = JSONAttribute()  # {lg: [], md: [], sm: []} (stored as JSON)
    createdAt = UnicodeAttribute()
    updatedAt = UnicodeAttribute()
