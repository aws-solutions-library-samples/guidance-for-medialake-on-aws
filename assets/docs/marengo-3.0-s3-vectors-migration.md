# Upgrading to Marengo 3.0 with S3 Vectors

This guide walks through upgrading an existing MediaLake deployment from
TwelveLabs **Marengo 2.7** (1024‑dimension) to **Marengo 3.0** (512‑dimension)
embeddings when using the **S3 Vectors** store. Existing embeddings are **not**
converted — they are regenerated from the source assets with the 3.0 pipelines.

## Table of Contents

- [Overview](#overview)
- [Why a Migration Is Required](#why-a-migration-is-required)
- [Prerequisites](#prerequisites)
- [Step 1 — Deploy the 3.0 Vector Pipelines](#step-1--deploy-the-30-vector-pipelines)
- [Step 2 — Recreate the S3 Vector Index](#step-2--recreate-the-s3-vector-index)
- [Step 3 — Select the 3.0 Provider](#step-3--select-the-30-provider)
- [Step 4 — Re-ingest Existing Assets](#step-4--re-ingest-existing-assets)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [References](#references)

## Overview

TwelveLabs Marengo 3.0 supersedes 2.7 on Amazon Bedrock. The key differences
that affect MediaLake:

| | Marengo 2.7 | Marengo 3.0 |
| --- | --- | --- |
| Model ID | `twelvelabs.marengo-embed-2-7-v1:0` | `twelvelabs.marengo-embed-3-0-v1:0` |
| Embedding dimension | 1024 | 512 |
| Request schema | flat | nested (per `inputType`) |

MediaLake's invoke, results, and S3 vector‑store Lambdas already handle both
model versions automatically. The migration is therefore primarily about
**vector storage**: the S3 Vectors index dimension changes from 1024 to 512.

> [!IMPORTANT]
> Embeddings created with Marengo 2.7 are **not** compatible with 3.0. All
> embeddings must be regenerated. There is no in-place conversion.

## Why a Migration Is Required

An S3 Vectors index is created with a **fixed dimension that is immutable after
creation**. A deployment originally provisioned for 2.7 has its `media-vectors`
index created at 1024 dimensions. A 3.0 pipeline produces 512‑dimension vectors,
so writes to the existing index fail with:

```
ValidationException ... vector must have length 1024, but has length 512
```

Migrating means recreating the index at 512 dimensions and regenerating all
vectors with the 3.0 pipelines.

## Prerequisites

- AWS CLI v2 configured with credentials for the target account/region.
- `jq` installed (used by the backfill script).
- Permissions for: `s3vectors:*`, `states:StartExecution`, `dynamodb:Scan`,
  and CloudFormation/CDK deploy permissions.
- Confirm you are operating against the intended (ideally **non-production**)
  environment. The index deletion in Step 2 is destructive.

> [!WARNING]
> This procedure **permanently deletes all existing 2.7 vectors**. In `prod`
> the S3 Vector bucket and index use a `RETAIN` removal policy as a safeguard;
> deletion is a deliberate manual action. Do not proceed in production without
> an explicit migration plan and sign-off.

## Step 1 — Deploy the 3.0 Vector Pipelines

The 3.0 S3 Vectors pipeline definitions live in the pipeline library:

```
pipeline_library/Semantic Search/TwelveLabs/Bedrock/S3 Vectors/
  TwelveLabs Bedrock Marengo 3.0 Video Embedding to S3 Vectors.json
  TwelveLabs Bedrock Marengo 3.0 Image Embedding to S3 Vectors.json
  TwelveLabs Bedrock Marengo 3.0 Audio Embedding to S3 Vectors.json
```

These are **library templates** — they are imported through the UI, not
auto-deployed by the stack (only `Default Pipelines/` is auto-deployed).

1. Open the MediaLake UI → **Settings → Pipelines**.
2. Open the action menu → **Import**.
3. Upload the desired pipeline JSON (start with the Video pipeline).
4. Save and deploy the pipeline.

> [!NOTE]
> The embedding pipeline is triggered by completion of the **Default Video
> Pipeline** (it listens for `pipelineName: "Default Video Pipeline"`,
> `pipelineStatus: "Completed"`), not by raw S3 uploads. The asset must already
> be ingested with a generated **proxy** representation.

If your code base still defaults the vector dimension to 1024, update it to 512
before deploying and redeploy the stack. The relevant default lives in
`medialake_stacks/base_infrastructure.py` (the `S3VectorCluster` instantiation).

## Step 2 — Recreate the S3 Vector Index

The index dimension is immutable, so the 1024‑dimension index must be deleted
and recreated at 512. Two paths are available — choose one.

Identify the vector bucket and index first, then export them as shell variables
so the rest of the commands can be copied verbatim. The bucket name follows the
pattern `<resource_prefix>-vectors-<account>-<region>-<environment>`; the
default index name is `media-vectors`.

```bash
# Set once, reused by every command below
export VECTOR_BUCKET="<resource_prefix>-vectors-<account>-<region>-<environment>"
export INDEX_NAME="media-vectors"

# List vector buckets and confirm the current index dimension
aws s3vectors list-vector-buckets
aws s3vectors list-indexes --vector-bucket-name "$VECTOR_BUCKET"
aws s3vectors get-index \
  --vector-bucket-name "$VECTOR_BUCKET" \
  --index-name "$INDEX_NAME"          # confirm dimension == 1024

# Delete the 1024-dimension index (DESTRUCTIVE — removes all 2.7 vectors)
aws s3vectors delete-index \
  --vector-bucket-name "$VECTOR_BUCKET" \
  --index-name "$INDEX_NAME"
```

### Option A — Redeploy the stack (recommended)

After deleting the index, redeploy so CloudFormation recreates it at 512 and the
infrastructure template stays consistent with the live resource.

```bash
cdk deploy <your-stack(s)>

# Verify the index was recreated at 512
aws s3vectors get-index \
  --vector-bucket-name "$VECTOR_BUCKET" \
  --index-name "$INDEX_NAME"          # expect dimension == 512
```

> [!NOTE]
> If `cdk deploy` reports the index already exists, the manual delete has not
> finished propagating. Wait a moment and retry.

### Option B — No redeploy (manual or auto-create)

A redeploy is not strictly required. The `s3_vector_store` Lambda derives the
index dimension from the **actual embedding length** at write time
(`dim = len(embedding_vector)`), and creates the index only if it is missing. It
does **not** read a configured dimension. So after deleting the index you can
either let the first 3.0 pipeline run recreate it, or create it explicitly:

```bash
# Option B1: create it now, matching the CDK construct's settings
aws s3vectors create-index \
  --vector-bucket-name "$VECTOR_BUCKET" \
  --index-name "$INDEX_NAME" \
  --data-type float32 \
  --dimension 512 \
  --distance-metric cosine

# Option B2: skip this — the first 3.0 pipeline run (Step 4) creates
#            the index at 512 automatically on first write.

# Verify
aws s3vectors get-index \
  --vector-bucket-name "$VECTOR_BUCKET" \
  --index-name "$INDEX_NAME"          # expect dimension == 512
```

> [!WARNING]
> Option B leaves **CloudFormation drift**: the `CfnIndex` resource in
> `medialake_constructs/shared_constructs/s3_vectors.py` still declares the old
> dimension until the 512 code change is deployed. A later `cdk deploy` that
> changes that property will **replace** the index (delete + recreate), wiping
> vectors again. Use Option B for quick tests/sandboxes; land the code change
> and deploy (Option A) for anything you intend to keep.

If you prefer to keep 2.7 data alongside 3.0 (parallel run rather than a
cutover), use a **separate index name** for the 3.0 pipeline (set the store
node's **Index Name** to a new value such as `media-vectors-v3`). The store
Lambda auto-creates a missing index at the incoming vector's dimension. Note
that search must then be pointed at the matching index — a 512‑dimension query
cannot match a 1024‑dimension index.

## Step 3 — Select the 3.0 Provider

In the MediaLake UI → **Settings → System Settings → Search**, choose:

- **Provider**: *TwelveLabs Marengo Embed 3.0 on Bedrock* (512D)
- **Embedding store**: *S3 Vectors*

This determines the model and dimension used at **query time**. It must match
the dimension of the stored vectors (512), or searches will not return results.

## Step 4 — Re-ingest Existing Assets

Existing assets must have their embeddings regenerated with the 3.0 pipeline.
The `scripts/trigger_embedding_pipeline.sh` script starts one Step Functions
execution per asset, keyed by `InventoryID`. It supports two modes:

- **Explicit** (`--inventory-ids`): target one or a few specific assets — ideal
  for testing before a full run.
- **Discovery** (`--table`): scan the asset table by media type and backfill
  everything (optionally filtered by `--prefix`).

First, find the embedding pipeline's state machine ARN and the asset table name,
and export them so the commands below can be copied verbatim:

```bash
# Embedding pipeline state machine (name contains the pipeline you imported)
aws stepfunctions list-state-machines \
  --query "stateMachines[?contains(name,'Marengo') || contains(name,'Embedding')].[name,stateMachineArn]" \
  --output table

# Asset DynamoDB table
aws dynamodb list-tables \
  --query "TableNames[?contains(@,'asset-table')]" --output table

export SM_ARN="<EMBEDDING_PIPELINE_SM_ARN>"
export ASSET_TABLE="<ASSET_TABLE>"
```

### Test with a single asset (or a few) first

Before backfilling everything, validate the end-to-end flow against one or two
known assets. List a few candidate assets from the table to pick `InventoryID`s
(they have the form `asset:uuid:<id>`):

```bash
# List up to 10 Video assets as: <InventoryID> ; <S3 object key>
aws dynamodb scan \
  --table-name "$ASSET_TABLE" \
  --filter-expression "DigitalSourceAsset.#t = :mt" \
  --expression-attribute-names '{"#t":"Type"}' \
  --expression-attribute-values '{":mt":{"S":"Video"}}' \
  --projection-expression "InventoryID, StoragePath" \
  --max-items 10 \
  --output json \
| jq -r '.Items[]
    | "\(.InventoryID.S) | \((.StoragePath.S // "") | sub("^[^:]*:"; ""))"'
```

> [!TIP]
> A plain dry run of the discovery mode also lists every matching asset without
> starting anything — useful to eyeball the full set:
> `./scripts/trigger_embedding_pipeline.sh --table "$ASSET_TABLE" --state-machine-arn "$SM_ARN" --media-type Video`

Pick one or two `InventoryID`s from the output, then dry-run, then `--execute`:

```bash
# Dry run a single asset — lists it, starts nothing
./scripts/trigger_embedding_pipeline.sh \
  --state-machine-arn "$SM_ARN" \
  --inventory-ids asset:uuid:abc123-def456

# Looks right? Trigger it (you will be asked to confirm)
./scripts/trigger_embedding_pipeline.sh \
  --state-machine-arn "$SM_ARN" \
  --inventory-ids asset:uuid:abc123-def456 \
  --execute

# A few specific assets at once (comma-separated, no spaces)
./scripts/trigger_embedding_pipeline.sh \
  --state-machine-arn "$SM_ARN" \
  --inventory-ids asset:uuid:abc123,asset:uuid:def456 \
  --execute
```

Confirm the test asset(s) succeeded (see [Verification](#verification)) before
proceeding to the full backfill.

### Backfill all assets

Run a **dry run** first (the default) to see exactly what would be triggered:

```bash
./scripts/trigger_embedding_pipeline.sh \
  --table "$ASSET_TABLE" \
  --state-machine-arn "$SM_ARN" \
  --media-type Video
```

The dry run lists each matching asset's `InventoryID` and S3 object key and
starts nothing. When the list looks correct, add `--execute` (you will be asked
to confirm before any executions start):

```bash
# All ingested videos
./scripts/trigger_embedding_pipeline.sh \
  --table "$ASSET_TABLE" \
  --state-machine-arn "$SM_ARN" \
  --media-type Video \
  --execute

# Limit to a prefix of the S3 object key (bucket stripped)
./scripts/trigger_embedding_pipeline.sh \
  --table "$ASSET_TABLE" \
  --state-machine-arn "$SM_ARN" \
  --media-type Video \
  --prefix uploads/2024 \
  --execute
```

Useful options: `--media-type Video|Audio|Image`, `--prefix <key-prefix>`,
`--region <name>`, `--profile <name>`. Run with `--help` for the full list.

> [!NOTE]
> The pipeline reads the asset's **proxy** representation. Assets that were
> ingested but never produced a proxy will fail at the invoke step; re-run them
> through the Default Video Pipeline first so a proxy exists.

## Verification

1. **Index dimension** — `aws s3vectors get-index ...` reports `dimension: 512`.
2. **Executions succeeded** —
   ```bash
   aws stepfunctions list-executions \
     --state-machine-arn $SM_ARN \
     --max-results 10 \
     --query "executions[].[name,status]" --output table
   ```
   Expect `SUCCEEDED`.
3. **Vectors written at 512** — check the `s3_vector_store` Lambda logs:
   ```bash
   aws logs tail /aws/lambda/<s3_vector_store-fn> --since 1h --format short \
     | grep -iE "embedding_dimension|Created index|dim="
   ```
   Expect `embedding_dimension: 512`.
4. **Search returns results** — run a semantic search in the UI for content in a
   re-ingested asset.

## Troubleshooting

| Symptom | Likely cause | Resolution |
| --- | --- | --- |
| `vector must have length 1024, but has length 512` on store | Index still at 1024 | Recreate the index (Step 2), or point the 3.0 pipeline at a new 512D index |
| Search returns no results after migration | Provider/dimension mismatch | Select the 3.0 provider (Step 3) so queries are 512D against the 512D index |
| Execution fails at the invoke step | Asset has no proxy representation | Run the asset through the Default Video Pipeline first, then re-trigger |
| `cdk deploy` says index already exists | Delete not yet propagated | Wait and re-run `cdk deploy` |
| Backfill triggers a 2.7 pipeline by mistake | Wrong state machine ARN | Confirm the ARN belongs to the imported 3.0 pipeline |

### Finding the pipeline execution for an asset

To confirm an embedding pipeline actually ran for a given asset, you need to
locate its execution starting from the asset's `InventoryID`
(`asset:uuid:<uuid>`). There are two paths, depending on whether the execution
still lives in the projected executions table.

#### Option A — Scan the pipeline executions table by asset id

Executions are projected into the DynamoDB table
`${RESOURCE_PREFIX}-pipelines-executions-${ENVIRONMENT}` (e.g.
`medialake-pipelines-executions-dev`), defined in
`medialake_stacks/pipelines_executions_stack.py`. Each item is keyed by
`execution_id` (PK) + `start_time` (SK) and carries an `inventory_id` attribute
that matches the asset's `InventoryID`. The table has **no GSI on
`inventory_id`**, so the lookup is a `Scan` with a filter expression:

```bash
aws dynamodb scan \
  --table-name medialake-pipelines-executions-dev \
  --filter-expression "inventory_id = :inv" \
  --expression-attribute-values '{":inv":{"S":"asset:uuid:<uuid>"}}'
```

> [!NOTE]
> **90-day TTL.** Items have a `ttl` attribute and are auto-deleted ~90 days
> after they are written, so older runs will be gone from this table. The `ttl`
> value is a Unix epoch (seconds) — convert it (e.g. `date -r <ttl> -u`) to see
> when the record expires.

> [!WARNING]
> **Manual API-triggered executions may not populate `inventory_id`.** The event
> processor (`lambdas/back_end/pipelines_executions_event_processor/index.py`)
> only reads `inventory_id` from `$.detail.InventoryID` /
> `$.detail.detail.InventoryID` in the Step Functions input, whereas the manual
> trigger (`lambdas/api/pipelines/trigger_pipeline/index.py`) emits it at
> `$.item.inventory_id`. For manually triggered runs, fall back to Option B.

#### Option B — Scan across Step Functions state machine executions

Step Functions is the source of truth (full input/output, no dependence on the
projected table). There is no native "query by input value", so the pattern is:
list pipeline state machines → list executions → inspect each execution's input
for the asset id. Pipeline state machines are named
`${RESOURCE_PREFIX}_<sanitized-name>_pipeline` (see
`lambdas/api/pipelines/post_pipelines/sanitizers.py`) and are **not tagged**, so
filter on the `_pipeline` name suffix:

```bash
ASSET="asset:uuid:<uuid>"

for SM in $(aws stepfunctions list-state-machines \
    --query "stateMachines[?ends_with(name,'_pipeline')].stateMachineArn" --output text); do
  for EX in $(aws stepfunctions list-executions --state-machine-arn "$SM" \
      --max-results 100 --query "executions[].executionArn" --output text); do
    if aws stepfunctions describe-execution --execution-arn "$EX" \
        --query input --output text | grep -q "$ASSET"; then
      echo "MATCH: $EX"
    fi
  done
done
```

> [!TIP]
> If you know which pipeline you triggered, skip the outer loop and run
> `list-executions` against that single state machine ARN — much faster than
> sweeping all of them. Execution names are AWS-generated UUIDs and do **not**
> encode the asset id or a timestamp, so you must inspect each execution's
> `input`. `describe-execution` returns the full `input`, `output`, `status`,
> `startDate`, and `stopDate`.

## References

- [AWS — TwelveLabs Marengo Embed 3.0](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-marengo-3.html)
- [AWS — Migrate from Marengo 2.7 to 3.0](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-marengo-3.html#model-parameters-marengo-3-migration)
- `scripts/trigger_embedding_pipeline.sh` — embedding pipeline backfill script
