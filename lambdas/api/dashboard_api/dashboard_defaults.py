"""Default layout configuration and widget constraints."""

# Widget type constraints for validation
WIDGET_CONSTRAINTS = {
    "favorites": {
        "defaultSize": {"w": 6, "h": 4},
        "minSize": {"w": 3, "h": 2},
        "maxSize": {"w": 12, "h": 8},
    },
    "collections": {
        "defaultSize": {"w": 6, "h": 4},
        "minSize": {"w": 3, "h": 2},
        "maxSize": {"w": 12, "h": 8},
    },
    "recent-assets": {
        "defaultSize": {"w": 12, "h": 4},
        "minSize": {"w": 4, "h": 2},
        "maxSize": {"w": 12, "h": 8},
    },
}

# Default layout configuration with 4 widgets
DEFAULT_LAYOUT = {
    "layoutVersion": 1,
    "widgets": [
        {"id": "favorites-default", "type": "favorites", "config": {}},
        {
            "id": "my-collections-default",
            "type": "collections",
            "config": {"viewType": "my-collections"},
        },
        {
            "id": "shared-collections-default",
            "type": "collections",
            "config": {"viewType": "shared-with-me"},
        },
        {"id": "recent-assets-default", "type": "recent-assets", "config": {}},
    ],
    "layouts": {
        "lg": [
            {
                "i": "favorites-default",
                "x": 0,
                "y": 0,
                "w": 6,
                "h": 4,
                "minW": 3,
                "minH": 2,
                "maxW": 12,
                "maxH": 8,
            },
            {
                "i": "my-collections-default",
                "x": 6,
                "y": 0,
                "w": 6,
                "h": 4,
                "minW": 3,
                "minH": 2,
                "maxW": 12,
                "maxH": 8,
            },
            {
                "i": "shared-collections-default",
                "x": 0,
                "y": 4,
                "w": 6,
                "h": 4,
                "minW": 3,
                "minH": 2,
                "maxW": 12,
                "maxH": 8,
            },
            {
                "i": "recent-assets-default",
                "x": 6,
                "y": 4,
                "w": 6,
                "h": 4,
                "minW": 4,
                "minH": 2,
                "maxW": 12,
                "maxH": 8,
            },
        ],
        "md": [
            {"i": "favorites-default", "x": 0, "y": 0, "w": 3, "h": 4},
            {"i": "my-collections-default", "x": 3, "y": 0, "w": 3, "h": 4},
            {"i": "shared-collections-default", "x": 0, "y": 4, "w": 3, "h": 4},
            {"i": "recent-assets-default", "x": 3, "y": 4, "w": 3, "h": 4},
        ],
        "sm": [
            {"i": "favorites-default", "x": 0, "y": 0, "w": 1, "h": 4},
            {"i": "my-collections-default", "x": 0, "y": 4, "w": 1, "h": 4},
            {"i": "shared-collections-default", "x": 0, "y": 8, "w": 1, "h": 4},
            {"i": "recent-assets-default", "x": 0, "y": 12, "w": 1, "h": 4},
        ],
    },
}
