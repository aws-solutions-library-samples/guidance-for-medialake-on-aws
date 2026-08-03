# Pipeline Output Packaging (Execution Groups)

Users can select multiple assets in the bin, run a manual-trigger pipeline
over all of them, and get the pipeline's output files back as a single zip
download when the last execution finishes.

This document explains how the outputs are discovered, so pipeline and node
authors know what their nodes must do to participate.

## How it works

1. **Submit** — the bin's _Run pipeline_ dialog has a checkbox,
   _Package outputs for download when finished_. With it checked, the UI sends
   a `group` object on `POST /pipelines/{pipelineId}/trigger`.
2. **Group key** — the API creates a group record and stamps a shared
   `group_id` into every asset's `params`. Nodes never read it; it simply
   rides along in the execution input.
3. **Baseline snapshot** — at submit time the API records which derived
   representations each asset already has. This is what makes "new output"
   meaningful.
4. **Fan-in** — as each execution reaches a terminal state, the executions
   event processor counts it against the group. When every member has
   resolved, the group flips to a terminal status.
5. **Packaging** — a finalizer resolves the group's outputs, creates a normal
   bulk-download job for them, and the existing download notification
   delivers the zip link.

## What counts as an output

> **An output is any derived representation that appears on the asset during
> the run and was not there when the group was submitted.**

This rule is deliberately purpose-agnostic, so every pipeline behaves the
same way. A reframed rendition, a proxy, a transcode, an extracted still, a
generated audio track — if the pipeline recorded it on the asset, it gets
packaged. No per-pipeline configuration, and nothing reframe-specific.

Only representations from executions that **succeeded** are packaged. If some
members failed, the group still packages what the successful ones produced.

## What a node must do to participate

Record the file it produced as a derived representation on the asset, the same
way the existing nodes do:

```python
representation = {
    "ID": f"{asset_id}:smartcrop:9-16",   # stable, unique per output
    "Type": "Video",
    "Format": "MP4",
    "Purpose": "smartcrop",               # free-form label
    "StorageInfo": {
        "PrimaryLocation": {
            "Bucket": out_bucket,
            "ObjectKey": {"FullPath": output_key},
            "FileInfo": {"Size": size_in_bytes},
            "Provider": "aws",
            "Status": "active",
            "StorageType": "s3",
        }
    },
}
```

Requirements for packaging to pick it up:

- **`ID` must be unique per output.** IDs are how new representations are told
  apart from pre-existing ones, and how duplicates are removed. Reusing an ID
  that already existed on the asset makes the output invisible to packaging.
- **`StorageInfo.PrimaryLocation` must carry `Bucket` and
  `ObjectKey.FullPath`.** Entries without both are skipped.
- **`FileInfo.Size`** should be set. It decides whether the file is zipped or
  delivered as an individual presigned URL; a missing size is treated as 0.
- **Write the representation before the execution succeeds.** Packaging is
  triggered by execution completion, so anything recorded afterwards is missed.
  Pipelines that poll an external job (MediaConvert, Bedrock, Transcribe)
  should record the representation in the status-check step that observes
  completion, as `check_media_convert_status` does.

A node that writes a file to S3 but never records a representation produces
nothing for packaging to find. In that case the group finishes with
`packagingSkippedReason = NO_ARTIFACTS_FOUND` and a CloudWatch warning that
points back to this document.

## Narrowing what gets packaged

By default every new representation is packaged. To restrict it, pass
`purposes` on the request:

```json
POST /pipelines/{pipelineId}/trigger
{
  "assets": [
    { "inventory_id": "…", "params": { "aspect_ratio": "9:16" } }
  ],
  "group": {
    "package": true,
    "purposes": ["smartcrop"],
    "name": "Vertical cuts for launch"
  }
}
```

- `package` (default `true`) — set `false` to group executions for tracking
  without producing a download.
- `purposes` (default: all) — only representations whose `Purpose` matches are
  packaged. Useful when a pipeline emits both a deliverable and incidental
  artifacts such as thumbnails.
- `name` — label shown in the download notification.

## Backwards compatibility

The `group` object is optional. Requests without it behave exactly as before:
one independent execution per asset, no group record, no packaging. Both the
current `assets` body and the legacy `inventory_ids` body are unchanged.

## Where things live

| Piece                              | Location                                                              |
| ---------------------------------- | --------------------------------------------------------------------- |
| Group submit + baseline snapshot   | `lambdas/api/pipelines/trigger_pipeline/`                             |
| Member counting / group completion | `lambdas/back_end/pipelines_executions_event_processor/`              |
| Artifact resolution + packaging    | `lambdas/back_end/pipeline_group_finalizer/`                          |
| Stale group timeout                | `lambdas/back_end/pipeline_group_sweeper/`                            |
| Group + member records             | `{prefix}-pipelines-groups-{env}` DynamoDB table                      |
| Zip + delivery                     | existing bulk-download workflow (`lambdas/api/assets/download/bulk/`) |

## Group record reference

`{prefix}-pipelines-groups-{env}`:

| Item   | Key                                      | Contents                                                                                                                                                  |
| ------ | ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Group  | `PK=GROUP#{id}`, `SK=META`               | status, `expectedCount` / `completedCount` / `failedCount` / `resolvedCount`, package config, `packagingJobId`, `packagingSkippedReason`, `timedOut`, TTL |
| Member | `PK=GROUP#{id}`, `SK=EXEC#{executionId}` | `inventoryId`, run `params`, `baselineRepIds`, terminal status, `countedAt`                                                                               |

Statuses: `OPEN` → `COMPLETED` (all succeeded), `COMPLETED_WITH_FAILURES`
(mixed), or `FAILED` (none succeeded). Groups whose executions never report a
terminal state are timed out by the sweeper after `GROUP_TIMEOUT_HOURS`
(default 24) and still package whatever completed.

On completion the finalizer publishes a `Pipeline Group Completed` event
(source `medialake.pipeline`) to the pipelines event bus, carrying
`groupId`, `pipelineId`, counts, `allSucceeded`, `packagingJobId`, and
`timedOut` — so automations can react to a finished group.
