import { describe, it, expect, beforeEach } from "vitest";
import {
  transformResultsToClipMode,
  isClipAsset,
  getClipDisplayName,
  getClipTimeRange,
  getClipSegment,
  getCollectionItemDisplayName,
  formatClipBoundaryLabel,
  getOriginalAssetId,
  clearTransformationCache,
  detectModelVersionFromResults,
} from "./clipTransformation";
import { RANGE_SEPARATOR } from "./timecode";
import { createTestAsset, createVideoAssetWithClips } from "../test/factories";

beforeEach(() => {
  clearTransformationCache();
});

describe("isClipAsset", () => {
  it("returns false for a regular asset", () => {
    expect(isClipAsset(createTestAsset())).toBe(false);
  });

  it("returns true for an object with clipData and originalAssetId", () => {
    expect(isClipAsset({ clipData: {}, originalAssetId: "abc" })).toBe(true);
  });

  it("returns falsy for null/undefined", () => {
    expect(isClipAsset(null)).toBeFalsy();
    expect(isClipAsset(undefined)).toBeFalsy();
  });
});

describe("getOriginalAssetId", () => {
  it("returns InventoryID for regular assets", () => {
    const asset = createTestAsset({ InventoryID: "asset-123" });
    expect(getOriginalAssetId(asset)).toBe("asset-123");
  });

  it("extracts original ID from clip-style IDs", () => {
    const asset = { InventoryID: "asset-123_clip_0" };
    expect(getOriginalAssetId(asset)).toBe("asset-123");
  });

  it("returns originalAssetId for clip assets", () => {
    const clipAsset = {
      InventoryID: "asset-123_clip_0",
      clipData: { score: 0.9 },
      originalAssetId: "asset-123",
    };
    expect(getOriginalAssetId(clipAsset)).toBe("asset-123");
  });
});

describe("transformResultsToClipMode", () => {
  it("returns original results when not in semantic mode", () => {
    const assets = [createTestAsset(), createTestAsset()];
    const { results, totalClips } = transformResultsToClipMode(assets as any, false, "full");
    expect(results).toBe(assets);
    expect(totalClips).toBe(2);
  });

  it("returns original results when semantic mode is 'full'", () => {
    const assets = [createTestAsset()];
    const { results } = transformResultsToClipMode(assets as any, true, "full");
    expect(results).toBe(assets);
  });

  it("expands video clips into individual assets in clip mode", () => {
    const video = createVideoAssetWithClips(3);
    const { results, totalClips } = transformResultsToClipMode([video] as any, true, "clip");
    expect(totalClips).toBe(3);
    expect(results).toHaveLength(3);
  });

  it("sorts clips by score descending", () => {
    const video = createTestAsset({
      DigitalSourceAsset: {
        Type: "Video",
        MainRepresentation: {
          StorageInfo: { PrimaryLocation: { ObjectKey: { Name: "test.mp4" } } },
        },
      },
      clips: [
        { start: 0, end: 10, score: 0.3 },
        { start: 10, end: 20, score: 0.9 },
        { start: 20, end: 30, score: 0.6 },
      ] as any,
    });

    const { results } = transformResultsToClipMode([video] as any, true, "clip");
    const scores = results.map((r: any) => r.score);
    expect(scores).toEqual([0.9, 0.6, 0.3]);
  });

  it("treats image assets as single clips", () => {
    const image = createTestAsset({
      DigitalSourceAsset: {
        Type: "Image",
        MainRepresentation: {
          StorageInfo: { PrimaryLocation: { ObjectKey: { Name: "photo.jpg" } } },
        },
      },
    });

    const { results, totalClips } = transformResultsToClipMode([image] as any, true, "clip");
    expect(totalClips).toBe(1);
    expect(results).toHaveLength(1);
  });

  it("paginates clip results", () => {
    const video = createVideoAssetWithClips(5);
    const { results, totalClips } = transformResultsToClipMode([video] as any, true, "clip", {
      page: 1,
      pageSize: 2,
    });
    expect(totalClips).toBe(5);
    expect(results).toHaveLength(2);
  });

  it("handles page 2 pagination", () => {
    const video = createVideoAssetWithClips(5);
    const { results } = transformResultsToClipMode([video] as any, true, "clip", {
      page: 2,
      pageSize: 2,
    });
    expect(results).toHaveLength(2);
  });
});

describe("getClipDisplayName", () => {
  it("returns name for regular assets", () => {
    const asset = createTestAsset();
    const name =
      asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name;
    expect(getClipDisplayName(asset)).toBe(name);
  });

  it("appends timecode range for video clips with timecodes", () => {
    const clipAsset = {
      DigitalSourceAsset: {
        Type: "Video",
        MainRepresentation: {
          StorageInfo: { PrimaryLocation: { ObjectKey: { Name: "video.mp4" } } },
        },
      },
      clipData: {
        start_timecode: "00:01:00:00",
        end_timecode: "00:02:00:00",
      },
      originalAssetId: "abc",
      clipIndex: 0,
    };
    expect(getClipDisplayName(clipAsset)).toBe(
      `video.mp4 (00:01:00:00${RANGE_SEPARATOR}00:02:00:00)`
    );
  });

  it("formats seconds for clips without timecodes", () => {
    const clipAsset = {
      DigitalSourceAsset: {
        Type: "Video",
        MainRepresentation: {
          StorageInfo: { PrimaryLocation: { ObjectKey: { Name: "video.mp4" } } },
        },
      },
      clipData: { start: 65, end: 130 },
      originalAssetId: "abc",
      clipIndex: 0,
    };
    expect(getClipDisplayName(clipAsset)).toBe(`video.mp4 (01:05${RANGE_SEPARATOR}02:10)`);
  });
});

describe("getClipTimeRange", () => {
  const clipAsset = (clipData: Record<string, unknown>) => ({
    DigitalSourceAsset: {
      Type: "Video",
      MainRepresentation: {
        StorageInfo: { PrimaryLocation: { ObjectKey: { Name: "video.mp4" } } },
      },
    },
    clipData,
    originalAssetId: "abc",
    clipIndex: 0,
  });

  it("prefers the frame-accurate source timecodes", () => {
    expect(
      getClipTimeRange(
        clipAsset({
          start_timecode: "00:01:00:00",
          end_timecode: "00:02:00:00",
          start: 60,
          end: 120,
        })
      )
    ).toBe(`00:01:00:00${RANGE_SEPARATOR}00:02:00:00`);
  });

  it("falls back to the numeric seconds", () => {
    expect(getClipTimeRange(clipAsset({ start: 65, end: 130 }))).toBe(
      `01:05${RANGE_SEPARATOR}02:10`
    );
  });

  it("returns null for a whole asset", () => {
    expect(getClipTimeRange(createTestAsset())).toBeNull();
  });

  it("returns null when the clip carries no usable range", () => {
    expect(getClipTimeRange(clipAsset({}))).toBeNull();
    expect(getClipTimeRange(clipAsset({ start: 65 }))).toBeNull();
  });
});

describe("getClipSegment", () => {
  const clipAsset = (clipData: Record<string, unknown>, metadata?: unknown) => ({
    DigitalSourceAsset: {
      Type: "Video",
      MainRepresentation: {
        StorageInfo: { PrimaryLocation: { ObjectKey: { Name: "video.mp4" } } },
      },
    },
    ...(metadata ? { Metadata: metadata } : {}),
    clipData,
    originalAssetId: "abc",
    clipIndex: 0,
  });

  it("derives seconds from the timecode-only payload the search API returns", () => {
    // Regression: the previous guard required numeric start/end, which the API
    // never sends. Every real clip therefore produced no segment -- the bin
    // showed no range, and bulk download/add-to-collection silently fell back to
    // the whole asset.
    const segment = getClipSegment(
      clipAsset({ start_timecode: "00:00:56:00", end_timecode: "00:01:03:00", score: 0.57 })
    );
    expect(segment).toEqual({
      startTime: 56,
      endTime: 63,
      startTimecode: "00:00:56:00",
      endTimecode: "00:01:03:00",
    });
  });

  it("uses the asset's frame rate for a frame offset inside the timecode", () => {
    const segment = getClipSegment(
      clipAsset(
        { start_timecode: "00:00:01:12", end_timecode: "00:00:02:00" },
        { EmbeddedMetadata: { video: [{ FrameRate: "24.000" }] } }
      )
    );
    expect(segment?.startTime).toBeCloseTo(1.5, 5);
  });

  it("prefers numeric seconds when the payload carries them", () => {
    const segment = getClipSegment(
      clipAsset({ start: 10.25, end: 20.5, start_timecode: "00:00:11:00" })
    );
    expect(segment?.startTime).toBe(10.25);
    expect(segment?.endTime).toBe(20.5);
    // The source timecode is still carried through for frame-accurate boundaries.
    expect(segment?.startTimecode).toBe("00:00:11:00");
  });

  it("returns undefined for a whole asset", () => {
    expect(getClipSegment(createTestAsset())).toBeUndefined();
  });

  it("returns undefined for an inverted or zero-length range", () => {
    expect(
      getClipSegment(clipAsset({ start_timecode: "00:01:00:00", end_timecode: "00:00:30:00" }))
    ).toBeUndefined();
    expect(
      getClipSegment(clipAsset({ start_timecode: "00:01:00:00", end_timecode: "00:01:00:00" }))
    ).toBeUndefined();
  });

  it("returns undefined when a timecode is missing, blank or unparseable", () => {
    expect(getClipSegment(clipAsset({ start_timecode: "00:00:56:00" }))).toBeUndefined();
    expect(
      getClipSegment(clipAsset({ start_timecode: "  ", end_timecode: "00:01:03:00" }))
    ).toBeUndefined();
    expect(
      getClipSegment(clipAsset({ start_timecode: "junk", end_timecode: "00:01:03:00" }))
    ).toBeUndefined();
  });
});

describe("formatClipBoundaryLabel", () => {
  it("formats a boundary with both ends as a range", () => {
    expect(formatClipBoundaryLabel({ startTime: "00:01:00:00", endTime: "00:02:00:00" })).toBe(
      `00:01:00:00${RANGE_SEPARATOR}00:02:00:00`
    );
  });

  it("returns null when the item is a whole asset rather than a clip", () => {
    expect(formatClipBoundaryLabel(undefined)).toBeNull();
    expect(formatClipBoundaryLabel(null)).toBeNull();
    expect(formatClipBoundaryLabel({})).toBeNull();
  });

  it("returns null for a half-open range rather than rendering a dangling separator", () => {
    expect(formatClipBoundaryLabel({ startTime: "00:01:00:00" })).toBeNull();
    expect(formatClipBoundaryLabel({ endTime: "00:02:00:00" })).toBeNull();
  });

  it("treats blank timecodes as absent", () => {
    expect(formatClipBoundaryLabel({ startTime: "  ", endTime: "00:02:00:00" })).toBeNull();
    expect(formatClipBoundaryLabel({ startTime: "00:01:00:00", endTime: "" })).toBeNull();
  });
});

describe("getCollectionItemDisplayName", () => {
  it("appends the timecode range for a collection clip", () => {
    expect(
      getCollectionItemDisplayName("video.mp4", {
        startTime: "00:01:00:00",
        endTime: "00:02:00:00",
      })
    ).toBe(`video.mp4 (00:01:00:00${RANGE_SEPARATOR}00:02:00:00)`);
  });

  it("matches the getClipDisplayName format so clips read alike everywhere", () => {
    const clipAsset = {
      DigitalSourceAsset: {
        Type: "Video",
        MainRepresentation: {
          StorageInfo: { PrimaryLocation: { ObjectKey: { Name: "video.mp4" } } },
        },
      },
      clipData: { start_timecode: "00:01:00:00", end_timecode: "00:02:00:00" },
      originalAssetId: "abc",
      clipIndex: 0,
    };
    expect(
      getCollectionItemDisplayName("video.mp4", {
        startTime: "00:01:00:00",
        endTime: "00:02:00:00",
      })
    ).toBe(getClipDisplayName(clipAsset));
  });

  it("returns the bare name for a whole-asset item", () => {
    expect(getCollectionItemDisplayName("video.mp4")).toBe("video.mp4");
    expect(getCollectionItemDisplayName("video.mp4", {})).toBe("video.mp4");
  });

  it("distinguishes two clips taken from the same asset", () => {
    const first = getCollectionItemDisplayName("video.mp4", {
      startTime: "00:00:05:00",
      endTime: "00:00:10:00",
    });
    const second = getCollectionItemDisplayName("video.mp4", {
      startTime: "00:00:20:00",
      endTime: "00:00:25:00",
    });
    expect(first).not.toBe(second);
  });
});

describe("detectModelVersionFromResults", () => {
  it("returns undefined for empty results", () => {
    expect(detectModelVersionFromResults([])).toBeUndefined();
  });

  it("detects model version from clip assets", () => {
    const asset = {
      clipData: { model_version: "3.0" },
      originalAssetId: "abc",
    };
    expect(detectModelVersionFromResults([asset])).toBe("3.0");
  });

  it("detects model version from clips array", () => {
    const asset = {
      clips: [{ model_version: "2.7", score: 0.5 }],
    };
    expect(detectModelVersionFromResults([asset])).toBe("2.7");
  });
});
