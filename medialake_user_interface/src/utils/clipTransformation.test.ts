import { describe, it, expect, beforeEach } from "vitest";
import {
  transformResultsToClipMode,
  isClipAsset,
  getClipDisplayName,
  getOriginalAssetId,
  clearTransformationCache,
  detectModelVersionFromResults,
} from "./clipTransformation";
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
    expect(getClipDisplayName(clipAsset)).toBe("video.mp4 (00:01:00:00 - 00:02:00:00)");
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
    expect(getClipDisplayName(clipAsset)).toBe("video.mp4 (1:05 - 2:10)");
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
