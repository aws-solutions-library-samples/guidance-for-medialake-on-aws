# Audio Track Selection — Video Proxy and Thumbnail Node

## Overview

The **Video Proxy and Thumbnail** node (used by the `Default Video Pipeline`) supports configurable, rule-based audio track selection when creating proxy videos via MediaConvert. This allows different users and pipelines to specify exactly which audio tracks from a multi-track source file should be combined into the output proxy.

If no rules are configured, the node falls back to MediaConvert's default behavior (`DefaultSelection: DEFAULT`), which selects the first/default audio track — preserving backward compatibility with existing pipelines.

## Why This Matters

Modern production video files (MXF, MP4, MOV) often contain many audio tracks in a "multi-mono" format — each track carrying a single channel (dialog, music, left surround, right surround, language dubs, etc.). Without explicit track selection, MediaConvert may pick a track that is missing dialog, music, or other expected audio, resulting in:

- Proxy videos that sound wrong or incomplete
- Poor-quality audio and transcript embeddings from downstream AI models (e.g., TwelveLabs Marengo)

## Configuration

In the Pipeline Editor, open the **Video Proxy and Thumbnail** node's settings (cog icon) and set the **Audio Track Selection Rules** field to a JSON array of rules.

### Rule Schema

Each rule has two fields:

| Field       | Type                          | Description                                                                          |
| ----------- | ----------------------------- | ------------------------------------------------------------------------------------ |
| `condition` | object                        | When this rule applies, based on the total number of audio tracks in the source file |
| `tracks`    | array of integers, or `"all"` | Which 1-based track numbers to select, or `"all"` to select every track              |

### Condition Types

| Pattern  | Example                | Matches when                                 |
| -------- | ---------------------- | -------------------------------------------- |
| Exact    | `{"exact": 1}`         | Source file has exactly 1 audio track        |
| Range    | `{"min": 2, "max": 7}` | Source file has 2–7 audio tracks (inclusive) |
| Min-only | `{"min": 8}`           | Source file has 8 or more audio tracks       |

Rules are evaluated in order — the **first matching rule wins**. If no rule matches, the node falls back to default behavior and logs a warning.

### Track Numbers

Track numbers are **1-based** (track 1 is the first audio track). All selected tracks are combined into a **single stereo AAC output track** in the proxy — regardless of how many tracks are selected.

## Examples

### User with known stereo downmix layout

This user's files follow a specific convention:

- 1 track → that's the mix
- 2–7 tracks → tracks 1 & 2 are the stereo left/right
- 8+ tracks → tracks 7 & 8 are the stereo downmix

```json
[
  { "condition": { "exact": 1 }, "tracks": [1] },
  { "condition": { "min": 2, "max": 7 }, "tracks": [1, 2] },
  { "condition": { "min": 8 }, "tracks": [7, 8] }
]
```

### Single-track source (no rules needed)

Leave the field empty — default behavior handles single-track files correctly.

### Select all tracks (use with caution)

The `"all"` wildcard selects every audio track in the file and mixes them into one stereo output. Useful when all tracks are complementary (e.g., multi-channel surround components with no duplicates or language dubs).

```json
[{ "condition": { "min": 1 }, "tracks": "all" }]
```

> **Warning:** Do not use `"all"` if the source file contains duplicate content across tracks (e.g., a 5.1 surround set alongside a stereo downmix) or multiple language dubs — the mixed output will be unusable.

## Validation

The rule engine validates your configuration before submitting any MediaConvert job:

- Track numbers must be ≥ 1
- Range conditions must have `min` ≤ `max`
- Each rule must specify either explicit track numbers or `"all"`
- Rules that can never be reached (shadowed by an earlier rule) are rejected with a clear error message — e.g., a `{"min": 7}` rule after a `{"min": 2}` rule with no upper bound would never match

If a matched rule references track numbers that don't exist in the source file (e.g., rule says tracks [10, 11] but the file only has 9 tracks), the pipeline **fails immediately** before submitting the MediaConvert job, with an error message identifying the rule and the out-of-bounds track numbers.

## Output

Regardless of how many input tracks are selected, the output proxy always contains **exactly one stereo audio track** (AAC, `CODING_MODE_2_0`, 44100 Hz). This ensures compatibility with the MediaLake web UI player and downstream AI embedding models.
