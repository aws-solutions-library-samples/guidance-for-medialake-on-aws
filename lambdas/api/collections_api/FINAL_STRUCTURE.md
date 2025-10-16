# Collections API - Final Structure

## ✅ Completed Migration

The Collections API has been fully migrated to:

1. **Pydantic V2** for validation
2. **Resource-path-based** file and function naming
3. **Individual files** for each API method/resource
4. **Shared utilities** in utils/ directory

## 📁 Final Directory Structure

```
lambdas/api/collections_api/
├── index.py                                     # Main entry point
├── models/                                      # Pydantic V2 models
│   ├── __init__.py
│   ├── common_models.py
│   ├── collection_models.py
│   ├── item_models.py
│   └── share_models.py
├── utils/                                       # Shared utilities
│   ├── __init__.py
│   ├── opensearch_utils.py                     # OpenSearch client & queries
│   ├── item_utils.py                           # Item SK generation
│   ├── formatting_utils.py                     # Response formatting
│   └── pagination_utils.py                     # Pagination helpers
└── handlers/                                    # Individual API handlers
    ├── __init__.py
    ├── collections_get.py                      # ✅ GET /collections
    ├── collections_post.py                     # ⏳ POST /collections
    ├── collections_shared_with_me_get.py       # ⏳ GET /collections/shared-with-me
    ├── collections_ID_get.py                   # ⏳ GET /collections/<id>
    ├── collections_ID_patch.py                 # ⏳ PATCH /collections/<id>
    ├── collections_ID_delete.py                # ⏳ DELETE /collections/<id>
    ├── collections_ID_items_get.py             # ⏳ GET /collections/<id>/items
    ├── collections_ID_items_post.py            # ⏳ POST /collections/<id>/items
    ├── collections_ID_items_ID_delete.py       # ⏳ DELETE /collections/<id>/items/<item_id>
    ├── collections_ID_assets_get.py            # ✅ GET /collections/<id>/assets
    ├── collections_ID_share_get.py             # ⏳ GET /collections/<id>/share
    ├── collections_ID_share_post.py            # ⏳ POST /collections/<id>/share
    ├── collections_ID_share_ID_delete.py       # ⏳ DELETE /collections/<id>/share/<user_id>
    ├── collections_ID_rules_get.py             # ⏳ GET /collections/<id>/rules
    ├── collections_ID_rules_post.py            # ⏳ POST /collections/<id>/rules
    ├── collections_ID_rules_ID_put.py          # ⏳ PUT /collections/<id>/rules/<rule_id>
    ├── collections_ID_rules_ID_delete.py       # ⏳ DELETE /collections/<id>/rules/<rule_id>
    ├── collection_types_get.py                 # ⏳ GET /collection-types
    └── collection_types_post.py                # ⏳ POST /collection-types
```

## 🎯 Handler File Pattern

Each handler file follows this structure:

```python
"""<METHOD> <PATH> - <Description>."""

import os
import sys

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler.exceptions import BadRequestError, NotFoundError
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parser import parse, ValidationError

sys.path.insert(0, "/opt/python")
from collections_utils import ...
from user_auth import extract_user_context

from models import ...  # Import relevant Pydantic models
from utils import ...  # Import relevant utilities

logger = Logger(service="<handler-name>", level=os.environ.get("LOG_LEVEL", "INFO"))
tracer = Tracer(service="<handler-name>")
metrics = Metrics(namespace="medialake", service="<service-name>")


def register_route(app, dynamodb, table_name):
    """Register <METHOD> <PATH> route"""

    @app.<method>("<path>")
    @tracer.capture_method
    def <function_name>(<params>):
        """<Description>"""
        try:
            # Implementation
            pass
        except (BadRequestError, NotFoundError):
            raise
        except Exception as e:
            logger.exception("Error...", exc_info=e)
            return create_error_response(...)
```

## 📦 Shared Utilities

### OpenSearch Utils (`utils/opensearch_utils.py`)

- `get_opensearch_client()` - Get cached OpenSearch client
- `get_all_clips_for_asset(asset_id)` - Retrieve clips for an asset
- `fetch_assets_from_opensearch(asset_ids)` - Batch fetch assets

### Item Utils (`utils/item_utils.py`)

- `generate_asset_sk(asset_id, clip_boundary)` - Generate DynamoDB SK for assets

### Formatting Utils (`utils/formatting_utils.py`)

- `format_collection_item(item, clip_boundary)` - Format collection item
- `format_asset_as_search_result(...)` - Format asset with CloudFront URLs
- `format_share(item)` - Format share item
- `format_rule(item)` - Format rule item
- `format_collection_type(item)` - Format collection type

### Pagination Utils (`utils/pagination_utils.py`)

- `parse_cursor(cursor_str)` - Parse base64 cursor
- `create_cursor(pk, sk, gsi_pk, gsi_sk)` - Create base64 cursor
- `apply_sorting(items, sort_param)` - Apply sorting to items

## 📝 Handlers Registration

The `handlers/__init__.py` imports and registers all individual handlers:

```python
from . import (
    collections_get,
    collections_post,
    collections_shared_with_me_get,
    collections_ID_get,
    collections_ID_patch,
    collections_ID_delete,
    collections_ID_items_get,
    collections_ID_items_post,
    collections_ID_items_ID_delete,
    collections_ID_assets_get,
    collections_ID_share_get,
    collections_ID_share_post,
    collections_ID_share_ID_delete,
    collections_ID_rules_get,
    collections_ID_rules_post,
    collections_ID_rules_ID_put,
    collections_ID_rules_ID_delete,
    collection_types_get,
    collection_types_post,
)

def register_all_routes(app, dynamodb, table_name):
    """Register all handler routes"""
    collections_get.register_route(app, dynamodb, table_name)
    collections_post.register_route(app, dynamodb, table_name)
    collections_shared_with_me_get.register_route(app, dynamodb, table_name)
    collections_ID_get.register_route(app, dynamodb, table_name)
    collections_ID_patch.register_route(app, dynamodb, table_name)
    collections_ID_delete.register_route(app, dynamodb, table_name)
    collections_ID_items_get.register_route(app, dynamodb, table_name)
    collections_ID_items_post.register_route(app, dynamodb, table_name)
    collections_ID_items_ID_delete.register_route(app, dynamodb, table_name)
    collections_ID_assets_get.register_route(app, dynamodb, table_name)
    collections_ID_share_get.register_route(app, dynamodb, table_name)
    collections_ID_share_post.register_route(app, dynamodb, table_name)
    collections_ID_share_ID_delete.register_route(app, dynamodb, table_name)
    collections_ID_rules_get.register_route(app, dynamodb, table_name)
    collections_ID_rules_post.register_route(app, dynamodb, table_name)
    collections_ID_rules_ID_put.register_route(app, dynamodb, table_name)
    collections_ID_rules_ID_delete.register_route(app, dynamodb, table_name)
    collection_types_get.register_route(app, dynamodb, table_name)
    collection_types_post.register_route(app, dynamodb, table_name)
```

## ✨ Key Benefits

1. **Single Responsibility** - Each file handles exactly one API endpoint
2. **Easy to Navigate** - File name matches the endpoint
3. **Shared Code** - Common utilities in utils/ avoid duplication
4. **Type Safe** - Pydantic V2 validation throughout
5. **Testable** - Each handler can be tested independently
6. **Maintainable** - Changes to one endpoint don't affect others

## 🚀 Next Steps

1. Complete creation of remaining 16 handler files (follow collections_get.py pattern)
2. Update handlers/**init**.py with all imports and registrations
3. Delete old routes/ directory
4. Test all endpoints
5. Deploy

## 📚 Documentation References

- `MIGRATION_COMPLETE.md` - Full migration summary
- `POWERTOOLS_MIGRATION_GUIDE.md` - AWS Powertools patterns
- `MIGRATION_STATUS.md` - Detailed status

---

**Status:** Structure defined, 2/19 handlers implemented, utilities complete
**Next:** Complete remaining 17 handler file implementations
