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

# Default layout configuration with 8 widgets
DEFAULT_LAYOUT = {
    "layoutVersion": 1,
    "widgets": [
        # Row 1: All Collections, Public Collections, Favorites
        {
            "id": "default-all-collections",
            "type": "collections",
            "config": {
                "viewType": "all",
                "sorting": {"sortBy": "name", "sortOrder": "asc"},
            },
        },
        {
            "id": "default-public-collections",
            "type": "collections",
            "config": {
                "viewType": "public",
                "sorting": {"sortBy": "name", "sortOrder": "asc"},
            },
        },
        {"id": "favorites-default", "type": "favorites", "config": {}},
        # Row 2: Private Collections, My Collections, Shared with Me
        {
            "id": "default-private-collections",
            "type": "collections",
            "config": {
                "viewType": "private",
                "sorting": {"sortBy": "name", "sortOrder": "asc"},
            },
        },
        {
            "id": "default-my-collections",
            "type": "collections",
            "config": {
                "viewType": "my-collections",
                "sorting": {"sortBy": "updatedAt", "sortOrder": "desc"},
            },
        },
        {
            "id": "default-shared-with-me",
            "type": "collections",
            "config": {
                "viewType": "shared-with-me",
                "sorting": {"sortBy": "updatedAt", "sortOrder": "desc"},
            },
        },
        # Row 3: My Shared Collections, Recent Assets
        {
            "id": "default-my-shared",
            "type": "collections",
            "config": {
                "viewType": "my-shared",
                "sorting": {"sortBy": "name", "sortOrder": "asc"},
            },
        },
        {"id": "recent-assets-default", "type": "recent-assets", "config": {}},
    ],
    "layouts": {
        "lg": [
            # Row 1
            {
                "i": "default-all-collections",
                "x": 0,
                "y": 0,
                "w": 4,
                "h": 4,
                "minW": 3,
                "minH": 2,
                "maxW": 12,
                "maxH": 8,
            },
            {
                "i": "default-public-collections",
                "x": 4,
                "y": 0,
                "w": 4,
                "h": 4,
                "minW": 3,
                "minH": 2,
                "maxW": 12,
                "maxH": 8,
            },
            {
                "i": "favorites-default",
                "x": 8,
                "y": 0,
                "w": 4,
                "h": 4,
                "minW": 3,
                "minH": 2,
                "maxW": 12,
                "maxH": 8,
            },
            # Row 2
            {
                "i": "default-private-collections",
                "x": 0,
                "y": 4,
                "w": 4,
                "h": 4,
                "minW": 3,
                "minH": 2,
                "maxW": 12,
                "maxH": 8,
            },
            {
                "i": "default-my-collections",
                "x": 4,
                "y": 4,
                "w": 4,
                "h": 4,
                "minW": 3,
                "minH": 2,
                "maxW": 12,
                "maxH": 8,
            },
            {
                "i": "default-shared-with-me",
                "x": 8,
                "y": 4,
                "w": 4,
                "h": 4,
                "minW": 3,
                "minH": 2,
                "maxW": 12,
                "maxH": 8,
            },
            # Row 3
            {
                "i": "default-my-shared",
                "x": 0,
                "y": 8,
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
                "y": 8,
                "w": 6,
                "h": 4,
                "minW": 4,
                "minH": 2,
                "maxW": 12,
                "maxH": 8,
            },
        ],
        "md": [
            {"i": "default-all-collections", "x": 0, "y": 0, "w": 5, "h": 4},
            {"i": "default-public-collections", "x": 5, "y": 0, "w": 5, "h": 4},
            {"i": "favorites-default", "x": 0, "y": 4, "w": 5, "h": 4},
            {"i": "default-private-collections", "x": 5, "y": 4, "w": 5, "h": 4},
            {"i": "default-my-collections", "x": 0, "y": 8, "w": 5, "h": 4},
            {"i": "default-shared-with-me", "x": 5, "y": 8, "w": 5, "h": 4},
            {"i": "default-my-shared", "x": 0, "y": 12, "w": 5, "h": 4},
            {"i": "recent-assets-default", "x": 5, "y": 12, "w": 5, "h": 4},
        ],
        "sm": [
            {"i": "default-all-collections", "x": 0, "y": 0, "w": 1, "h": 4},
            {"i": "default-public-collections", "x": 0, "y": 4, "w": 1, "h": 4},
            {"i": "favorites-default", "x": 0, "y": 8, "w": 1, "h": 4},
            {"i": "default-private-collections", "x": 0, "y": 12, "w": 1, "h": 4},
            {"i": "default-my-collections", "x": 0, "y": 16, "w": 1, "h": 4},
            {"i": "default-shared-with-me", "x": 0, "y": 20, "w": 1, "h": 4},
            {"i": "default-my-shared", "x": 0, "y": 24, "w": 1, "h": 4},
            {"i": "recent-assets-default", "x": 0, "y": 28, "w": 1, "h": 4},
        ],
    },
}
