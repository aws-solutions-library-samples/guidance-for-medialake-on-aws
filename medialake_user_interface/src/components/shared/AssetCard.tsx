import React, { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useSemanticSearch } from "@/stores/searchStore";
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
    const semanticMode = useSemanticMode();
    const isSemanticSearchActive = useSemanticSearch();
    const isClipMode = isSemanticSearchActive && semanticMode === "clip";

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
                          const markerColor = getMarkerColorByConfidence(clip.score);

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
                const markerColor = getMarkerColorByConfidence(clip.score);

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

    // Determine the card dimensions based on props
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
          transition: "all 0.2s ease-in-out",
          "&:hover": {
            transform: "translateY(-4px)",
          },
        }}
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}
      >
        <Box
          sx={{
            borderRadius: 4, // Increased from 2 to 4 for more curved corners
            overflow: "hidden",
            bgcolor: "background.paper",
            boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
            position: "relative", // Ensure this is a positioning context
            "&:hover": {
              boxShadow: "0 8px 16px rgba(0,0,0,0.1)",
            },
          }}
        >
          {/* Render appropriate content based on asset type */}
          {assetType === "Video" || assetType === "Audio" ? (
            <Box sx={{ display: "flex", flexDirection: "column" }}>
              {proxyUrl && !videoLoadError ? (
                <div
                  id={`${assetType.toLowerCase()}-asset-${id}`}
                  className={`asset-card-${assetType.toLowerCase()}`}
                  style={{
                    width: dimensions.width,
                    height: dimensions.height,
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
                    width: dimensions.width,
                    height: dimensions.height,
                    backgroundColor: "rgba(0,0,0,0.03)",
                    objectFit: thumbnailScale === "fit" ? "contain" : "cover",
                    transition: "all 0.2s ease-in-out",
                  }}
                />
              )}

              {/* Video/Audio Control Bar */}
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 1,
                  p: 1,
                  bgcolor: "background.paper",
                  borderTop: "1px solid",
                  borderColor: "divider",
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <IconButton
                  size="small"
                  onClick={handleDownloadClick}
                  sx={{
                    color: "primary.main",
                    "&:hover": {
                      bgcolor: "primary.main",
                      color: "primary.contrastText",
                    },
                  }}
                  title={t("common.actions.download")}
                >
                  <DownloadIcon fontSize="small" />
                </IconButton>

                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onAddToCollectionClick) {
                      onAddToCollectionClick(e);
                    }
                  }}
                  sx={{
                    color: "primary.main",
                    "&:hover": {
                      bgcolor: "primary.main",
                      color: "primary.contrastText",
                    },
                  }}
                  title={t("common.actions.addToCollection")}
                >
                  {showRemoveButton ? (
                    <RemoveIcon fontSize="small" />
                  ) : (
                    <AddIcon fontSize="small" />
                  )}
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
                    mx: 1,
                    minWidth: "40px",
                    fontSize: "0.75rem",
                    py: 0.5,
                    textAlign: "center",
                    justifyContent: "center",
                    overflow: "hidden",
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

                {/* Favorite button */}
                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onFavoriteToggle) {
                      onFavoriteToggle(e);
                    }
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

                <IconButton
                  size="small"
                  onClick={handleDeleteClick}
                  sx={{
                    color: "primary.main",
                    "&:hover": {
                      bgcolor: "primary.main",
                      color: "primary.contrastText",
                    },
                  }}
                  title={t("common.actions.delete")}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Box>
            </Box>
          ) : (
            <Box sx={{ display: "flex", flexDirection: "column" }}>
              <Box
                onClick={onAssetClick}
                component="img"
                src={thumbnailUrl || placeholderImage}
                alt={name}
                onError={onImageError || defaultImageErrorHandler}
                data-image-id={id}
                sx={{
                  cursor: "pointer",
                  width: dimensions.width,
                  height: dimensions.height,
                  backgroundColor: "rgba(0,0,0,0.03)",
                  objectFit: thumbnailScale === "fit" ? "contain" : "cover",
                  transition: "all 0.2s ease-in-out",
                }}
              />

              {/* Image Control Bar */}
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 1,
                  p: 1,
                  bgcolor: "background.paper",
                  borderTop: "1px solid",
                  borderColor: "divider",
                }}
                onClick={(e) => e.stopPropagation()}
              >
                {!isClipMode && (
                  <IconButton
                    size="small"
                    onClick={handleDownloadClick}
                    sx={{
                      color: "primary.main",
                      "&:hover": {
                        bgcolor: "primary.main",
                        color: "primary.contrastText",
                      },
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
                    "&:hover": {
                      bgcolor: "primary.main",
                      color: "primary.contrastText",
                    },
                  }}
                  title={showRemoveButton ? "Remove from Collection" : "Add to Collection"}
                >
                  {showRemoveButton ? (
                    <RemoveIcon fontSize="small" />
                  ) : (
                    <AddIcon fontSize="small" />
                  )}
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
                    mx: 1,
                    minWidth: "40px",
                    fontSize: "0.75rem",
                    py: 0.5,
                    textAlign: "center",
                    justifyContent: "center",
                    overflow: "hidden",
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
                    Asset Detail
                  </Box>
                </Button>

                {/* Favorite button */}
                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onFavoriteToggle) {
                      onFavoriteToggle(e);
                    }
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
                      "&:hover": {
                        bgcolor: "primary.main",
                        color: "primary.contrastText",
                      },
                    }}
                    title={t("common.actions.delete")}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                )}
              </Box>
            </Box>
          )}

          {/* Position checkbox at the top left of the card */}
          <Box
            sx={{
              position: "absolute",
              top: 8,
              left: 8,
              display: "flex",
              gap: 1,
              zIndex: 1000, // Keep high z-index to ensure it's above other elements
              opacity: shouldShowButtons || isSelected ? 1 : 0, // Visible when hovering or selected
              transition: "opacity 0.2s ease-in-out",
              pointerEvents: shouldShowButtons || isSelected ? "auto" : "none", // Ensure buttons are clickable when visible
              "&:hover": {
                opacity: shouldShowButtons || isSelected ? 1 : 0,
              },
            }}
            onClick={(e) => e.stopPropagation()} // Stop propagation at the container level
          >
            {/* Checkbox for bulk selection */}
            {
              <Box
                sx={(theme) => ({
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                  // if selected and not hovered, make it transparent; otherwise show the light circle
                  bgcolor: isSelected ? "transparent" : alpha(theme.palette.background.paper, 0.7),
                  borderRadius: "50%",
                  width: 28,
                  height: 28,
                  transition: "all 0.2s ease-in-out",
                  "&:hover": {
                    // on hover always show the background
                    bgcolor: alpha(theme.palette.background.default, 0.9),
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
                    "& .MuiSvgIcon-root": {
                      fontSize: 18,
                    },
                  }}
                />
              </Box>
            }
          </Box>

          {/* Position buttons at the top right of the card, visible on hover or when menu is open - Removed since all assets now have bottom control bars */}
          {false && (
            <Box
              sx={{
                position: "absolute",
                top: 8,
                right: 8,
                display: "flex",
                gap: 1,
                zIndex: 10, // Increased z-index to ensure buttons are above other elements
                opacity: shouldShowButtons ? 1 : 0, // Visible when hovering or menu is clicked
                transition: "opacity 0.2s ease-in-out",
                pointerEvents: shouldShowButtons ? "auto" : "none", // Ensure buttons are clickable when visible
              }}
              onClick={(e) => e.stopPropagation()} // Stop propagation at the container level
            >
              <IconButton
                size="small"
                onClick={handleDeleteClick}
                sx={(theme) => ({
                  bgcolor: alpha(theme.palette.background.paper, 0.7),
                  padding: "4px",
                  "&:hover": {
                    bgcolor: alpha(theme.palette.background.default, 0.9),
                  },
                })}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
              <IconButton
                size="small"
                onClick={handleDownloadClick}
                sx={(theme) => ({
                  bgcolor: alpha(theme.palette.background.paper, 0.7),
                  padding: "4px",
                  "&:hover": {
                    bgcolor: alpha(theme.palette.background.default, 0.9),
                  },
                })}
              >
                <DownloadIcon fontSize="small" />
              </IconButton>
            </Box>
          )}

          {/* Metadata section */}
          {showMetadata && (
            <Box sx={{ p: 2 }}>
              <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
                {visibleFields.map((field) => (
                  <Box
                    key={field.id}
                    sx={{
                      display: "grid",
                      gridTemplateColumns: "100px 1fr",
                      alignItems: "center",
                      width: "100%",
                    }}
                  >
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{
                        flexShrink: 0,
                        paddingRight: 1,
                      }}
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
                        >
                          <InlineTextEditor
                            initialValue={editedName || ""}
                            editingCellId={id} // ← pass a stable ID (e.g. asset ID)
                            preventCommitRef={preventCommitRef} // ← pass the ref to prevent commit
                            commitRef={commitRef} // ← pass the ref to expose commit function
                            onChangeCommit={(value) => {
                              // Update parent state
                              onEditNameChange({
                                target: { value },
                              } as React.ChangeEvent<HTMLInputElement>);
                            }}
                            onComplete={(save, value) => {
                              console.log("🎯 AssetCard onComplete - save:", save, "value:", value);
                              console.log(
                                "🎯 Calling onEditNameComplete with save:",
                                save,
                                "value:",
                                value
                              );
                              onEditNameComplete?.(save, value);
                            }}
                            isEditing={true}
                            disabled={isRenaming}
                            autoFocus
                            size="small"
                            fullWidth
                            multiline
                            rows={2}
                            sx={{
                              width: "100%",
                              "& .MuiInputBase-root": {
                                width: "100%",
                              },
                              "& .MuiInputBase-input": {
                                whiteSpace: "normal",
                                wordBreak: "break-word",
                              },
                            }}
                            InputProps={{
                              endAdornment: isRenaming && <CircularProgress size={16} />,
                            }}
                          />
                          <Box
                            sx={{
                              display: "flex",
                              justifyContent: "flex-end",
                              gap: 1,
                            }}
                          >
                            <Button
                              size="small"
                              onMouseDown={(e) => {
                                e.stopPropagation();
                                e.preventDefault();
                                console.log("💾 AssetCard Save mousedown");
                                // Set flag to prevent blur from canceling
                                preventCommitRef.current = true;
                              }}
                              onClick={(e) => {
                                e.stopPropagation();
                                e.preventDefault();
                                console.log("💾 AssetCard Save clicked");
                                console.log("💾 AssetCard commitRef.current:", commitRef.current);
                                // Reset the prevent flag
                                preventCommitRef.current = false;
                                // Call the commit function directly via ref
                                if (commitRef.current) {
                                  console.log("💾 AssetCard calling commitRef.current()");
                                  commitRef.current();
                                } else {
                                  console.error("💾 AssetCard commitRef.current is null!");
                                }
                              }}
                              variant="contained"
                              disabled={isRenaming}
                            >
                              Save
                            </Button>
                            <Button
                              size="small"
                              disabled={isRenaming}
                              onMouseDown={(e) => {
                                e.stopPropagation();
                                console.log("🚫 AssetCard Cancel clicked");
                                // Set flag to prevent InlineTextEditor commit from being called
                                // Use onMouseDown instead of onClick to set the flag before onBlur
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
                            sx={{
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "normal",
                              wordBreak: "break-word",
                              flexGrow: 1,
                              userSelect: "text", // Allow text selection
                              maxHeight: "2.4em", // Limit to exactly 2 lines
                              lineHeight: "1.2em",
                              display: "-webkit-box",
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: "vertical",
                              position: "relative",
                              "&:after": {
                                content: '"..."',
                                position: "absolute",
                                bottom: 0,
                                right: 0,
                                paddingLeft: "4px",
                                backgroundColor: "inherit",
                                boxShadow: "-8px 0 8px rgba(255,255,255,0.8)",
                                display: "none",
                              },
                              "&.truncated:after": {
                                display: "inline",
                              },
                              "&:hover": {
                                maxHeight: "none", // Remove height limit on hover
                                WebkitLineClamp: "unset",
                                "&:after": {
                                  display: "none",
                                },
                              },
                            }}
                            className={String(renderField(field.id)).length > 60 ? "truncated" : ""}
                            display="inline"
                            variant="body2"
                            title={String(renderField(field.id))}
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
                      <Box sx={{ width: "100%" }}>
                        <Typography
                          variant="body2"
                          sx={{
                            userSelect: "text",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "normal",
                            wordBreak: "break-word",
                            width: "100%",
                            maxHeight: "2.4em", // Limit to exactly 2 lines
                            lineHeight: "1.2em",
                            display: "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: "vertical",
                            position: "relative",
                            "&:after": {
                              content: '"..."',
                              position: "absolute",
                              bottom: 0,
                              right: 0,
                              paddingLeft: "4px",
                              backgroundColor: "inherit",
                              boxShadow: "-8px 0 8px rgba(255,255,255,0.8)",
                              display: "none",
                            },
                            "&.truncated:after": {
                              display: "inline",
                            },
                            "&:hover": {
                              maxHeight: "none", // Remove height limit on hover
                              WebkitLineClamp: "unset",
                              "&:after": {
                                display: "none",
                              },
                            },
                          }}
                          className={String(renderField(field.id)).length > 60 ? "truncated" : ""}
                          title={String(renderField(field.id))}
                        >
                          {renderField(field.id)}
                        </Typography>
                      </Box>
                    )}
                  </Box>
                ))}
              </Box>
            </Box>
          )}
        </Box>
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
