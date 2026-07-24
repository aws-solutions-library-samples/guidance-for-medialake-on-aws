# vector-audit

Audit an S3 Vectors library for embedding-metadata **filterability** — the
property MediaLake semantic search depends on.

For each asset it reports the embedding clip counts (visual / audio /
transcription) and whether an `embedding_option = visual` filter returns any
results:

- **ok** — filterable (search works for this asset)
- **BROKEN** — 0 filterable (the S3 Vectors metadata-filter bug: vectors written
  into a freshly created index can have `embedding_option` silently registered
  as non-filterable)

## Run it

No install step — [`uv`](https://docs.astral.sh/uv/) resolves dependencies and
runs the CLI in one command:

```bash
uv run --project tools/vector_audit vector-audit --bucket <vector-bucket> --names
```

Or from inside the tool directory:

```bash
cd tools/vector_audit
uv run vector-audit --bucket <vector-bucket> --names
```

## Common usage

```bash
# Audit the whole library (parallel probes), with filenames
uv run vector-audit --bucket medialake-vectors-123-us-east-1-dev --names

# Large library: sample 150 assets, higher concurrency, verdict only
uv run vector-audit --bucket ... --sample 150 --concurrency 16 --summary

# Troubleshoot specific assets
uv run vector-audit --bucket ... --inventory-ids asset:uuid:abc,asset:uuid:def

# Exact serial timing (probe_s is per-asset only when --concurrency 1)
uv run vector-audit --bucket ... --concurrency 1
```

## Options

| Option | Description |
| --- | --- |
| `--bucket` | **required** — S3 Vectors bucket to audit |
| `--index` | vector index (default: `media-vectors`) |
| `--inventory-ids` | comma-separated asset IDs (troubleshooting) |
| `--sample N` | probe a random sample of N assets |
| `--concurrency N` | parallel probe workers (default 8; 1 = serial) |
| `--names` | resolve each asset's filename (1 DynamoDB lookup/asset) |
| `--summary` | verdict only, skip the per-asset table |
| `--profile` / `--region` | AWS profile / region (region inferred from bucket) |
| `--asset-table` | override the asset table used by `--names` |

## Notes

- The `filterable` count is a **lower bound** (shown `>100` at the query cap),
  not an exact total — it comes from a top-K nearest-neighbor query. Only
  0-vs-nonzero is meaningful: a broken asset returns exactly 0, so any hit is a
  reliable PASS.
- Throttling is handled by boto3 adaptive retries; a probe that still fails
  after retries is reported as `ERROR` (never miscounted as BROKEN).
- Exit code is non-zero when any asset is BROKEN (CI-friendly).
