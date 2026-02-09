"""Default layout configuration and widget constraints."""

# Widget type constraints for validation
WIDGET_CONSTRAINTS = {
    "favorites": {
        "defaultSize": {"w": 6, "h": 6},
        "minSize": {"w": 3, "h": 4},
        "maxSize": {"w": 12, "h": 12},
    },
    "collections": {
        "defaultSize": {"w": 6, "h": 6},
        "minSize": {"w": 3, "h": 2},
        "maxSize": {"w": 12, "h": 8},
    },
    "recent-assets": {
        "defaultSize": {"w": 12, "h": 6},
        "minSize": {"w": 4, "h": 4},
        "maxSize": {"w": 12, "h": 12},
    },
    "collection-group": {
        "defaultSize": {"w": 6, "h": 6},
        "minSize": {"w": 3, "h": 2},
        "maxSize": {"w": 12, "h": 8},
    },
}

# Default layout configuration with 3 widgets
DEFAULT_LAYOUT = {
    "layoutVersion": 1,
    "widgets": [
        # Row 1: Recent Assets (full width)
        {"id": "recent-assets-default", "type": "recent-assets", "config": {}},
        # Row 2: Favorites (left), All Collections (right)
        {"id": "favorites-default", "type": "favorites", "config": {}},
        {
            "id": "default-all-collections",
            "type": "collections",
            "config": {
                "viewType": "all",
                "sorting": {"sortBy": "name", "sortOrder": "asc"},
            },
        },
    ],
    "layouts": {
        "lg": [
            # Row 1: Recent Assets full width
            {
                "i": "recent-assets-default",
                "x": 0,
                "y": 0,
                "w": 12,
                "h": 6,
                "minW": 4,
                "minH": 4,
                "maxW": 12,
                "maxH": 12,
            },
            # Row 2: Favorites left, Collections right
            {
                "i": "favorites-default",
                "x": 0,
                "y": 6,
                "w": 6,
                "h": 6,
                "minW": 3,
                "minH": 4,
                "maxW": 12,
                "maxH": 12,
            },
            {
                "i": "default-all-collections",
                "x": 6,
                "y": 6,
                "w": 6,
                "h": 6,
                "minW": 3,
                "minH": 2,
                "maxW": 12,
                "maxH": 8,
            },
        ],
        "md": [
            {"i": "recent-assets-default", "x": 0, "y": 0, "w": 10, "h": 6},
            {"i": "favorites-default", "x": 0, "y": 6, "w": 5, "h": 6},
            {"i": "default-all-collections", "x": 5, "y": 6, "w": 5, "h": 6},
        ],
        "sm": [
            {"i": "recent-assets-default", "x": 0, "y": 0, "w": 1, "h": 6},
            {"i": "favorites-default", "x": 0, "y": 6, "w": 1, "h": 6},
            {"i": "default-all-collections", "x": 0, "y": 12, "w": 1, "h": 6},
        ],
    },
}
