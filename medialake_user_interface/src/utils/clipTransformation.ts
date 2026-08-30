import { type ImageItem, type VideoItem, type AudioItem } from "@/types/search/searchResults";
import {
  formatTimeRange,
  formatTimecodeRange,
  getAssetFrameRate,
  isValidTime,
  parseTimecode,
} from "@/utils/timecode";

type AssetItem = (ImageItem | VideoItem | AudioItem) & {
  DigitalSourceAsset: {
    Type: string;
  };
};

// Cache for transformed results to avoid re-computation
const transformationCache = new Map<string, AssetItem[]>();

// Generate a cache key based on the input parameters
function generateCacheKey(
  results: AssetItem[],
  isSemantic: boolean,
  semanticMode: "full" | "clip",
  pagination?: { page: number; pageSize: number }
): string {
  // Create a simple hash of the results array and parameters
  const resultIds = results.map((r) => r.InventoryID).join(",");
  const paginationKey = pagination ? `_p${pagination.page}_s${pagination.pageSize}` : "";
  return `${isSemantic}_${semanticMode}_${resultIds}${paginationKey}`;
}

interface ClipData {
  start_timecode?: string;
  end_timecode?: string;
  start?: number;
  end?: number;
  score?: number;
  embedding_option?: string;
  model_version?: string; // e.g., "3.0" for Marengo 3.0, "2.7" for Marengo 2.7
  model_provider?: string;
  model_name?: string;
}

type ClipAssetItem = AssetItem & {
  // Add clip-specific properties
  clipData: ClipData;
  originalAssetId: string;
  clipIndex: number;
  clips?: any; // Allow clips property override
};

/**
 * Transforms search results from asset-based to clip-based presentation
 * Each clip becomes its own asset card, ranked by score
 */
export function transformResultsToClipMode(
  results: AssetItem[],
  isSemantic: boolean,
  semanticMode: "full" | "clip",
  pagination?: {
    page: number;
    pageSize: number;
  }
): { results: AssetItem[]; totalClips: number } {
  // If not in semantic clip mode, return original results immediately
  if (!isSemantic || semanticMode !== "clip") {
    return { results, totalClips: results.length };
  }

  // Check cache first (only cache the full transformation, not paginated results)
  const fullCacheKey = generateCacheKey(results, isSemantic, semanticMode);
  let allClipAssets = transformationCache.get(fullCacheKey) as ClipAssetItem[] | undefined;

  if (!allClipAssets) {
    const startTime = performance.now();

    allClipAssets = [];

    // Extract all clips from all assets
    results.forEach((asset, assetIndex) => {
      const clips = (asset as any).clips as ClipData[] | undefined;
      const assetType = asset.DigitalSourceAsset?.Type || "Unknown";

      // For video and audio assets, process individual clips if available
      if (
        (assetType === "Video" || assetType === "Audio") &&
        clips &&
        Array.isArray(clips) &&
        clips.length > 0
      ) {
        clips.forEach((clip, clipIndex) => {
          // Only process clips that have a valid score for semantic search
          if (clip.score !== undefined && clip.score !== null) {
            // Create a new asset item for each clip
            const clipAsset: ClipAssetItem = {
              ...asset,
              // Generate unique ID for the clip
              InventoryID: `${asset.InventoryID}_clip_${clipIndex}`,
              // Use clip score if available, otherwise use asset score
              score: clip.score ?? asset.score ?? 0,
              // Store original clip data
              clipData: clip,
              originalAssetId: asset.InventoryID,
              clipIndex: clipIndex,
              // Override clips to contain only this specific clip
              clips: [clip],
            };

            allClipAssets!.push(clipAsset);
          }
        });
      }
      // For non-video/audio assets (Image), treat the entire asset as a "clip"
      else if (assetType === "Image") {
        const wholeAssetClip: ClipAssetItem = {
          ...asset,
          // Keep original ID for non-video assets
          InventoryID: asset.InventoryID,
          // Use asset score
          score: asset.score ?? 0,
          // Create dummy clip data for consistency
          clipData: {
            score: asset.score ?? 0,
          },
          originalAssetId: asset.InventoryID,
          clipIndex: 0,
          // No clips array for whole assets
          clips: undefined,
        };

        allClipAssets!.push(wholeAssetClip);
      }
      // For video/audio assets without clips, also treat as whole asset
      else if (assetType === "Video" || assetType === "Audio") {
        const wholeAssetClip: ClipAssetItem = {
          ...asset,
          InventoryID: asset.InventoryID,
          score: asset.score ?? 0,
          clipData: {
            score: asset.score ?? 0,
          },
          originalAssetId: asset.InventoryID,
          clipIndex: 0,
          // No clips array for whole assets
          clips: undefined,
        };

        allClipAssets!.push(wholeAssetClip);
      }
    });

    // Sort clips by score (highest first) - this is the expensive part
    allClipAssets.sort((a, b) => (b.score ?? 0) - (a.score ?? 0));

    // Debug: Show summary of asset types processed
    const assetTypeSummary = results.reduce(
      (acc, asset) => {
        const type = asset.DigitalSourceAsset?.Type || "Unknown";
        const hasClips = !!(asset as any).clips?.length;
        if (!acc[type]) acc[type] = { total: 0, withClips: 0 };
        acc[type].total++;
        if (hasClips) acc[type].withClips++;
        return acc;
      },
      {} as Record<string, { total: number; withClips: number }>
    );

    const endTime = performance.now();

    // Cache the result for future use
    transformationCache.set(fullCacheKey, allClipAssets);

    // Limit cache size to prevent memory leaks
    if (transformationCache.size > 10) {
      const firstKey = transformationCache.keys().next().value;
      transformationCache.delete(firstKey);
    }
  } else {
  }

  const totalClips = allClipAssets.length;

  // Apply pagination if provided
  if (pagination) {
    const { page, pageSize } = pagination;
    const startIndex = (page - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const paginatedClips = allClipAssets.slice(startIndex, endIndex);

    return { results: paginatedClips, totalClips };
  }

  // Return all clips if no pagination
  return { results: allClipAssets, totalClips };
}

/**
 * Checks if an asset is a clip-based asset (including whole assets treated as clips)
 */
export function isClipAsset(asset: any): asset is ClipAssetItem {
  return asset && typeof asset === "object" && "clipData" in asset && "originalAssetId" in asset;
}

/**
 * Gets the display name for a clip asset
 */
export function getClipDisplayName(asset: any): string {
  if (isClipAsset(asset)) {
    const originalName =
      asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name;
    const clipData = asset.clipData;
    const assetType = asset.DigitalSourceAsset?.Type || "Unknown";

    // For non-video assets or video assets without time markers, just return the name
    if (assetType !== "Video" || (!clipData.start_timecode && !clipData.start)) {
      return originalName;
    }

    // For video clips with time markers
    if (clipData.start_timecode && clipData.end_timecode) {
      const range = formatTimecodeRange(clipData.start_timecode, clipData.end_timecode);
      return range ? `${originalName} (${range})` : originalName;
    } else if (clipData.start !== undefined && clipData.end !== undefined) {
      // Same formatter as every other clip surface, so a clip discovered by
      // search reads identically to the same clip sitting in a collection or
      // the selection bin.
      const range = formatTimeRange(clipData.start, clipData.end);
      return range ? `${originalName} (${range})` : originalName;
    } else {
      return `${originalName} (Clip ${asset.clipIndex + 1})`;
    }
  }

  return asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name;
}

/**
 * A clip's time range as persisted on a collection item.
 *
 * Note this is a different shape from `ClipAssetItem.clipData`: search results carry
 * `clipData` plus `originalAssetId` (so `isClipAsset` recognises them), whereas a
 * collection item carries only `clipBoundary` with HH:MM:SS:FF timecodes. Collection
 * clips therefore never satisfy `isClipAsset`, which is why they need their own label
 * helper rather than reusing `getClipDisplayName`.
 */
export interface ClipBoundary {
  startTime?: string;
  endTime?: string;
}

/**
 * Formats a collection item's clip boundary as a range, or returns null when the item is
 * a whole asset rather than a clip.
 *
 * Returns null unless both ends are present: a half-open range would render as
 * "00:00:10:00 - " and read as though the data were truncated.
 *
 * Delegates to the shared timecode formatter so this range uses the same separator as the
 * selection bin, the add-to-collection modal and the collection table's Timecode column.
 */
export function formatClipBoundaryLabel(boundary?: ClipBoundary | null): string | null {
  return formatTimecodeRange(boundary?.startTime, boundary?.endTime);
}

/**
 * Display name for a collection item, appending the clip's timecode range when the item
 * is a clip.
 *
 * Without this, several clips taken from one asset all render under the same filename and
 * are indistinguishable on the collection page. The `name (start - end)` form matches
 * `getClipDisplayName` so clips read the same wherever they appear.
 */
export function getCollectionItemDisplayName(
  assetName: string,
  boundary?: ClipBoundary | null
): string {
  const range = formatClipBoundaryLabel(boundary);
  return range ? `${assetName} (${range})` : assetName;
}

/**
 * The display-ready time range for a search-result clip, or null when the asset
 * is not a clip (or carries no usable range).
 *
 * Prefers the source timecodes, which are frame-accurate, and falls back to the
 * numeric seconds. Exists so callers that need the range on its own -- a chip, a
 * table cell, the add-to-collection manifest -- don't have to re-derive it from
 * `getClipDisplayName`, which bakes it into a filename.
 */
export function getClipTimeRange(asset: any): string | null {
  if (!isClipAsset(asset)) return null;

  const clipData = asset.clipData;
  if (!clipData) return null;

  return (
    formatTimecodeRange(clipData.start_timecode, clipData.end_timecode) ??
    formatTimeRange(clipData.start, clipData.end)
  );
}

/**
 * The time range of a search-result clip, in the shape the selection bin uses.
 *
 * Returns undefined when the asset is not a clip, or carries no usable range.
 *
 * Both representations are returned when available: `startTime`/`endTime` in
 * seconds drive display and per-segment pipeline runs, while the original
 * `HH:MM:SS:FF` timecodes are preserved so `segmentToClipBoundary` can send
 * frame-accurate boundaries to the download and collection APIs rather than
 * re-deriving a second-accurate approximation.
 *
 * The seconds are derived from the timecodes when the payload has no numeric
 * ones -- which is the normal case. The search API returns clips as
 * `{start_timecode, end_timecode, score}` (see
 * collections_ID_assets_get.py and the OpenSearch clip documents), so a guard
 * requiring numeric `start`/`end` rejects every real clip: the bin then showed
 * no time range, and, because `segmentToClipBoundary` was never reached, a
 * bulk download or add-to-collection silently processed the whole asset instead
 * of the selected clip.
 *
 * `fps` is taken from the asset's embedded metadata so a frame offset inside the
 * timecode converts correctly; it falls back to DEFAULT_FPS when unknown.
 */
export function getClipSegment(asset: any):
  | {
      startTime: number;
      endTime: number;
      startTimecode?: string;
      endTimecode?: string;
    }
  | undefined {
  const clip = asset?.clipData;
  if (!clip) return undefined;

  const fps = getAssetFrameRate(asset);

  const startTimecode =
    typeof clip.start_timecode === "string" && clip.start_timecode.trim()
      ? clip.start_timecode.trim()
      : undefined;
  const endTimecode =
    typeof clip.end_timecode === "string" && clip.end_timecode.trim()
      ? clip.end_timecode.trim()
      : undefined;

  const startTime = typeof clip.start === "number" ? clip.start : parseTimecode(startTimecode, fps);
  const endTime = typeof clip.end === "number" ? clip.end : parseTimecode(endTimecode, fps);

  if (!isValidTime(startTime) || !isValidTime(endTime) || endTime <= startTime) {
    return undefined;
  }

  return { startTime, endTime, startTimecode, endTimecode };
}

/**
 * Gets the original asset ID from either a clip asset or regular asset
 * For clip assets, returns the originalAssetId property
 * For regular assets, returns the InventoryID
 * For clip IDs that follow the pattern "originalId_clip_N", extracts the original ID
 */
export function getOriginalAssetId(asset: any): string {
  // If it's a clip asset with originalAssetId property, use that
  if (isClipAsset(asset)) {
    return asset.originalAssetId;
  }

  // If the ID contains "_clip_", extract the original part
  if (typeof asset.InventoryID === "string" && asset.InventoryID.includes("_clip_")) {
    return asset.InventoryID.split("_clip_")[0];
  }

  // Otherwise, return the regular InventoryID
  return asset.InventoryID;
}

/**
 * Clears the transformation cache
 */
export function clearTransformationCache(): void {
  transformationCache.clear();
}

/**
 * Detects the model version from the results by looking at the first clip's model_version
 * Returns undefined if no model version is found (defaults to 2.7 behavior)
 */
export function detectModelVersionFromResults(results: any[]): string | undefined {
  for (const asset of results) {
    // Check if it's a clip asset with clipData
    if (isClipAsset(asset) && asset.clipData?.model_version) {
      return asset.clipData.model_version;
    }
    // Check if asset has clips array
    const clips = asset.clips as ClipData[] | undefined;
    if (clips && clips.length > 0 && clips[0].model_version) {
      return clips[0].model_version;
    }
  }
  return undefined;
}

export type { ClipAssetItem };
