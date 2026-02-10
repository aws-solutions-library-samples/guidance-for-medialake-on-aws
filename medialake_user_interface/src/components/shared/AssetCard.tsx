import React, { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Box, Typography, IconButton, Button, CircularProgress, Checkbox } from "@mui/material";
import { alpha } from "@mui/material/styles";
import DeleteIcon from "@mui/icons-material/Delete";
import DownloadIcon from "@mui/icons-material/Download";
import EditIcon from "@mui/icons-material/Edit";
import FavoriteIcon from "@mui/icons-material/Favorite";
import FavoriteBorderIcon from "@mui/icons-material/FavoriteBorder";
import CheckBoxOutlineBlankIcon from "@mui/icons-material/CheckBoxOutlineBlank";
// import InfoIcon from "@mui/icons-material/Info";
import AddIcon from "@mui/icons-material/Add";
import RemoveIcon from "@mui/icons-material/Remove";
import { PLACEHOLDER_IMAGE, VIDEO_PLACEHOLDER_IMAGE } from "@/utils/placeholderSvg";
import CheckBoxIcon from "@mui/icons-material/CheckBox";
import { InlineTextEditor } from "../common/InlineTextEditor";
import {
  OmakasePlayer,
  PeriodMarker,
  PlayerChromingTheme,
  StampThemeScale,
} from "@byomakase/omakase-player";
import { useSemanticMode } from "@/stores/searchStore";
import { getMarkerColorByConfidence } from "../common/utils";

export interface AssetField {
  id: string;
  label: string;
  visible: boolean;
}

export interface AssetCardProps {
  id: string;
  name: string;
  thumbnailUrl?: string;
  proxyUrl?: string;
  assetType?: string;
  clips?: Array<{
    start_timecode?: string;
    end_timecode?: string;
    start?: number;
    end?: number;
    score?: number; // Add score for confidence filtering
    embedding_option?: string;
  }>;
  fields: AssetField[];
  isRenaming?: boolean;
  renderField: (fieldId: string) => string | React.ReactNode;
  onAssetClick: () => void;
  onDeleteClick: (event: React.MouseEvent<HTMLElement>) => void;
  onDownloadClick: (event: React.MouseEvent<HTMLElement>) => void;
  onAddToCollectionClick?: (event: React.MouseEvent<HTMLElement>) => void;
  showRemoveButton?: boolean;
  onEditClick?: (event: React.MouseEvent<HTMLElement>) => void;
  placeholderImage?: string;
  onImageError?: (event: React.SyntheticEvent<HTMLImageElement, Event>) => void;
  isEditing?: boolean;
  editedName?: string;
  onEditNameChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete?: (save: boolean, value?: string) => void;
  cardSize?: "small" | "medium" | "large";
  aspectRatio?: "vertical" | "square" | "horizontal";
  thumbnailScale?: "fit" | "fill";
  showMetadata?: boolean;
  menuOpen?: boolean; // Add prop to track menu state from parent
  isFavorite?: boolean; // Whether the asset is favorited
  onFavoriteToggle?: (event: React.MouseEvent<HTMLElement>) => void; // Callback when favorite is toggled
  isSelected?: boolean; // Whether the asset is selected for bulk operations
  onSelectToggle?: (id: string, event: React.MouseEvent<HTMLElement>) => void; // Callback when selection is toggled
  selectedSearchFields?: string[]; // Selected search fields
  // Semantic search confidence filtering for clips
  isSemantic?: boolean;
  confidenceThreshold?: number;
  variant?: "compact" | "full"; // compact = dashboard style, full = search results style
}

const AssetCard: React.FC<AssetCardProps> = React.memo(
  ({
    id,
    name,
    thumbnailUrl,
    proxyUrl,
    assetType,
    clips,
    fields,
    renderField,
    onAssetClick,
    onDeleteClick,
    onDownloadClick,
    onAddToCollectionClick,
    showRemoveButton = false,
    onEditClick,
    placeholderImage = PLACEHOLDER_IMAGE,
    onImageError,
    isRenaming = false,
    isEditing,
    editedName,
    onEditNameChange,
    onEditNameComplete,
    cardSize = "medium",
    aspectRatio = "square",
    thumbnailScale = "fill",
    showMetadata = true,
    menuOpen = false, // Default to false
    isFavorite = false,
    onFavoriteToggle,
    isSelected = false,
    onSelectToggle,
    selectedSearchFields,
    // Semantic search confidence filtering for clips
    isSemantic = false,
    confidenceThreshold = 0.57,
    variant = "full",
  }) => {
    const { t } = useTranslation();
    const [isHovering, setIsHovering] = useState(false);
    const [isMenuClicked, setIsMenuClicked] = useState(false);
    const preventCommitRef = useRef<boolean>(false);
    const commitRef = useRef<(() => void) | null>(null);
    const omakasePlayerRef = useRef<OmakasePlayer | null>(null);

    // Lazy loading state for video assets
    const [isVisible, setIsVisible] = useState(false);
    const cardContainerRef = useRef<HTMLDivElement>(null);

    // Get semantic mode to conditionally hide buttons
    // Only hide buttons when semantic search is active AND in clip mode
    // Use the isSemantic prop instead of global store to allow parent components to control this
    // This prevents dashboard cards from being affected by search page state
    const semanticMode = useSemanticMode();
    const isClipMode = isSemantic && semanticMode === "clip";

    // Update when menuOpen prop changes
    useEffect(() => {
      if (menuOpen) {
        setIsMenuClicked(true);
      }
    }, [menuOpen]);

    // Track if player has been initialized to prevent re-initialization
    const playerInitializedRef = useRef<boolean>(false);
    const currentProxyUrlRef = useRef<string | undefined>(proxyUrl);
    const markerIdsRef = useRef<string[]>([]);
    const [videoLoadError, setVideoLoadError] = useState(false);

    // IntersectionObserver for lazy loading videos and audio
    useEffect(() => {
      // Only observe if this is a video or audio asset
      if ((assetType !== "Video" && assetType !== "Audio") || !cardContainerRef.current) return;

      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              // Stagger initialization to spread load across frames
              // Use requestAnimationFrame for smoother initialization
              requestAnimationFrame(() => {
                setTimeout(() => {
                  setIsVisible(true);
                }, Math.random() * 100); // 0-100ms random delay per video
              });
              observer.unobserve(entry.target);
            }
          });
        },
        {
          rootMargin: "400px", // Start loading 400px before entering viewport (increased from 200px)
          threshold: 0.01,
        }
      );

      observer.observe(cardContainerRef.current);

      return () => observer.disconnect();
    }, [assetType]);

    // Initialize Omakase player for video and audio assets
    useEffect(() => {
      // Only initialize if it's a video or audio, has a proxy URL, is visible, and hasn't been initialized yet
      if (
        (assetType === "Video" || assetType === "Audio") &&
        proxyUrl &&
        isVisible &&
        !playerInitializedRef.current
      ) {
        // Sanitize the ID to remove characters that are invalid in CSS selectors (colons, etc.)
        const sanitizedId = id.replace(/[^a-zA-Z0-9_-]/g, "-");
        const playerId = `omakase-player-${sanitizedId}`;

        // Check if player container already exists
        let playerContainer = document.getElementById(playerId);
        if (!playerContainer) {
          playerContainer = document.createElement("div");
          playerContainer.id = playerId;
          playerContainer.style.width = "100%";
          playerContainer.style.height = "100%";
        }

        // Initialize Omakase player
        try {
          const omakasePlayer = new OmakasePlayer({
            playerHTMLElementId: playerId,
            playerChroming: {
              theme: PlayerChromingTheme.Stamp,
              themeConfig: {
                stampScale: thumbnailScale === "fit" ? StampThemeScale.Fit : StampThemeScale.Fill,
              },
            },
          });

          // Store the player reference
          omakasePlayerRef.current = omakasePlayer;
          playerInitializedRef.current = true;
          currentProxyUrlRef.current = proxyUrl;

          // Reset error state when attempting to load video/audio
          setVideoLoadError(false);

          // Load the video/audio then add markers if clips provided
          // For audio assets, pass protocol: "audio"
          // For video assets with thumbnails, add poster
          const loadOptions =
            assetType === "Audio"
              ? { protocol: "audio" as const }
              : assetType === "Video" && thumbnailUrl
                ? { poster: thumbnailUrl }
                : undefined;
          omakasePlayer.loadVideo(proxyUrl, loadOptions).subscribe({
            next: () => {
              // Defer marker creation to idle time to avoid blocking video playback
              const scheduleMarkerCreation = () => {
                const callback = () => {
                  try {
                    // Clear any default markers that might have been created by the player
                    console.log(`🧹 Clearing any default markers for asset ${id}`);
                    try {
                      omakasePlayer.progressMarkerTrack.removeAllMarkers();
                      console.log(`🧹 ✅ Default markers cleared`);
                    } catch (e) {
                      console.warn(`🧹 ❌ Could not clear default markers:`, e);
                    }

                    if (Array.isArray(clips) && clips.length > 0) {
                      const timecodeToSeconds = (tc: string): number => {
                        const [hh, mm, ss, ff] = tc.split(":").map(Number);
                        const fps = 25; // default/fallback; adjust if actual fps available
                        return hh * 3600 + mm * 60 + ss + (isNaN(ff) ? 0 : ff / fps);
                      };

                      // For clip mode, we should only show the marker for this specific clip
                      // Check if this is a clip asset (ID contains #CLIP# or _clip_)
                      const isClipAsset = id.includes("#CLIP#") || id.includes("_clip_");

                      console.log(`🎬 INITIAL Asset ${id}:`);
                      console.log(`  - isClipAsset: ${isClipAsset}`);
                      console.log(`  - isSemantic: ${isSemantic} (type: ${typeof isSemantic})`);
                      console.log(
                        `  - confidenceThreshold: ${confidenceThreshold} (type: ${typeof confidenceThreshold})`
                      );
                      console.log(`  - clips count: ${clips?.length || 0}`);
                      console.log(
                        `  - clips:`,
                        clips?.map((c, idx) => ({
                          index: idx,
                          score: c.score,
                          start_timecode: c.start_timecode,
                          end_timecode: c.end_timecode,
                          start_seconds: c.start,
                          end_seconds: c.end,
                        }))
                      );

                      // For clip assets, we only want to show the single clip marker
                      // For full assets, we show all clips that pass the confidence threshold
                      let filteredClips;
                      if (isClipAsset) {
                        // This is a clip asset, so clips array should contain only one clip
                        // But let's be extra careful and ensure we only process valid clips
                        filteredClips = (clips || []).filter((clip) => {
                          const hasValidTimes =
                            (clip.start_timecode && clip.end_timecode) ||
                            (typeof clip.start === "number" && typeof clip.end === "number");
                          console.log(`    Validating clip:`, {
                            hasValidTimes,
                            start_timecode: clip.start_timecode,
                            end_timecode: clip.end_timecode,
                            start: clip.start,
                            end: clip.end,
                          });
                          return hasValidTimes;
                        });
                        console.log(
                          `  - Clip asset: showing ${filteredClips.length} of ${
                            clips?.length || 0
                          } marker(s)`
                        );
                      } else {
                        // This is a full asset, show all clips from API response
                        // Only apply confidence filtering if explicitly enabled and threshold > 0
                        const shouldFilter = isSemantic && confidenceThreshold > 0;
                        console.log(
                          `  - shouldFilter: ${shouldFilter} (isSemantic=${isSemantic} && confidenceThreshold=${confidenceThreshold} > 0)`
                        );

                        filteredClips = shouldFilter
                          ? clips.filter((clip) => {
                              const score = clip.score ?? 1;
                              const passes = score >= confidenceThreshold;
                              console.log(
                                `    Clip ${clip.start_timecode}-${clip.end_timecode}: score=${score}, threshold=${confidenceThreshold}, passes=${passes}`
                              );
                              return passes;
                            })
                          : clips; // Show all clips when not filtering

                        console.log(
                          `  - Full asset: showing ${filteredClips.length} of ${
                            clips.length
                          } markers${
                            shouldFilter
                              ? ` (confidence >= ${confidenceThreshold})`
                              : " (all clips)"
                          }`
                        );
                      }

                      filteredClips.forEach((clip, index) => {
                        const start =
                          typeof clip.start === "number"
                            ? clip.start
                            : clip.start_timecode
                              ? timecodeToSeconds(clip.start_timecode)
                              : undefined;
                        const end =
                          typeof clip.end === "number"
                            ? clip.end
                            : clip.end_timecode
                              ? timecodeToSeconds(clip.end_timecode)
                              : undefined;

                        console.log(`  🎯 Processing clip ${index}:`, {
                          start_timecode: clip.start_timecode,
                          end_timecode: clip.end_timecode,
                          start_seconds: clip.start,
                          end_seconds: clip.end,
                          calculated_start: start,
                          calculated_end: end,
                          score: clip.score,
                        });

                        if (start !== undefined && end !== undefined) {
                          // Skip markers that have very short duration (likely unwanted markers)
                          // Only skip clips starting at 0 if they're very short (< 1 second)
                          if ((start === 0 && end - start < 1) || (start < 2 && end - start < 1)) {
                            console.log(
                              `  ⚠️ Skipping unwanted short marker: ${start}s - ${end}s (duration: ${
                                end - start
                              }s)`
                            );
                            return;
                          }

                          // Additional validation: ensure the marker has reasonable duration
                          if (end - start < 1) {
                            console.log(
                              `  ⚠️ Skipping marker with too short duration: ${start}s - ${end}s (duration: ${
                                end - start
                              }s)`
                            );
                            return;
                          }

                          // Use confidence-based colors for markers
                          // Pass model_version for model-aware thresholds (3.0 vs 2.7)
                          const markerColor = getMarkerColorByConfidence(
                            clip.score,
                            clip.model_version
                          );

                          // Follow JSFiddle approach: let byomakase library generate its own IDs
                          // This prevents querySelector errors with colon-containing custom IDs
                          const marker = new PeriodMarker({
                            timeObservation: { start, end },
                            style: {
                              color: markerColor,
                            },
                          });
                          // Add marker to progress track when available
                          try {
                            omakasePlayer.progressMarkerTrack.addMarker(marker);
                            // Store marker reference for later removal since we don't control the ID
                            markerIdsRef.current.push(marker.id || `${start}-${end}`);
                            console.log(
                              `  ✅ Added marker: ${start}s - ${end}s (color: ${markerColor})`
                            );

                            // For clip assets or single-clip items, seek to the beginning of the clip
                            // This includes collection items with a specific clip boundary
                            if (isClipAsset || (filteredClips.length === 1 && index === 0)) {
                              try {
                                omakasePlayer.video.seekToTime(start);
                                console.log(
                                  `  🎯 Seeked to clip start time: ${start}s for ${
                                    isClipAsset ? "clip asset" : "single-clip item"
                                  } ${assetType.toLowerCase()} ${id}`
                                );
                              } catch (seekError) {
                                console.warn(
                                  `  ⚠️ Failed to seek to clip start time ${start}s for ${assetType.toLowerCase()} asset:`,
                                  seekError
                                );
                              }
                            }
                          } catch (e) {
                            console.warn("progressMarkerTrack not ready", e);
                          }
                        } else {
                          console.log(`  ❌ Skipped clip ${index}: invalid start/end times`);
                        }
                      });
                    }
                  } catch (e) {
                    console.error("Failed to add semantic markers:", e);
                  }
                };

                // Use requestIdleCallback to defer marker creation, with fallback to setTimeout
                if ("requestIdleCallback" in window) {
                  requestIdleCallback(callback, { timeout: 2000 });
                } else {
                  // Fallback for browsers without requestIdleCallback
                  setTimeout(callback, 100);
                }
              };

              // Call the schedule function to initiate deferred marker creation
              scheduleMarkerCreation();
            },
            error: (error) => {
              console.error(`Failed to load ${assetType.toLowerCase()} for asset ${id}:`, error);
              setVideoLoadError(true);
            },
          });

          console.log(`Omakase player initialized for ${assetType.toLowerCase()} asset: ${id}`);
        } catch (error) {
          console.error(
            `Failed to initialize Omakase player for ${assetType.toLowerCase()} asset ${id}:`,
            error
          );
        }
      }
      // If the proxy URL changed, we need to reload the video/audio
      else if (
        (assetType === "Video" || assetType === "Audio") &&
        proxyUrl &&
        playerInitializedRef.current &&
        currentProxyUrlRef.current !== proxyUrl &&
        omakasePlayerRef.current
      ) {
        currentProxyUrlRef.current = proxyUrl;
        const loadOptions = assetType === "Audio" ? { protocol: "audio" as const } : undefined;
        omakasePlayerRef.current.loadVideo(proxyUrl, loadOptions).subscribe({
          next: () => {
            console.log(`${assetType} reloaded for asset ${id}`);
          },
          error: (error) => {
            console.error(`Failed to reload ${assetType.toLowerCase()} for asset ${id}:`, error);
            setVideoLoadError(true);
          },
        });
      }

      // Cleanup function - only destroy when component unmounts
      return () => {
        if (omakasePlayerRef.current) {
          try {
            omakasePlayerRef.current.destroy();
            omakasePlayerRef.current = null;
            playerInitializedRef.current = false;
            console.log(`Omakase player destroyed for ${assetType.toLowerCase()} asset: ${id}`);
          } catch (error) {
            console.error(
              `Failed to destroy Omakase player for ${assetType.toLowerCase()} asset ${id}:`,
              error
            );
          }
        }
      };
    }, [assetType, proxyUrl, id, isVisible]); // Removed thumbnailScale to prevent reload on appearance change

    // Separate effect to handle clip marker updates when confidence threshold changes
    useEffect(() => {
      if (
        (assetType === "Video" || assetType === "Audio") &&
        omakasePlayerRef.current &&
        Array.isArray(clips) &&
        clips.length > 0
      ) {
        // Defer marker updates to idle time to avoid blocking interactions
        const updateMarkers = () => {
          try {
            // Clear ALL existing markers using removeAllMarkers method
            console.log(
              `🧹 CLEARING ALL existing markers for asset ${id} using removeAllMarkers()`
            );
            try {
              omakasePlayerRef.current?.progressMarkerTrack.removeAllMarkers();
              markerIdsRef.current = []; // Reset our tracking array
              console.log(`🧹 ✅ All markers cleared successfully`);
            } catch (e) {
              console.warn(`🧹 ❌ Could not clear all markers:`, e);
              // Fallback to individual removal if removeAllMarkers fails
              markerIdsRef.current.forEach((markerId) => {
                try {
                  omakasePlayerRef.current?.progressMarkerTrack.removeMarker(markerId);
                  console.log(`  ✅ Fallback removed marker: ${markerId}`);
                } catch (e) {
                  console.warn(`  ❌ Could not remove marker ${markerId}:`, e);
                }
              });
              markerIdsRef.current = [];
            }

            const timecodeToSeconds = (tc: string): number => {
              const [hh, mm, ss, ff] = tc.split(":").map(Number);
              const fps = 25; // default/fallback; adjust if actual fps available
              return hh * 3600 + mm * 60 + ss + (isNaN(ff) ? 0 : ff / fps);
            };

            // For clip mode, we should only show the marker for this specific clip
            // Check if this is a clip asset (has clipData property)
            const isClipAsset = id.includes("_clip_");

            console.log(`🔄 UPDATE Asset ${id}:`);
            console.log(`  - isClipAsset: ${isClipAsset}`);
            console.log(`  - isSemantic: ${isSemantic} (type: ${typeof isSemantic})`);
            console.log(
              `  - confidenceThreshold: ${confidenceThreshold} (type: ${typeof confidenceThreshold})`
            );
            console.log(`  - clips count: ${clips?.length || 0}`);

            // For clip assets, we only want to show the single clip marker
            // For full assets, we show all clips that pass the confidence threshold
            let filteredClips;
            if (isClipAsset) {
              // This is a clip asset, so clips array should contain only one clip
              // But let's be extra careful and ensure we only process valid clips
              filteredClips = (clips || []).filter((clip) => {
                const hasValidTimes =
                  (clip.start_timecode && clip.end_timecode) ||
                  (typeof clip.start === "number" && typeof clip.end === "number");
                console.log(`    UPDATE: Validating clip:`, {
                  hasValidTimes,
                  start_timecode: clip.start_timecode,
                  end_timecode: clip.end_timecode,
                  start: clip.start,
                  end: clip.end,
                });
                return hasValidTimes;
              });
              console.log(
                `  - Clip asset: updating ${filteredClips.length} of ${
                  clips?.length || 0
                } marker(s)`
              );
            } else {
              // This is a full asset, show all clips from API response
              // Only apply confidence filtering if explicitly enabled and threshold > 0
              const shouldFilter = isSemantic && confidenceThreshold > 0;
              console.log(
                `  - shouldFilter: ${shouldFilter} (isSemantic=${isSemantic} && confidenceThreshold=${confidenceThreshold} > 0)`
              );

              filteredClips = shouldFilter
                ? clips.filter((clip) => {
                    const score = clip.score ?? 1;
                    const passes = score >= confidenceThreshold;
                    console.log(
                      `    UPDATE Clip ${clip.start_timecode}-${clip.end_timecode}: score=${score}, threshold=${confidenceThreshold}, passes=${passes}`
                    );
                    return passes;
                  })
                : clips; // Show all clips when not filtering

              console.log(
                `  - Full asset: updating ${filteredClips.length} of ${clips.length} markers${
                  shouldFilter ? ` (confidence >= ${confidenceThreshold})` : " (all clips)"
                }`
              );
            }

            filteredClips.forEach((clip) => {
              const start =
                typeof clip.start === "number"
                  ? clip.start
                  : clip.start_timecode
                    ? timecodeToSeconds(clip.start_timecode)
                    : undefined;
              const end =
                typeof clip.end === "number"
                  ? clip.end
                  : clip.end_timecode
                    ? timecodeToSeconds(clip.end_timecode)
                    : undefined;

              if (start !== undefined && end !== undefined) {
                // Skip markers that have very short duration (likely unwanted markers)
                // Only skip clips starting at 0 if they're very short (< 1 second)
                if ((start === 0 && end - start < 1) || (start < 2 && end - start < 1)) {
                  console.log(
                    `  ⚠️ UPDATE: Skipping unwanted short marker: ${start}s - ${end}s (duration: ${
                      end - start
                    }s)`
                  );
                  return;
                }

                // Additional validation: ensure the marker has reasonable duration
                if (end - start < 1) {
                  console.log(
                    `  ⚠️ UPDATE: Skipping marker with too short duration: ${start}s - ${end}s (duration: ${
                      end - start
                    }s)`
                  );
                  return;
                }

                // Use confidence-based colors for markers
                // Pass model_version for model-aware thresholds (3.0 vs 2.7)
                const markerColor = getMarkerColorByConfidence(clip.score, clip.model_version);

                // Follow JSFiddle approach: let byomakase library generate its own IDs
                // This prevents querySelector errors with colon-containing custom IDs
                const marker = new PeriodMarker({
                  timeObservation: { start, end },
                  style: {
                    color: markerColor,
                  },
                });
                // Add marker to progress track when available
                try {
                  omakasePlayerRef.current.progressMarkerTrack.addMarker(marker);
                  // Store marker reference for later removal since we don't control the ID
                  markerIdsRef.current.push(marker.id || `${start}-${end}`);
                  console.log(
                    `  ✅ Added marker: ${marker.id || "auto-generated"} (${start}s-${end}s)`
                  );

                  // For clip assets, seek to the beginning of the clip
                  if (isClipAsset) {
                    try {
                      // Use video.seekToTime for both video and audio assets
                      omakasePlayerRef.current.video.seekToTime(start);
                      console.log(
                        `  🎯 UPDATE: Seeked to clip start time: ${start}s for ${assetType.toLowerCase()} clip asset ${id}`
                      );
                    } catch (seekError) {
                      console.warn(
                        `  ⚠️ UPDATE: Failed to seek to clip start time ${start}s for ${assetType.toLowerCase()} asset:`,
                        seekError
                      );
                    }
                  }
                } catch (e) {
                  console.warn("progressMarkerTrack not ready", e);
                }
              }
            });

            console.log(
              `🎯 SUMMARY for Asset ${id}: Created ${markerIdsRef.current.length} markers from ${filteredClips.length} filtered clips (out of ${clips.length} total clips)`
            );
          } catch (e) {
            console.error("Failed to update semantic markers:", e);
          }
        };

        // Use requestIdleCallback to defer marker updates, with fallback to setTimeout
        if ("requestIdleCallback" in window) {
          requestIdleCallback(updateMarkers, { timeout: 1000 });
        } else {
          // Fallback for browsers without requestIdleCallback
          setTimeout(updateMarkers, 50);
        }
      }
    }, [clips, isSemantic, confidenceThreshold, assetType, id]); // Update markers when clips or confidence threshold changes

    // Separate effect to handle thumbnailScale changes in real-time without reloading the player
    useEffect(() => {
      if (
        (assetType === "Video" || assetType === "Audio") &&
        omakasePlayerRef.current &&
        playerInitializedRef.current
      ) {
        try {
          // Get the HTML video element from the Omakase player
          const videoElement = omakasePlayerRef.current.video.getHTMLVideoElement();

          // Update the object-fit CSS property directly on the video element
          if (videoElement) {
            const objectFitValue = thumbnailScale === "fit" ? "contain" : "cover";
            videoElement.style.objectFit = objectFitValue;

            // Also update any video elements within the player container
            const sanitizedId = id.replace(/[^a-zA-Z0-9_-]/g, "-");
            const playerContainer = document.getElementById(`omakase-player-${sanitizedId}`);
            if (playerContainer) {
              // Find all video elements within the container and update them
              const videoElements = playerContainer.querySelectorAll("video");
              videoElements.forEach((video) => {
                video.style.objectFit = objectFitValue;
              });
            }

            console.log(`Updated video object-fit to: ${objectFitValue} for asset ${id}`);
          }
        } catch (error) {
          console.warn(`Failed to update video object-fit for asset ${id}:`, error);
        }
      }
    }, [thumbnailScale, assetType, id]); // Update object-fit when thumbnailScale changes

    const isCompact = variant === "compact";

    // Determine the card dimensions based on props (used by full variant)
    const getCardDimensions = () => {
      const baseHeight =
        aspectRatio === "vertical"
          ? 300
          : aspectRatio === "square"
            ? 200
            : aspectRatio === "horizontal"
              ? 150
              : 200;
      const sizeMultiplier = cardSize === "small" ? 0.8 : cardSize === "large" ? 1.4 : 1.1;
      return {
        height: baseHeight * sizeMultiplier,
        width: "100%",
      };
    };
    const dimensions = getCardDimensions();

    // Fallback image error
    const defaultImageErrorHandler = (event: React.SyntheticEvent<HTMLImageElement, Event>) => {
      event.currentTarget.src = assetType === "Video" ? VIDEO_PLACEHOLDER_IMAGE : placeholderImage;
    };

    const handleDeleteClick = (event: React.MouseEvent<HTMLElement>) => {
      event.stopPropagation();
      onDeleteClick(event);
    };

    const handleDownloadClick = (event: React.MouseEvent<HTMLElement>) => {
      event.stopPropagation();
      // Directly trigger download functionality
      onDownloadClick(event);
    };

    // Handle clicks outside to detect when menu should be considered closed
    useEffect(() => {
      const handleClickOutside = (event: MouseEvent) => {
        // If we click outside the card and the menu is open, consider it closed
        if (cardContainerRef.current && !cardContainerRef.current.contains(event.target as Node)) {
          // This is a click outside the card
          // We'll keep the menu clicked state for a short time to allow the menu to close gracefully
          setTimeout(() => {
            setIsMenuClicked(false);
          }, 300);
        }
      };

      // Add event listener for clicks
      document.addEventListener("mousedown", handleClickOutside);

      // Cleanup
      return () => {
        document.removeEventListener("mousedown", handleClickOutside);
      };
    }, []);

    // Determine if buttons should be visible
    const shouldShowButtons = isHovering || isMenuClicked;

    // Create a mapping between API field IDs and card field IDs based on the new API response structure
    const fieldMapping: Record<string, string> = {
      // Root level fields (new API structure)
      id: "id",
      assetType: "type",
      format: "format",
      createdAt: "createdAt",
      objectName: "name",
      fileSize: "size",
      fullPath: "fullPath",
      bucket: "bucket",
      FileHash: "hash",

      // Legacy nested fields (for backward compatibility)
      "DigitalSourceAsset.Type": "type",
      "DigitalSourceAsset.MainRepresentation.Format": "format",
      "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.CreateDate":
        "createdAt",
      "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate": "createdAt",
      "DigitalSourceAsset.CreateDate": "createdAt",
      "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name": "name",
      "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size": "size",
      "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize": "size",
      "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath":
        "fullPath",
      "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.Bucket": "bucket",
      "Metadata.Consolidated": "metadata",
      InventoryID: "id",
    };

    // Create a reverse mapping for easier lookup

    // Create a reverse mapping for easier lookup
    // Since multiple API fields can map to the same card field, we need to store arrays
    const reverseFieldMapping: Record<string, string[]> = {};
    Object.entries(fieldMapping).forEach(([apiId, cardId]) => {
      if (!reverseFieldMapping[cardId]) {
        reverseFieldMapping[cardId] = [];
      }
      reverseFieldMapping[cardId].push(apiId);
    });

    // Filter fields based on visibility and selected search fields
    const visibleFields = fields.filter((field) => {
      // First check if the field is marked as visible in cardFields
      if (!field.visible) return false;

      // If no selectedSearchFields are provided, show all visible fields
      if (!selectedSearchFields || selectedSearchFields.length === 0) return true;

      // Special case for name field - check if any selected field contains 'Name' or matches 'objectName'
      if (field.id === "name") {
        return selectedSearchFields.some(
          (field) => field.includes("Name") || field === "objectName"
        );
      }

      // Special case for date field - check if any selected field contains 'CreateDate' or matches 'createdAt'
      if (field.id === "createdAt") {
        return selectedSearchFields.some(
          (field) => field.includes("CreateDate") || field === "createdAt"
        );
      }

      // Special case for file size field - check if any selected field contains 'FileSize', 'Size', or matches 'fileSize'
      if (field.id === "size") {
        return selectedSearchFields.some(
          (field) => field.includes("FileSize") || field.includes("Size") || field === "fileSize"
        );
      }

      // Special case for fullPath field - check if any selected field contains 'FullPath' or 'Path'
      if (field.id === "fullPath") {
        return selectedSearchFields.some(
          (field) => field.includes("FullPath") || field.includes("Path") || field === "fullPath"
        );
      }

      // For other fields, check if any of their mapped API field IDs are in the selectedSearchFields
      const apiFieldIds = reverseFieldMapping[field.id] || [];
      return apiFieldIds.some((apiFieldId) => selectedSearchFields.includes(apiFieldId));
    });

    return (
      <Box
        ref={cardContainerRef}
        sx={{
          position: "relative",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          cursor: "pointer",
          borderRadius: 3,
          overflow: "hidden",
          border: "1px solid",
          borderColor: (theme) => alpha(theme.palette.divider, 0.1),
          bgcolor: "background.paper",
          transition:
            "transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
          "&:hover": {
            transform: "translateY(-4px)",
            boxShadow: (theme) => `0 8px 32px ${alpha(theme.palette.common.black, 0.15)}`,
          },
        }}
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}
      >
        {/* Thumbnail area */}
        <Box sx={{ p: isCompact ? 1 : 0, pb: 0, position: "relative" }}>
          <Box
            sx={{
              height: isCompact ? 120 : dimensions.height,
              borderRadius: isCompact ? 2.5 : 0,
              overflow: "hidden",
              bgcolor: (theme) => alpha(theme.palette.primary.main, 0.04),
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              position: "relative",
            }}
          >
            {assetType === "Video" || assetType === "Audio" ? (
              proxyUrl && !videoLoadError ? (
                <div
                  id={`${assetType.toLowerCase()}-asset-${id}`}
                  className={`asset-card-${assetType.toLowerCase()}`}
                  style={{
                    width: "100%",
                    height: "100%",
                    backgroundColor: "rgba(0,0,0,0.03)",
                    cursor: "pointer",
                    position: "relative",
                  }}
                >
                  <div
                    id={`omakase-player-${id.replace(/[^a-zA-Z0-9_-]/g, "-")}`}
                    style={{ width: "100%", height: "100%" }}
                  />
                </div>
              ) : (
                <Box
                  onClick={onAssetClick}
                  component="img"
                  src={thumbnailUrl || VIDEO_PLACEHOLDER_IMAGE}
                  alt={name}
                  onError={onImageError || defaultImageErrorHandler}
                  data-image-id={id}
                  sx={{
                    cursor: "pointer",
                    width: "100%",
                    height: "100%",
                    objectFit: thumbnailScale === "fit" ? "contain" : "cover",
                  }}
                />
              )
            ) : (
              <Box
                onClick={onAssetClick}
                component="img"
                src={thumbnailUrl || placeholderImage}
                alt={name}
                onError={onImageError || defaultImageErrorHandler}
                data-image-id={id}
                sx={{
                  cursor: "pointer",
                  width: "100%",
                  height: "100%",
                  objectFit: thumbnailScale === "fit" ? "contain" : "cover",
                }}
              />
            )}

            {/* Hover overlay with action buttons (compact variant only) */}
            {isCompact && (
              <Box
                sx={{
                  position: "absolute",
                  inset: 0,
                  bgcolor: (theme) => alpha(theme.palette.common.black, 0.5),
                  opacity: shouldShowButtons ? 1 : 0,
                  transition: "opacity 0.2s ease-in-out",
                  pointerEvents: shouldShowButtons ? "auto" : "none",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 0.5,
                  borderRadius: 2.5,
                }}
                onClick={(e) => e.stopPropagation()}
              >
                {!isClipMode && (
                  <IconButton
                    size="small"
                    onClick={handleDownloadClick}
                    sx={{
                      color: "common.white",
                      bgcolor: (theme) => alpha(theme.palette.common.white, 0.15),
                      backdropFilter: "blur(4px)",
                      "&:hover": { bgcolor: (theme) => alpha(theme.palette.common.white, 0.3) },
                      width: 30,
                      height: 30,
                    }}
                    title={t("common.actions.download")}
                  >
                    <DownloadIcon sx={{ fontSize: 16 }} />
                  </IconButton>
                )}

                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    onAddToCollectionClick?.(e);
                  }}
                  sx={{
                    color: "common.white",
                    bgcolor: (theme) => alpha(theme.palette.common.white, 0.15),
                    backdropFilter: "blur(4px)",
                    "&:hover": { bgcolor: (theme) => alpha(theme.palette.common.white, 0.3) },
                    width: 30,
                    height: 30,
                  }}
                  title={
                    showRemoveButton
                      ? t("common.actions.removeFromCollection")
                      : t("common.actions.addToCollection")
                  }
                >
                  {showRemoveButton ? (
                    <RemoveIcon sx={{ fontSize: 16 }} />
                  ) : (
                    <AddIcon sx={{ fontSize: 16 }} />
                  )}
                </IconButton>

                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    onFavoriteToggle?.(e);
                  }}
                  sx={{
                    color: isFavorite ? "#FC8181" : "common.white",
                    bgcolor: (theme) => alpha(theme.palette.common.white, 0.15),
                    backdropFilter: "blur(4px)",
                    "&:hover": { bgcolor: (theme) => alpha(theme.palette.common.white, 0.3) },
                    width: 30,
                    height: 30,
                  }}
                  title={isFavorite ? t("favorites.removeFavorite") : t("favorites.addFavorite")}
                  data-testid="favorite-button"
                >
                  {isFavorite ? (
                    <FavoriteIcon sx={{ fontSize: 16 }} />
                  ) : (
                    <FavoriteBorderIcon sx={{ fontSize: 16 }} />
                  )}
                </IconButton>

                {!isClipMode && (
                  <IconButton
                    size="small"
                    onClick={handleDeleteClick}
                    sx={{
                      color: "common.white",
                      bgcolor: (theme) => alpha(theme.palette.common.white, 0.15),
                      backdropFilter: "blur(4px)",
                      "&:hover": {
                        bgcolor: (theme) => alpha(theme.palette.error.main, 0.6),
                      },
                      width: 30,
                      height: 30,
                    }}
                    title={t("common.actions.delete")}
                  >
                    <DeleteIcon sx={{ fontSize: 16 }} />
                  </IconButton>
                )}
              </Box>
            )}
          </Box>
        </Box>

        {/* Bottom control bar (full variant only) */}
        {!isCompact && (
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 0.5,
              px: 1,
              py: 0.75,
              bgcolor: "background.paper",
              borderTop: "1px solid",
              borderColor: (theme) => alpha(theme.palette.divider, 0.08),
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {!isClipMode && (
              <IconButton
                size="small"
                onClick={handleDownloadClick}
                sx={{
                  color: "primary.main",
                  "&:hover": { bgcolor: "primary.main", color: "primary.contrastText" },
                }}
                title={t("common.actions.download")}
              >
                <DownloadIcon fontSize="small" />
              </IconButton>
            )}

            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                onAddToCollectionClick?.(e);
              }}
              sx={{
                color: "primary.main",
                "&:hover": { bgcolor: "primary.main", color: "primary.contrastText" },
              }}
              title={
                showRemoveButton
                  ? t("common.actions.removeFromCollection")
                  : t("common.actions.addToCollection")
              }
            >
              {showRemoveButton ? <RemoveIcon fontSize="small" /> : <AddIcon fontSize="small" />}
            </IconButton>

            <Button
              size="small"
              variant="outlined"
              onClick={(e) => {
                e.stopPropagation();
                onAssetClick();
              }}
              sx={{
                flex: 1,
                mx: 0.5,
                minWidth: "40px",
                fontSize: "0.7rem",
                py: 0.4,
                textTransform: "none",
                borderColor: (theme) => alpha(theme.palette.primary.main, 0.3),
              }}
              title={t("common.actions.assetDetail")}
            >
              <Box
                sx={{
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  width: "100%",
                  textAlign: "center",
                }}
              >
                {t("common.actions.assetDetail")}
              </Box>
            </Button>

            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                onFavoriteToggle?.(e);
              }}
              sx={{
                color: isFavorite ? "error.main" : "primary.main",
                "&:hover": {
                  bgcolor: isFavorite ? "error.main" : "primary.main",
                  color: "primary.contrastText",
                },
              }}
              title={isFavorite ? t("favorites.removeFavorite") : t("favorites.addFavorite")}
              data-testid="favorite-button"
            >
              {isFavorite ? (
                <FavoriteIcon fontSize="small" />
              ) : (
                <FavoriteBorderIcon fontSize="small" />
              )}
            </IconButton>

            {!isClipMode && (
              <IconButton
                size="small"
                onClick={handleDeleteClick}
                sx={{
                  color: "primary.main",
                  "&:hover": { bgcolor: "primary.main", color: "primary.contrastText" },
                }}
                title={t("common.actions.delete")}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            )}
          </Box>
        )}

        {/* Checkbox for bulk selection - top left of thumbnail */}
        <Box
          sx={{
            position: "absolute",
            top: 12,
            left: 12,
            zIndex: 10,
            opacity: shouldShowButtons || isSelected ? 1 : 0,
            transition: "opacity 0.2s ease-in-out",
            pointerEvents: shouldShowButtons || isSelected ? "auto" : "none",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <Box
            sx={(theme) => ({
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              bgcolor: isSelected
                ? alpha(theme.palette.primary.main, 0.9)
                : alpha(theme.palette.background.paper, 0.85),
              borderRadius: "50%",
              width: 26,
              height: 26,
              backdropFilter: "blur(4px)",
              transition: "all 0.2s ease-in-out",
              "&:hover": {
                bgcolor: alpha(theme.palette.background.default, 0.95),
              },
            })}
            onClick={(e) => {
              e.stopPropagation();
              onSelectToggle?.(id, e);
            }}
          >
            <Checkbox
              size="small"
              disableRipple
              checked={isSelected}
              data-testid="asset-checkbox"
              onClick={(e) => {
                e.stopPropagation();
                onSelectToggle?.(id, e);
              }}
              icon={<CheckBoxOutlineBlankIcon />}
              checkedIcon={<CheckBoxIcon />}
              sx={{
                padding: 0,
                color: isSelected ? "common.white" : undefined,
                "&.Mui-checked": { color: "common.white" },
                "& .MuiSvgIcon-root": { fontSize: 16 },
              }}
            />
          </Box>
        </Box>

        {/* Info section */}
        {showMetadata && isCompact && (
          <Box sx={{ px: 1.5, pt: 1, pb: 1, cursor: "pointer" }} onClick={onAssetClick}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 0.75 }}>
              {isEditing && onEditClick ? (
                <Box
                  sx={{ width: "100%", display: "flex", flexDirection: "column", gap: 0.5 }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <InlineTextEditor
                    initialValue={editedName || ""}
                    editingCellId={id}
                    preventCommitRef={preventCommitRef}
                    commitRef={commitRef}
                    onChangeCommit={(value) => {
                      onEditNameChange?.({
                        target: { value },
                      } as React.ChangeEvent<HTMLInputElement>);
                    }}
                    onComplete={(save, value) => onEditNameComplete?.(save, value)}
                    isEditing={true}
                    disabled={isRenaming}
                    autoFocus
                    size="small"
                    fullWidth
                    sx={{ "& .MuiInputBase-root": { fontSize: "0.82rem" } }}
                    InputProps={{ endAdornment: isRenaming && <CircularProgress size={14} /> }}
                  />
                  <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 0.5 }}>
                    <Button
                      size="small"
                      variant="contained"
                      disabled={isRenaming}
                      onMouseDown={(e) => {
                        e.stopPropagation();
                        e.preventDefault();
                        preventCommitRef.current = true;
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        e.preventDefault();
                        preventCommitRef.current = false;
                        commitRef.current?.();
                      }}
                      sx={{ fontSize: "0.7rem", py: 0.25, px: 1, minWidth: 0 }}
                    >
                      Save
                    </Button>
                    <Button
                      size="small"
                      disabled={isRenaming}
                      onMouseDown={(e) => {
                        e.stopPropagation();
                        preventCommitRef.current = true;
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        onEditNameComplete?.(false, undefined);
                      }}
                      sx={{ fontSize: "0.7rem", py: 0.25, px: 1, minWidth: 0 }}
                    >
                      Cancel
                    </Button>
                  </Box>
                </Box>
              ) : (
                <>
                  <Typography
                    variant="subtitle2"
                    component="h4"
                    title={name}
                    sx={{
                      fontWeight: 600,
                      fontSize: "0.82rem",
                      lineHeight: 1.4,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      flex: 1,
                    }}
                  >
                    {name}
                  </Typography>
                  {onEditClick && (
                    <IconButton
                      size="small"
                      onClick={(e) => {
                        e.stopPropagation();
                        onEditClick(e);
                      }}
                      disabled={isRenaming}
                      sx={{ p: 0.25 }}
                    >
                      {isRenaming ? (
                        <CircularProgress size={12} />
                      ) : (
                        <EditIcon sx={{ fontSize: 14 }} />
                      )}
                    </IconButton>
                  )}
                </>
              )}
            </Box>
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.7rem" }}>
                {visibleFields
                  .filter((f) => f.id !== "name")
                  .map((f) => String(renderField(f.id)))
                  .filter(Boolean)
                  .join(" · ")}
              </Typography>
              {assetType && (
                <Box
                  component="span"
                  sx={(theme) => ({
                    display: "inline-flex",
                    alignItems: "center",
                    height: 20,
                    px: 1,
                    borderRadius: 10,
                    fontSize: "0.65rem",
                    fontWeight: 500,
                    color: theme.palette.primary.main,
                    bgcolor: alpha(theme.palette.primary.main, 0.08),
                    border: "1px solid",
                    borderColor: alpha(theme.palette.primary.main, 0.2),
                    whiteSpace: "nowrap",
                  })}
                >
                  {assetType}
                </Box>
              )}
            </Box>
          </Box>
        )}

        {/* Metadata section (full variant) */}
        {showMetadata && !isCompact && (
          <Box sx={{ px: 1.5, pt: 1.5, pb: 1.5 }}>
            <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
              {visibleFields.map((field) => (
                <Box
                  key={field.id}
                  sx={{
                    display: "grid",
                    gridTemplateColumns: "80px 1fr",
                    alignItems: "center",
                    width: "100%",
                  }}
                >
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ flexShrink: 0, pr: 1, fontSize: "0.75rem" }}
                  >
                    {field.label}:
                  </Typography>
                  {field.id === "name" && onEditClick ? (
                    isEditing ? (
                      <Box
                        sx={{
                          gridColumn: "1 / span 2",
                          display: "flex",
                          flexDirection: "column",
                          gap: 1,
                          width: "100%",
                          mt: 1,
                        }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <InlineTextEditor
                          initialValue={editedName || ""}
                          editingCellId={id}
                          preventCommitRef={preventCommitRef}
                          commitRef={commitRef}
                          onChangeCommit={(value) => {
                            onEditNameChange?.({
                              target: { value },
                            } as React.ChangeEvent<HTMLInputElement>);
                          }}
                          onComplete={(save, value) => onEditNameComplete?.(save, value)}
                          isEditing={true}
                          disabled={isRenaming}
                          autoFocus
                          size="small"
                          fullWidth
                          multiline
                          rows={2}
                          sx={{
                            width: "100%",
                            "& .MuiInputBase-root": { width: "100%" },
                            "& .MuiInputBase-input": {
                              whiteSpace: "normal",
                              wordBreak: "break-word",
                            },
                          }}
                          InputProps={{
                            endAdornment: isRenaming && <CircularProgress size={16} />,
                          }}
                        />
                        <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1 }}>
                          <Button
                            size="small"
                            variant="contained"
                            disabled={isRenaming}
                            onMouseDown={(e) => {
                              e.stopPropagation();
                              e.preventDefault();
                              preventCommitRef.current = true;
                            }}
                            onClick={(e) => {
                              e.stopPropagation();
                              e.preventDefault();
                              preventCommitRef.current = false;
                              commitRef.current?.();
                            }}
                          >
                            Save
                          </Button>
                          <Button
                            size="small"
                            disabled={isRenaming}
                            onMouseDown={(e) => {
                              e.stopPropagation();
                              preventCommitRef.current = true;
                            }}
                            onClick={(e) => {
                              e.stopPropagation();
                              onEditNameComplete?.(false, undefined);
                            }}
                          >
                            Cancel
                          </Button>
                        </Box>
                      </Box>
                    ) : (
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          width: "100%",
                          justifyContent: "space-between",
                        }}
                      >
                        <Typography
                          variant="body2"
                          title={String(renderField(field.id))}
                          sx={{
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "normal",
                            wordBreak: "break-word",
                            flexGrow: 1,
                            userSelect: "text",
                            maxHeight: "2.4em",
                            lineHeight: "1.2em",
                            display: "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: "vertical",
                            "&:hover": { maxHeight: "none", WebkitLineClamp: "unset" },
                          }}
                        >
                          {renderField(field.id)}
                        </Typography>
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            onEditClick(e);
                          }}
                          disabled={isRenaming}
                        >
                          {isRenaming ? (
                            <CircularProgress size={16} />
                          ) : (
                            <EditIcon fontSize="small" />
                          )}
                        </IconButton>
                      </Box>
                    )
                  ) : (
                    <Typography
                      variant="body2"
                      title={String(renderField(field.id))}
                      sx={{
                        userSelect: "text",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "normal",
                        wordBreak: "break-word",
                        width: "100%",
                        maxHeight: "2.4em",
                        lineHeight: "1.2em",
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        "&:hover": { maxHeight: "none", WebkitLineClamp: "unset" },
                      }}
                    >
                      {renderField(field.id)}
                    </Typography>
                  )}
                </Box>
              ))}
            </Box>
          </Box>
        )}
      </Box>
    );
  }
);

// Utility function to iterate through all video asset divs and log their IDs
export const logAllVideoAssetIds = () => {
  const videoAssetDivs = document.querySelectorAll('[id^="video-asset-"]');
  console.log(`Found ${videoAssetDivs.length} video asset divs:`);

  videoAssetDivs.forEach((div) => {
    const id = div.id;
    const assetId = id.replace("video-asset-", "");
    console.log(`Video Asset ID: ${assetId}`);

    // Also log the corresponding Omakase player ID
    const playerId = `omakase-player-${assetId}`;
    const playerElement = document.getElementById(playerId);
    if (playerElement) {
      console.log(`  └─ Omakase Player ID: ${playerId} (found)`);
    } else {
      console.log(`  └─ Omakase Player ID: ${playerId} (not found)`);
    }
  });

  return Array.from(videoAssetDivs).map((div) => div.id.replace("video-asset-", ""));
};

// Utility function to get all video asset IDs as an array
export const getAllVideoAssetIds = (): string[] => {
  const videoAssetDivs = document.querySelectorAll('[id^="video-asset-"]');
  return Array.from(videoAssetDivs).map((div) => div.id.replace("video-asset-", ""));
};

// Utility function to get a specific video asset div by asset ID
export const getVideoAssetDiv = (assetId: string): HTMLDivElement | null => {
  return document.getElementById(`video-asset-${assetId}`) as HTMLDivElement;
};

// Utility function to get all Omakase player IDs
export const getAllOmakasePlayerIds = (): string[] => {
  const playerDivs = document.querySelectorAll('[id^="omakase-player-"]');
  return Array.from(playerDivs).map((div) => div.id);
};

// Utility function to get a specific Omakase player element by asset ID
export const getOmakasePlayerElement = (assetId: string): HTMLDivElement | null => {
  return document.getElementById(`omakase-player-${assetId}`) as HTMLDivElement;
};

export default AssetCard;
