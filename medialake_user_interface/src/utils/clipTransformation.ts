import {
  type ImageItem,
  type VideoItem,
  type AudioItem,
} from "@/types/search/searchResults";

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
  pagination?: { page: number; pageSize: number },
): string {
  // Create a simple hash of the results array and parameters
  const resultIds = results.map((r) => r.InventoryID).join(",");
  const paginationKey = pagination
    ? `_p${pagination.page}_s${pagination.pageSize}`
    : "";
  return `${isSemantic}_${semanticMode}_${resultIds}${paginationKey}`;
}

interface ClipData {
  start_timecode?: string;
  end_timecode?: string;
  start?: number;
  end?: number;
  score?: number;
  embedding_option?: string;
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
  },
): { results: AssetItem[]; totalClips: number } {
  // If not in semantic clip mode, return original results immediately
  if (!isSemantic || semanticMode !== "clip") {
    return { results, totalClips: results.length };
  }

  // Check cache first (only cache the full transformation, not paginated results)
  const fullCacheKey = generateCacheKey(results, isSemantic, semanticMode);
  let allClipAssets = transformationCache.get(fullCacheKey) as
    | ClipAssetItem[]
    | undefined;

  if (!allClipAssets) {
    console.log(
      "🎬 Starting clip transformation for",
      results.length,
      "assets",
    );
    const startTime = performance.now();

    allClipAssets = [];

    // Extract all clips from all assets
    results.forEach((asset, assetIndex) => {
      const clips = (asset as any).clips as ClipData[] | undefined;
      const assetType = asset.DigitalSourceAsset?.Type || "Unknown";

      // Debug: Log asset types and clip availability
      console.log(
        `🎬 Processing asset ${assetIndex + 1}/${results.length}: Type=${assetType}, HasClips=${!!clips}, ClipCount=${clips?.length || 0}`,
      );

      // Debug: Log all clips for this asset to see if the 00:00:00 clip is present
      if (clips && clips.length > 0) {
        console.log(
          `🎬 Clips for asset ${assetIndex + 1}:`,
          clips.map((clip) => ({
            start_timecode: clip.start_timecode,
            end_timecode: clip.end_timecode,
            score: clip.score,
          })),
        );

        // Check specifically for clips starting at 00:00:00
        const zeroStartClips = clips.filter(
          (clip) => clip.start_timecode === "00:00:00:00",
        );
        if (zeroStartClips.length > 0) {
          console.log(
            `🔍 Found ${zeroStartClips.length} clips starting at 00:00:00:00:`,
            zeroStartClips,
          );
        }
      }

      // For video and audio assets, process individual clips if available
      if (
        (assetType === "Video" || assetType === "Audio") &&
        clips &&
        Array.isArray(clips) &&
        clips.length > 0
      ) {
        clips.forEach((clip, clipIndex) => {
          // Debug logging for clips starting at 00:00:00
          if (clip.start_timecode === "00:00:00:00") {
            console.log(`🔍 Found clip starting at 00:00:00:00:`, {
              clipIndex,
              score: clip.score,
              start_timecode: clip.start_timecode,
              end_timecode: clip.end_timecode,
              hasValidScore: clip.score !== undefined && clip.score !== null,
            });
          }

          // Only process clips that have a valid score for semantic search
          if (clip.score !== undefined && clip.score !== null) {
            // Create a new asset item for each clip
            const { clips: originalClips, ...assetWithoutClips } = asset as any;
            const clipAsset: ClipAssetItem = {
              ...assetWithoutClips,
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

            // Debug logging for clips starting at 00:00:00 that are being added
            if (clip.start_timecode === "00:00:00:00") {
              console.log(
                `✅ Adding clip starting at 00:00:00:00 to results:`,
                {
                  clipAssetId: clipAsset.InventoryID,
                  score: clipAsset.score,
                },
              );
            }

            allClipAssets!.push(clipAsset);
          } else if (clip.start_timecode === "00:00:00:00") {
            console.log(
              `❌ Skipping clip starting at 00:00:00:00 due to invalid score:`,
              {
                score: clip.score,
                scoreType: typeof clip.score,
              },
            );
          }
        });
      }
      // For non-video/audio assets (Image), treat the entire asset as a "clip"
      else if (assetType === "Image") {
        const { clips: originalClips, ...assetWithoutClips } = asset as any;
        const wholeAssetClip: ClipAssetItem = {
          ...assetWithoutClips,
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
        const { clips: originalClips, ...assetWithoutClips } = asset as any;
        const wholeAssetClip: ClipAssetItem = {
          ...assetWithoutClips,
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
      {} as Record<string, { total: number; withClips: number }>,
    );

    const endTime = performance.now();
    console.log(
      `🎬 Clip transformation completed in ${(endTime - startTime).toFixed(2)}ms`,
    );
    console.log(
      `📊 Transformed ${results.length} assets into ${allClipAssets.length} clips`,
    );
    console.log("📈 Asset type summary:", assetTypeSummary);

    // Cache the result for future use
    transformationCache.set(fullCacheKey, allClipAssets);

    // Limit cache size to prevent memory leaks
    if (transformationCache.size > 10) {
      const firstKey = transformationCache.keys().next().value;
      transformationCache.delete(firstKey);
    }
  } else {
    console.log("🚀 Using cached clip transformation result");
  }

  const totalClips = allClipAssets.length;

  // Apply pagination if provided
  if (pagination) {
    const { page, pageSize } = pagination;
    const startIndex = (page - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const paginatedClips = allClipAssets.slice(startIndex, endIndex);

    console.log(
      `📄 Applied pagination: page ${page}, pageSize ${pageSize}, showing ${paginatedClips.length} of ${totalClips} clips`,
    );

    return { results: paginatedClips, totalClips };
  }

  // Return all clips if no pagination
  return { results: allClipAssets, totalClips };
}

/**
 * Checks if an asset is a clip-based asset (including whole assets treated as clips)
 */
export function isClipAsset(asset: any): asset is ClipAssetItem {
  return (
    asset &&
    typeof asset === "object" &&
    "clipData" in asset &&
    "originalAssetId" in asset
  );
}

/**
 * Gets the display name for a clip asset
 */
export function getClipDisplayName(asset: any): string {
  if (isClipAsset(asset)) {
    const originalName =
      asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
        .ObjectKey.Name;
    const clipData = asset.clipData;
    const assetType = asset.DigitalSourceAsset?.Type || "Unknown";

    // For non-video assets or video assets without time markers, just return the name
    if (
      assetType !== "Video" ||
      (!clipData.start_timecode && !clipData.start)
    ) {
      return originalName;
    }

    // For video clips with time markers
    if (clipData.start_timecode && clipData.end_timecode) {
      return `${originalName} (${clipData.start_timecode} - ${clipData.end_timecode})`;
    } else if (clipData.start !== undefined && clipData.end !== undefined) {
      const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, "0")}`;
      };
      return `${originalName} (${formatTime(clipData.start)} - ${formatTime(clipData.end)})`;
    } else {
      return `${originalName} (Clip ${asset.clipIndex + 1})`;
    }
  }

  return asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
    .ObjectKey.Name;
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
  if (
    typeof asset.InventoryID === "string" &&
    asset.InventoryID.includes("_clip_")
  ) {
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
  console.log("🧹 Transformation cache cleared");
}

export type { ClipAssetItem };
