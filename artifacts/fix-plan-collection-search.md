# Fix Plan: `refactor/collection-search` Branch

> **Last reviewed:** Round 5 — 2026-04-27
> **Branch:** `refactor/collection-search` → `main`

## Dashboard

| Status            | Count  |
| ----------------- | ------ |
| ✅ Fixed          | **27** |
| ❌ Still Present  | **6**  |
| 📋 Accepted Risk  | **3**  |
| **Total tracked** | **36** |

**Estimated remaining effort:** ~3.5 hours (2 HIGH, 1 MEDIUM, 3 LOW)

---

## Table of Contents

- [Remaining Issues (7)](#remaining-issues)
  - [HIGH: Eventual consistency gap (#7)](#issue-7-high-eventual-consistency-gap)
  - [HIGH: Inline index mapping in create_os_index (#23)](#issue-23-high-inline-index-mapping-in-create_os_index)
  - [MEDIUM: Duplicate timestamp key (#29)](#issue-29-medium-duplicate-timestamp-key)
  - [LOW: Conditional imports (#15)](#issue-15-low-conditional-imports-inside-function-body)
  - [LOW: Silent except pass (#16)](#issue-16-low-silent-except-pass-on-permrule-deletes)
  - [LOW: Duplicated opensearch_client.py (#33)](#issue-33-low-opensearch_clientpy-duplicated)
  - [LOW: DecimalEncoder float precision (#34)](#issue-34-low-decimalencoder-float-precision)
- [Fixed Issues (27)](#fixed-issues)
- [Accepted Risks (3)](#accepted-risks)
- [Changelog](#changelog)

---

## Remaining Issues

### Issue 7 (HIGH): Eventual consistency gap

- **File:** [`collections_get.py`](lambdas/api/collections_api/handlers/collections_get.py:148)
- **Effort:** M
- [ ] Fixed

**Problem:** Writes go to DynamoDB, reads come from OpenSearch. Only an internal comment exists (`# --- OpenSearch only path — no DynamoDB fallback ---`). No user-facing documentation or response metadata about eventual consistency.

**Suggested fix:** Add metadata to the response:

```python
"meta": {
    "dataSource": "opensearch",
    "consistency": "eventual",
    "page": page,
    "pageSize": page_size,
    "totalResults": total_results,
}
```

And add a note to the API documentation (`assets/docs/collections-api.md`).

---

### Issue 23 (HIGH): Inline index mapping in create_os_index

- **File:** [`create_os_index/index.py`](lambdas/back_end/create_os_index/index.py:839)
- **Effort:** M
- [ ] Fixed

**Problem:** Full inline copy of collections index mapping at lines 839-873. The shared JSON file exists at [`lambdas/sync/collections_index_mapping.json`](lambdas/sync/collections_index_mapping.json) but `create_os_index` does not load from it. Only a WARNING comment acknowledges the duplication.

**Suggested fix:** Load the mapping from the shared JSON file:

```python
import json
from pathlib import Path

def _load_collections_mapping():
    mapping_path = Path(__file__).parent.parent.parent / "sync" / "collections_index_mapping.json"
    with open(mapping_path) as f:
        return json.load(f)

# Replace the inline collections_payload dict with:
collections_payload = _load_collections_mapping()
```

Alternatively, if Lambda packaging makes cross-directory imports difficult, copy the JSON file into the `create_os_index` directory during CDK bundling.

---

### Issue 29 (MEDIUM): Duplicate timestamp key

- **File:** [`create_os_index/index.py`](lambdas/back_end/create_os_index/index.py:394)
- **Effort:** S
- [ ] Fixed

**Problem:** `"timestamp": {"type": "date"}` appears at line 394 (COMMON FIELDS) and again at line 432 (LEGACY FIELDS). Python silently overwrites — the last wins. A documentation comment exists but the duplicate was not removed.

**Suggested fix:** Remove the duplicate at line 432:

```python
# LEGACY FIELDS section — delete this line:
# "timestamp": {"type": "date"},  ← REMOVE (duplicate of line 394)
```

---

### Issue 15 (LOW): Conditional imports inside function body

- **File:** [`collections_get.py`](lambdas/api/collections_api/handlers/collections_get.py:127)
- **Effort:** S
- [ ] Fixed

**Problem:** `import boto3` and `from collection_groups_utils import get_collection_ids_by_group_ids` at lines 127-128 inside the function body.

**Suggested fix:** Move to top of file:

```python
# At top of file, with other imports:
import boto3
from collection_groups_utils import get_collection_ids_by_group_ids
```

---

### Issue 16 (LOW): Silent `except: pass` on PERM#/RULE# deletes

- **File:** [`collections_ID_delete.py`](lambdas/api/collections_api/handlers/collections_ID_delete.py:119)
- **Effort:** S
- [ ] Fixed

**Problem:** `except Exception: pass` at lines 119 and 127 silently swallows errors when deleting permission/rule records. Could leave orphaned records.

**Suggested fix:** Add logging:

```python
except Exception as e:
    logger.warning("Failed to delete PERM# records for collection",
                   extra={"collection_id": collection_id, "error": str(e)})
```

---

### Issue 33 (LOW): opensearch_client.py duplicated

- **Files:** [`collections_sync/opensearch_client.py`](lambdas/sync/collections_sync/opensearch_client.py) and [`collections_backfill/opensearch_client.py`](lambdas/sync/collections_backfill/opensearch_client.py)
- **Effort:** M
- [ ] Fixed

**Problem:** ~240-line files are near-identical, duplicated between sync and backfill. Any bug fix must be applied to both.

**Suggested fix:** Extract to `lambdas/sync/shared_opensearch_client.py` and import from both:

```python
# In both index.py files:
from shared_opensearch_client import get_opensearch_client, bulk_index_with_retry, ...
```

Or package as a Lambda Layer.

---

### Issue 34 (LOW): DecimalEncoder float precision

- **File:** [`opensearch_client.py`](lambdas/sync/collections_sync/opensearch_client.py:27)
- **Effort:** S
- [ ] Fixed

**Problem:** `return int(obj) if obj == int(obj) else float(obj)` — non-integer Decimals are converted to `float`, which can lose precision.

**Suggested fix:**

```python
if obj == int(obj):
    return int(obj)
return str(obj)  # Preserve precision for fractional values
```

---

## Fixed Issues

<details>
<summary>27 issues resolved across 5 review rounds (click to expand)</summary>

### Backend API — Fixed (15)

| #   | Severity | Issue                                                       | Fixed In |
| --- | -------- | ----------------------------------------------------------- | -------- |
| 1   | CRITICAL | Auth check added in `collections_get.py:37`                 | Round 4  |
| 2   | CRITICAL | ValueError catch for page/pageSize at line 47               | Round 4  |
| 3   | CRITICAL | Regex validation on metadata filter keys                    | Round 4  |
| 4   | HIGH     | PATCH authorization — ownership check at line 65            | Round 4  |
| 5   | HIGH     | Dead code `_model_to_dict()` removed                        | Round 4  |
| 6   | HIGH     | Deep pagination capped: `pageSize≤200` + model validator    | Round 4  |
| 8   | MEDIUM   | `create_error_response` returns Powertools `Response`       | Round 4  |
| 9   | MEDIUM   | Index env vars documented as intentionally separate         | Round 4  |
| 10  | MEDIUM   | Duplicate `get_opensearch_client()` removed                 | Round 4  |
| 11  | MEDIUM   | Query body moved to DEBUG, INFO has safe fields only        | Round 4  |
| 12  | MEDIUM   | Recursive delete capped at `MAX_DELETE_DEPTH=20`            | Round 4  |
| 13  | MEDIUM   | Parent validated before transaction with DoesNotExist catch | Round 4  |
| 14  | MEDIUM   | GET by ID checks isPublic/ownerId/sharedWithUserIds         | Round 4  |
| 17  | LOW      | `search_groups()` docstring clarifies intentional omission  | Round 5  |
| 18  | LOW      | Unused `current_timestamp` parameter removed                | Round 4  |

### Sync/Infrastructure — Fixed (12)

| #   | Severity | Issue                                              | Fixed In |
| --- | -------- | -------------------------------------------------- | -------- |
| 19  | LOW      | Dead code files confirmed non-existent             | Round 2  |
| 20  | CRITICAL | OpenSearch client 45-min TTL credential cache      | Round 2  |
| 21  | CRITICAL | PERM# 404 raises DocumentNotFoundError → retry     | Round 2  |
| 22  | CRITICAL | Create path uses safe `create_index_if_not_exists` | Round 2  |
| 24  | HIGH     | Backfill uses `bulk_index_with_retry()`            | Round 2  |
| 25  | HIGH     | Document transformers unified                      | Round 2  |
| 26  | MEDIUM   | Unused SQS_URL removed                             | Round 2  |
| 27  | MEDIUM   | Jitter added to retry delays                       | Round 2  |
| 30  | MEDIUM   | `recreate_index` gated behind env var              | Round 2  |
| 31  | MEDIUM   | `_ensure_index_exists` failure raises RuntimeError | Round 2  |
| 35  | LOW      | `__init__.py` added to backfill directory          | Round 2  |

</details>

---

## Accepted Risks

| #   | Issue                         | Rationale                                                                                             |
| --- | ----------------------------- | ----------------------------------------------------------------------------------------------------- |
| 28  | `StartingPosition.LATEST`     | Documented at `api_gateway_collections.py:459`. Backfill lambda covers the gap on initial deployment. |
| 32  | Async backfill hides failures | Documented at `collections_backfill/index.py:293`. CloudWatch alarm on DLQ depth provides monitoring. |
| 36  | DLQ queue policy SourceArn    | Same-account IAM should work. Warrants integration test but not a blocker.                            |

---

## Changelog

| Round | Date       | Result                                                  |
| ----- | ---------- | ------------------------------------------------------- |
| 1     | 2026-04-26 | Initial review: 36 issues found                         |
| 2     | 2026-04-26 | Re-review: 12 sync/infra issues fixed, 24 remaining     |
| 3     | 2026-04-26 | Re-review: 0 additional fixes, 24 remaining             |
| 4     | 2026-04-26 | Re-review: 14 backend API issues fixed, 8 remaining     |
| 5     | 2026-04-27 | Re-review: 1 additional fix (Issue 17), **7 remaining** |
