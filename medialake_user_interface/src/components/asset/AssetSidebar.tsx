import React, { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useGeneratePresignedUrl } from "../../api/hooks/usePresignedUrl";
import { useSemanticSearchStatus } from "../../features/settings/system/hooks/useSystemSettings";
import { fetchUserAttributes } from "aws-amplify/auth";
import { UserAvatar } from "../common/UserAvatar";
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Button,
  IconButton,
  Badge,
  TextField,
  alpha,
  useTheme,
  Tooltip,
  CircularProgress,
  Slider,
  FormControlLabel,
  Switch,
  Paper,
  Avatar,
} from "@mui/material";
import { useSnackbar } from "notistack";
import { RightSidebar } from "../common/RightSidebar";

// Icons
import HistoryIcon from "@mui/icons-material/History";
import BookmarkIcon from "@mui/icons-material/Bookmark";
import PersonIcon from "@mui/icons-material/Person";
import PlayCircleOutlineIcon from "@mui/icons-material/PlayCircleOutline";
import ImageIcon from "@mui/icons-material/Image";
import PictureAsPdfIcon from "@mui/icons-material/PictureAsPdf";
import MovieIcon from "@mui/icons-material/Movie";
import DownloadIcon from "@mui/icons-material/Download";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import CloseIcon from "@mui/icons-material/Close";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import RestoreIcon from "@mui/icons-material/Restore";
import GroupsIcon from "@mui/icons-material/Groups";
import SendIcon from "@mui/icons-material/Send";
import AccountTreeIcon from "@mui/icons-material/AccountTree";
import TimelineIcon from "@mui/icons-material/Timeline";
import { randomHexColor, getMarkerColorByConfidence } from "../common/utils";
import type { DetailMarkerAdapter, MarkerApi } from "../player/marker-sync/ports";
import { getPlayerCurrentTime } from "../player/playerTimeStore";

/** Marker display info used by the sidebar UI. Extends MarkerApi with display-only fields. */
interface MarkerInfo extends MarkerApi {
  name?: string;
  style: { color: string };
  createdAt?: number;
  model_version?: string;
}

// Storage utilities for confidence level persistence
const CONFIDENCE_LEVEL_STORAGE_KEY = "medialake_confidence_level";

const loadConfidenceLevelFromStorage = (): number | null => {
  try {
    const stored = localStorage.getItem(CONFIDENCE_LEVEL_STORAGE_KEY);
    return stored ? parseFloat(stored) : null;
  } catch (error) {
    console.warn("Failed to load confidence level from localStorage:", error);
    return null;
  }
};

const saveConfidenceLevelToStorage = (confidenceLevel: number): void => {
  try {
    localStorage.setItem(CONFIDENCE_LEVEL_STORAGE_KEY, confidenceLevel.toString());
  } catch (error) {
    console.error("Failed to save confidence level to localStorage:", error);
  }
};

// Utility functions for timecode editing
const parseTimecodeToSeconds = (timecode: string): number | null => {
  // Support formats: HH:MM:SS:FF, HH:MM:SS.mmm, MM:SS.mmm, SS.mmm, or just seconds
  const patterns = [
    /^(\d{1,2}):(\d{2}):(\d{2}):(\d{2})$/, // HH:MM:SS:FF (frames)
    /^(\d{1,2}):(\d{2}):(\d{2})\.(\d{3})$/, // HH:MM:SS.mmm
    /^(\d{1,2}):(\d{2})\.(\d{3})$/, // MM:SS.mmm
    /^(\d{1,2})\.(\d{3})$/, // SS.mmm
    /^(\d+(?:\.\d+)?)$/, // Just seconds (decimal)
  ];

  for (let i = 0; i < patterns.length; i++) {
    const match = timecode.match(patterns[i]);

    if (match) {
      let result: number;
      switch (i) {
        case 0: // HH:MM:SS:FF (frames) - assume 30fps
          result =
            parseInt(match[1]) * 3600 +
            parseInt(match[2]) * 60 +
            parseInt(match[3]) +
            parseInt(match[4]) / 30;
          break;
        case 1: // HH:MM:SS.mmm
          result =
            parseInt(match[1]) * 3600 +
            parseInt(match[2]) * 60 +
            parseInt(match[3]) +
            parseInt(match[4]) / 1000;
          break;
        case 2: // MM:SS.mmm
          result = parseInt(match[1]) * 60 + parseInt(match[2]) + parseInt(match[3]) / 1000;
          break;
        case 3: // SS.mmm
          result = parseInt(match[1]) + parseInt(match[2]) / 1000;
          break;
        case 4: // Just seconds
          result = parseFloat(match[1]);
          break;
        default:
          result = 0;
      }
      return result;
    }
  }

  return null;
};

const formatSecondsToTimecode = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const frames = Math.floor((seconds % 1) * 30); // Assume 30fps

  // Always use HH:MM:SS:FF format to match the system
  return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${secs
    .toString()
    .padStart(2, "0")}:${frames.toString().padStart(2, "0")}`;
};

// Editable Timecode Component
const EditableTimecode: React.FC<{
  value: number;
  markerId: string;
  field: "start" | "end";
  onUpdate: (markerId: string, field: "start" | "end", newTimeSeconds: number) => void;
}> = ({ value, markerId, field, onUpdate }) => {
  const { t } = useTranslation();
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState("");

  const handleStartEdit = () => {
    const formattedTime = formatSecondsToTimecode(value);
    setEditValue(formattedTime);
    setIsEditing(true);
  };

  const handleSaveEdit = () => {
    const newTimeSeconds = parseTimecodeToSeconds(editValue);

    if (newTimeSeconds !== null) {
      onUpdate(markerId, field, newTimeSeconds);
    } else {
      console.warn("Failed to parse timecode:", editValue);
    }
    setIsEditing(false);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditValue("");
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSaveEdit();
    } else if (e.key === "Escape") {
      handleCancelEdit();
    }
  };

  if (isEditing) {
    return (
      <TextField
        size="small"
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onBlur={handleSaveEdit}
        onKeyDown={(e) => {
          // Prevent video player keyboard shortcuts when editing timecode
          e.stopPropagation();
          handleKeyPress(e);
        }}
        autoFocus
        sx={{
          "& .MuiInputBase-input": {
            fontSize: "0.75rem",
            padding: "2px 4px",
            minWidth: "80px",
          },
        }}
      />
    );
  }

  return (
    <Typography
      variant="caption"
      sx={{
        color: "text.secondary",
        cursor: "pointer",
        "&:hover": {
          color: "primary.main",
          textDecoration: "underline",
        },
      }}
      onClick={handleStartEdit}
      title={t("common.clickToEdit")}
    >
      {formatSecondsToTimecode(value)}
    </Typography>
  );
};

interface AssetSidebarProps {
  versions?: any[];
  comments?: any[];
  onAddComment?: (comment: string) => void;
  markerAdapter?: DetailMarkerAdapter;
  isMarkerReady?: boolean;
  seek?: (time: number) => void;
  assetId?: string;
  asset?: any;
  assetType?: string;
  searchTerm?: string;
}

interface AssetVersionProps {
  versions: any[];
}

interface AssetMarkersProps {
  onMarkerAdd?: () => void;
  markerAdapter?: DetailMarkerAdapter;
  isMarkerReady?: boolean;
  seek?: (time: number) => void;
  markers?: MarkerInfo[];
  setMarkers?: React.Dispatch<React.SetStateAction<MarkerInfo[]>>;
  asset: any;
  assetId?: string;
  assetType: string;
  searchTerm?: string;
  clipsMarkersCreated: boolean;
  setClipsMarkersCreated: (created: boolean) => void;
}

interface AssetCollaborationProps {
  comments?: any[];
  onAddComment?: (comment: string) => void;
}

interface AssetPipelinesProps {
  // No props required currently
}

interface AssetActivityProps {
  // No props required currently
}

// Version content component (using existing data)
const AssetVersions: React.FC<AssetVersionProps> = ({ versions = [] }) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const generatePresignedUrl = useGeneratePresignedUrl();
  const [downloadingVersionId, setDownloadingVersionId] = useState<string | null>(null);

  const handleDownload = async (version: any) => {
    try {
      setDownloadingVersionId(version.id);

      // Always generate a presigned URL
      // Determine the purpose based on version type
      const purpose = version.type.toLowerCase();

      const result = await generatePresignedUrl.mutateAsync({
        inventoryId: version.inventoryId || version.assetId,
        expirationTime: 60, // 1 minute in seconds
        purpose: purpose, // Pass the purpose to get the correct representation
      });

      // Create a temporary link element
      const link = document.createElement("a");
      link.href = result.presigned_url;

      // Use version name or extract filename from the URL
      const fileName = version.name || (version.src ? version.src.split("/").pop() : purpose);
      link.setAttribute("download", fileName);

      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (error) {
      console.error("Error downloading file:", error);
    } finally {
      setDownloadingVersionId(null);
    }
  };

  const getVersionIcon = (version: any) => {
    const type = version.type.toLowerCase();

    if (type === "original") {
      return <MovieIcon fontSize="small" color="primary" sx={{ mr: 1 }} />;
    } else if (type === "proxy" || type.includes("proxy")) {
      return <PlayCircleOutlineIcon fontSize="small" color="secondary" sx={{ mr: 1 }} />;
    } else if (type === "thumbnail" || type.includes("thumb")) {
      return <ImageIcon fontSize="small" color="success" sx={{ mr: 1 }} />;
    } else if (type === "pdf" || version.format?.toLowerCase()?.includes("pdf")) {
      return <PictureAsPdfIcon fontSize="small" color="error" sx={{ mr: 1 }} />;
    }

    // Default icon based on format
    if (
      version.format?.toLowerCase()?.includes("video") ||
      version.format?.toLowerCase()?.includes("mp4")
    ) {
      return <MovieIcon fontSize="small" color="primary" sx={{ mr: 1 }} />;
    } else if (
      version.format?.toLowerCase()?.includes("image") ||
      version.format?.toLowerCase()?.includes("jpg") ||
      version.format?.toLowerCase()?.includes("png")
    ) {
      return <ImageIcon fontSize="small" color="success" sx={{ mr: 1 }} />;
    }

    return <InfoOutlinedIcon fontSize="small" color="action" sx={{ mr: 1 }} />;
  };

  return (
    <List disablePadding sx={{ p: 1.5 }}>
      {versions.length === 0 ? (
        <Box
          sx={{
            p: 3,
            textAlign: "center",
            bgcolor: (theme) => alpha(theme.palette.background.default, 0.4),
            borderRadius: "10px",
            border: "1px dashed",
            borderColor: (theme) => alpha(theme.palette.divider, 0.3),
          }}
        >
          <HistoryIcon sx={{ fontSize: 28, opacity: 0.2, mb: 0.5, display: "block", mx: "auto" }} />
          <Typography variant="body2" color="text.secondary" sx={{ fontSize: "0.8rem" }}>
            No versions available
          </Typography>
        </Box>
      ) : (
        versions.map((version, index) => (
          <React.Fragment key={version.id}>
            <ListItem
              alignItems="flex-start"
              sx={{
                py: 1.5,
                px: 1.5,
                borderRadius: "10px",
                border: "1px solid",
                borderColor: (theme) => alpha(theme.palette.divider, 0.08),
                bgcolor: (theme) => alpha(theme.palette.background.default, 0.3),
                mb: 1,
                transition:
                  "background-color 0.2s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
                "&:hover": {
                  bgcolor: (theme) => alpha(theme.palette.primary.main, 0.04),
                  borderColor: (theme) => alpha(theme.palette.primary.main, 0.15),
                  boxShadow: (theme) => `0 2px 8px ${alpha(theme.palette.common.black, 0.04)}`,
                },
              }}
            >
              <Box sx={{ width: "100%" }}>
                <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
                  {getVersionIcon(version)}
                  <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: "0.825rem" }}>
                    {version.type.charAt(0).toUpperCase() + version.type.slice(1).toLowerCase()}
                  </Typography>
                  <Box
                    component="span"
                    sx={{
                      ml: "auto",
                      display: "inline-flex",
                      px: 0.75,
                      py: 0.25,
                      borderRadius: "6px",
                      bgcolor: (theme) => alpha(theme.palette.text.secondary, 0.08),
                      fontSize: "0.7rem",
                      color: "text.secondary",
                      fontWeight: 500,
                    }}
                  >
                    {version.format}
                  </Box>
                </Box>
                <Typography variant="body2" color="text.secondary" sx={{ fontSize: "0.8rem" }}>
                  <strong>{t("assets.fields.size")}:</strong>{" "}
                  {version.size || t("common.notAvailable")}
                </Typography>
                <Box sx={{ display: "flex", mt: 1.5 }}>
                  <Tooltip title={t("common.downloadVersion")}>
                    <Button
                      variant="outlined"
                      size="small"
                      sx={{
                        mr: 1,
                        textTransform: "none",
                        borderRadius: "8px",
                        fontSize: "0.775rem",
                        fontWeight: 500,
                        borderColor: (theme) => alpha(theme.palette.divider, 0.3),
                        "&:hover": {
                          borderColor: "primary.main",
                          bgcolor: (theme) => alpha(theme.palette.primary.main, 0.04),
                        },
                      }}
                      onClick={() => handleDownload(version)}
                      disabled={downloadingVersionId === version.id}
                      startIcon={
                        downloadingVersionId === version.id ? (
                          <CircularProgress size={14} />
                        ) : (
                          <DownloadIcon sx={{ fontSize: 16 }} />
                        )
                      }
                    >
                      {downloadingVersionId === version.id ? "Downloading..." : "Download"}
                    </Button>
                  </Tooltip>
                  {/* i18n-ignore - commented out code
                  <Tooltip title="Preview this version">
                                        <Button
                                            variant="text"
                                            size="small"
                                            sx={{ textTransform: 'none' }}
                                            startIcon={<PreviewIcon fontSize="small" />}
                                        >
                                            Preview
                                        </Button>
                                    </Tooltip>
                  */}
                </Box>
              </Box>
            </ListItem>
          </React.Fragment>
        ))
      )}
    </List>
  );
};

// Markers content component
const AssetMarkers: React.FC<AssetMarkersProps> = ({
  markers,
  setMarkers,
  markerAdapter,
  isMarkerReady,
  seek,
  asset,
  assetId,

  searchTerm,
  clipsMarkersCreated,
  setClipsMarkersCreated,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const { enqueueSnackbar } = useSnackbar();
  // State to track editable marker names
  const [markerNames, setMarkerNamesState] = useState<Record<string, string>>({});
  const markerNamesRef = useRef<Record<string, string>>({});
  const setMarkerNames: typeof setMarkerNamesState = useCallback((action) => {
    setMarkerNamesState((prev) => {
      const next = typeof action === "function" ? action(prev) : action;
      markerNamesRef.current = next;
      return next;
    });
  }, []);
  // State for score threshold slider
  const [scoreThreshold, setScoreThreshold] = useState<number>(0);
  const [scoreThresholdInitialized, setScoreThresholdInitialized] = useState<boolean>(false);

  // Marker filtering state
  const [showUserMarkers, setShowUserMarkers] = useState<boolean>(true);
  const [showSemanticMarkers, setShowSemanticMarkers] = useState<boolean>(true);

  // Get search provider information
  const { providerData } = useSemanticSearchStatus();

  // User information state
  const [userName, setUserName] = useState<string>("");

  // Loading state for semantic markers
  const [isLoadingSemanticMarkers, setIsLoadingSemanticMarkers] = useState<boolean>(false);

  // Fetch user information
  useEffect(() => {
    const fetchUserInfo = async () => {
      try {
        const attributes = await fetchUserAttributes();
        const name = attributes.given_name || attributes.email?.split("@")[0] || "User";
        setUserName(name);
      } catch (error) {
        console.error("Error fetching user attributes:", error);
        setUserName("User");
      }
    };

    fetchUserInfo();
  }, []);

  // Function to sanitize and format the provider name
  const sanitizeProviderName = (name: string): string => {
    if (!name) return "semantic search";

    // Convert to title case and handle common formatting
    return name
      .split(/[-_\s]+/) // Split on hyphens, underscores, and spaces
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(" ")
      .replace(/api/i, "API") // Ensure API is uppercase
      .replace(/bedrock/i, "Bedrock"); // Ensure proper casing for Bedrock
  };

  // Function to get the display name of the current search provider
  const getSearchProviderName = useCallback(() => {
    // Debug logging to see what we're getting

    const provider = providerData?.data?.searchProvider;

    if (!provider) {
      return "semantic search";
    }

    // Use provider name first, fallback to type, then sanitize
    const rawName = provider.name || provider.type || "semantic search";

    const sanitizedName = sanitizeProviderName(rawName);

    return sanitizedName;
  }, [providerData]);
  // Initialize score threshold from localStorage or based on available clips
  useEffect(() => {
    if (!asset?.clips || !Array.isArray(asset.clips) || scoreThresholdInitialized) return;

    const storedThreshold = loadConfidenceLevelFromStorage();
    if (storedThreshold !== null) {
      setScoreThreshold(storedThreshold);
      setScoreThresholdInitialized(true);
      return;
    }

    const visualTextClips = asset.clips.filter(
      (clip) =>
        (clip.embedding_option === "visual-text" ||
          clip.embedding_option === "visual" ||
          clip.embedding_scope === "clip") &&
        clip.score !== null &&
        clip.score !== undefined
    );

    if (visualTextClips.length > 0) {
      const minScore = Math.min(...visualTextClips.map((clip) => clip.score || 0));
      const defaultThreshold = Math.max(0, minScore - 0.1);
      setScoreThreshold(defaultThreshold);
      saveConfidenceLevelToStorage(defaultThreshold);
      setScoreThresholdInitialized(true);
    }
  }, [asset?.clips, scoreThresholdInitialized]);

  // Refresh markers from adapter whenever adapter readiness changes
  const refreshMarkers = useCallback(() => {
    if (!markerAdapter?.isReady()) return;
    const adapterMarkers = markerAdapter.list();
    const names = markerNamesRef.current;
    const mapped: MarkerInfo[] = adapterMarkers.map((m) => ({
      ...m,
      name: names[m.id] || m.label,
      style: {
        color:
          m.color ||
          (m.type === "semantic" ? getMarkerColorByConfidence(m.score) : randomHexColor()),
      },
    }));
    setMarkers(mapped);
  }, [markerAdapter, setMarkers]);

  // Refresh marker list when adapter becomes ready
  useEffect(() => {
    if (isMarkerReady) {
      refreshMarkers();
    }
  }, [isMarkerReady, refreshMarkers]);

  // Subscribe to MARKER_COMMIT_FAILED_ROLLBACK_APPLIED for rollback warning
  useEffect(() => {
    if (!markerAdapter) return;
    const handler = () => {
      enqueueSnackbar(
        t("common.markerRollbackWarning", "A marker change was rolled back due to a sync error."),
        {
          variant: "warning",
          autoHideDuration: 4000,
        }
      );
      refreshMarkers();
    };
    markerAdapter.on("MARKER_COMMIT_FAILED_ROLLBACK_APPLIED", handler);
    return () => {
      markerAdapter.off("MARKER_COMMIT_FAILED_ROLLBACK_APPLIED", handler);
    };
  }, [markerAdapter, refreshMarkers, enqueueSnackbar, t]);

  // Create semantic markers from clips via adapter
  useEffect(() => {
    if (
      !markerAdapter?.isReady() ||
      !asset?.clips ||
      !Array.isArray(asset.clips) ||
      clipsMarkersCreated
    )
      return;

    const allVisualTextClips = asset.clips
      .filter((clip) => {
        const isValidEmbedding =
          clip.embedding_option === "visual-text" ||
          clip.embedding_option === "visual" ||
          clip.embedding_scope === "clip";
        const hasValidScore = clip.score !== null && clip.score !== undefined;
        const hasValidTimes =
          (clip.start_timecode || clip.start_time) && (clip.end_timecode || clip.end_time);
        return isValidEmbedding && hasValidScore && hasValidTimes;
      })
      .sort((a, b) => (b.score || 0) - (a.score || 0));

    setIsLoadingSemanticMarkers(true);

    allVisualTextClips.forEach((clip) => {
      const startTime = clip.start_timecode || clip.start_time;
      const endTime = clip.end_timecode || clip.end_time;
      const startSeconds = timecodeToSeconds(startTime);
      const endSeconds = timecodeToSeconds(endTime);
      const clipScore = clip.score !== undefined ? clip.score : undefined;
      const markerColor = getMarkerColorByConfidence(clipScore, clip.model_version);
      const defaultName = searchTerm || `Clip`;

      markerAdapter.add(
        {
          timeObservation: { start: startSeconds, end: endSeconds },
          label: defaultName,
          color: markerColor,
          score: clipScore,
          type: "semantic",
        },
        "sidebar"
      );
    });

    setClipsMarkersCreated(true);
    setIsLoadingSemanticMarkers(false);
    refreshMarkers();
  }, [
    markerAdapter,
    isMarkerReady,
    asset?.clips,
    clipsMarkersCreated,
    searchTerm,
    setClipsMarkersCreated,
    refreshMarkers,
  ]);

  // Sync confidence threshold → coordinator: remove semantic markers below threshold,
  // re-add ones above threshold that were previously removed.
  // This keeps the player's progressMarkerTrack in sync via the MARKER_ADDED/REMOVED events.
  const prevThresholdRef = useRef<number | null>(null);
  useEffect(() => {
    if (!markerAdapter?.isReady() || !clipsMarkersCreated) return;
    // Skip the first run (initial threshold set before markers exist)
    if (prevThresholdRef.current === null) {
      prevThresholdRef.current = scoreThreshold;
      return;
    }
    prevThresholdRef.current = scoreThreshold;

    // Get current semantic markers in the coordinator
    const currentMarkers = markerAdapter.list().filter((m) => m.type === "semantic");
    const currentIds = new Set(currentMarkers.map((m) => m.id));

    // Remove semantic markers that are now below threshold
    for (const m of currentMarkers) {
      if ((m.score ?? 0) < scoreThreshold) {
        markerAdapter.remove(m.id, "sidebar");
      }
    }

    // Re-add semantic markers from clips that are now above threshold but missing
    if (asset?.clips && Array.isArray(asset.clips)) {
      // Snapshot current marker IDs to avoid calling list() inside the loop
      const currentMarkerIds = new Set(markerAdapter.list().map((m) => m.id));

      const eligibleClips = asset.clips.filter((clip: any) => {
        const isValidEmbedding =
          clip.embedding_option === "visual-text" ||
          clip.embedding_option === "visual" ||
          clip.embedding_scope === "clip";
        const hasValidScore = clip.score !== null && clip.score !== undefined;
        const hasValidTimes =
          (clip.start_timecode || clip.start_time) && (clip.end_timecode || clip.end_time);
        return (
          isValidEmbedding && hasValidScore && hasValidTimes && (clip.score ?? 0) >= scoreThreshold
        );
      });

      for (const clip of eligibleClips) {
        const startTime = clip.start_timecode || clip.start_time;
        const endTime = clip.end_timecode || clip.end_time;
        const startSeconds = timecodeToSeconds(startTime);
        const endSeconds = timecodeToSeconds(endTime);
        // Reconstruct the expected coordinator ID for semantic markers
        const expectedId = `clip-${startSeconds}-${endSeconds}-${assetId}`;
        // Only add if not already present in the coordinator
        if (!currentMarkerIds.has(expectedId)) {
          const clipScore = clip.score !== undefined ? clip.score : undefined;
          const markerColor = getMarkerColorByConfidence(clipScore, clip.model_version);
          markerAdapter.add(
            {
              timeObservation: { start: startSeconds, end: endSeconds },
              label: searchTerm || "Clip",
              color: markerColor,
              score: clipScore,
              type: "semantic",
            },
            "sidebar"
          );
        }
      }
    }

    refreshMarkers();
  }, [
    scoreThreshold,
    markerAdapter,
    clipsMarkersCreated,
    asset?.clips,
    assetId,
    searchTerm,
    refreshMarkers,
  ]);

  const deleteMarker = (markerId: string) => {
    if (!markerAdapter) return;

    try {
      markerAdapter.remove(markerId, "sidebar");
      setMarkerNames((prev) => {
        const newNames = { ...prev };
        delete newNames[markerId];
        return newNames;
      });
      refreshMarkers();
    } catch (error) {
      console.error("Error deleting marker:", error);
    }
  };

  // Function to reset a specific semantic marker to original values
  const resetSemanticMarker = (markerId: string) => {
    if (!markerAdapter || !asset?.clips) return;

    try {
      const originalClip = asset.clips.find((clip) => {
        const startTime = clip.start_time || clip.start_timecode;
        const endTime = clip.end_time || clip.end_timecode;
        if (!startTime || !endTime) return false;
        const clipId = `clip_${startTime}_${endTime}`;
        return markerId.includes(clipId) || markerId.includes(startTime.toString());
      });

      if (!originalClip) return;

      const startTime = originalClip.start_time || originalClip.start_timecode;
      const endTime = originalClip.end_time || originalClip.end_timecode;
      if (!startTime || !endTime) return;

      const startSeconds = timecodeToSeconds(startTime);
      const endSeconds = timecodeToSeconds(endTime);

      markerAdapter.update(
        markerId,
        { timeObservation: { start: startSeconds, end: endSeconds } },
        "sidebar"
      );
      refreshMarkers();
    } catch (error) {
      console.error("Error resetting semantic marker:", error);
    }
  };

  // Function to update marker time (start or end) for both user and semantic markers
  const updateMarkerTime = (markerId: string, field: "start" | "end", newTimeSeconds: number) => {
    if (!markerAdapter) return;

    try {
      const marker = markers.find((m) => m.id === markerId);
      if (!marker) return;

      const currentTimeObservation = marker.timeObservation;
      const newTimeObservation = {
        start: field === "start" ? newTimeSeconds : currentTimeObservation.start,
        end: field === "end" ? newTimeSeconds : currentTimeObservation.end,
      };

      if (newTimeObservation.start >= newTimeObservation.end) {
        console.warn("Invalid time range: start must be less than end", newTimeObservation);
        return;
      }

      markerAdapter.update(markerId, { timeObservation: newTimeObservation }, "sidebar");
      refreshMarkers();
    } catch (error) {
      console.error("Error updating marker time:", error);
    }
  };

  const addMarker = () => {
    if (!markerAdapter?.isReady()) return;

    try {
      const time = getPlayerCurrentTime();
      const color = randomHexColor();
      const userMarkerCount = markers.filter((m) => m.type === "user").length;
      const defaultName = `Marker ${userMarkerCount + 1}`;

      const created = markerAdapter.add(
        {
          timeObservation: { start: time, end: time + 5 },
          label: defaultName,
          color,
          type: "user",
        },
        "sidebar"
      );

      if (created) {
        setMarkerNames((prev) => ({ ...prev, [created.id]: defaultName }));
        refreshMarkers();
      }
    } catch (error) {
      console.error("Error adding marker:", error);
    }
  };

  // Cache the extracted frame rate so we don't re-parse metadata on every call
  const cachedFpsRef = useRef<number | null>(null);

  // Reset cached FPS when asset changes
  useEffect(() => {
    cachedFpsRef.current = null;
  }, [asset]);

  // Helper function to convert timecode to seconds using actual asset frame rate
  const timecodeToSeconds = (timecode: string): number => {
    const [hours, minutes, seconds, frames] = timecode.split(":").map(Number);

    if (cachedFpsRef.current === null) {
      let framesPerSecond = 25;
      try {
        const videoMetadata = asset?.Metadata?.EmbeddedMetadata?.video;
        if (videoMetadata && Array.isArray(videoMetadata) && videoMetadata[0]) {
          const frameRate = videoMetadata[0].FrameRate;
          if (frameRate && typeof frameRate === "string") {
            framesPerSecond = parseFloat(frameRate);
          } else if (frameRate && typeof frameRate === "number") {
            framesPerSecond = frameRate;
          }
        }
        if (framesPerSecond === 25) {
          const generalMetadata = asset?.Metadata?.EmbeddedMetadata?.general;
          if (generalMetadata?.FrameRate) {
            const frameRate = generalMetadata.FrameRate;
            if (typeof frameRate === "string") {
              framesPerSecond = parseFloat(frameRate);
            } else if (typeof frameRate === "number") {
              framesPerSecond = frameRate;
            }
          }
        }
      } catch {
        /* use default */
      }
      cachedFpsRef.current = framesPerSecond;
    }

    return hours * 3600 + minutes * 60 + seconds + frames / cachedFpsRef.current;
  };

  // Helper function to convert score threshold to human-friendly confidence label
  const getConfidenceLabel = (threshold: number): string => {
    if (threshold >= 0.9) return "Very High";
    if (threshold >= 0.7) return "High";
    if (threshold >= 0.5) return "Medium";
    if (threshold >= 0.3) return "Low";
    return "Very Low";
  };

  const userMarkerCount = markers?.filter((m) => m.type === "user").length || 0;
  const aiMarkerCount =
    markers?.filter((m) => m.type === "semantic" && (m.score || 0) >= scoreThreshold).length || 0;

  const userMarkerCount = markers?.filter((m) => m.type === "user").length || 0;
  const aiMarkerCount =
    markers?.filter((m) => m.type === "semantic" && (m.score || 0) >= scoreThreshold).length || 0;

  return (
    <Box sx={{ p: 1.5, pt: 1 }}>
      {/* Compact toolbar: visibility toggles + add button in one row */}
      <Box
        sx={{
          mb: 2,
          display: "flex",
          alignItems: "center",
          gap: 0.75,
        }}
      >
        {/* User toggle chip */}
        <Box
          onClick={() => setShowUserMarkers(!showUserMarkers)}
          sx={{
            display: "inline-flex",
            alignItems: "center",
            gap: 0.5,
            px: 1.375,
            py: 0.75,
            borderRadius: "7px",
            cursor: "pointer",
            fontSize: "0.85rem",
            fontWeight: 600,
            letterSpacing: "0.01em",
            userSelect: "none",
            transition: "background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease",
            bgcolor: (theme) =>
              showUserMarkers
                ? alpha(theme.palette.primary.main, 0.1)
                : alpha(theme.palette.action.hover, theme.palette.mode === "dark" ? 0.12 : 0.6),
            color: (theme) =>
              showUserMarkers ? theme.palette.primary.main : theme.palette.text.secondary,
            border: "1px solid",
            borderColor: (theme) =>
              showUserMarkers
                ? alpha(theme.palette.primary.main, 0.25)
                : alpha(theme.palette.divider, 0.12),
            "&:hover": {
              bgcolor: (theme) =>
                showUserMarkers
                  ? alpha(theme.palette.primary.main, 0.15)
                  : alpha(theme.palette.action.hover, theme.palette.mode === "dark" ? 0.2 : 0.8),
            },
          }}
        >
          <PersonIcon sx={{ fontSize: 16 }} />
          <span>User</span>
          <Box
            component="span"
            sx={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              minWidth: 18,
              height: 18,
              borderRadius: "4px",
              fontSize: "0.675rem",
              fontWeight: 700,
              bgcolor: (theme) =>
                showUserMarkers
                  ? alpha(theme.palette.primary.main, 0.15)
                  : alpha(theme.palette.text.secondary, 0.1),
              lineHeight: 1,
              px: 0.5,
            }}
          >
            {userMarkerCount}
          </Box>
        </Box>

        {/* AI toggle chip */}
        <Box
          onClick={() => setShowSemanticMarkers(!showSemanticMarkers)}
          sx={{
            display: "inline-flex",
            alignItems: "center",
            gap: 0.5,
            px: 1.375,
            py: 0.75,
            borderRadius: "7px",
            cursor: "pointer",
            fontSize: "0.85rem",
            fontWeight: 600,
            letterSpacing: "0.01em",
            userSelect: "none",
            transition: "background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease",
            bgcolor: (theme) =>
              showSemanticMarkers
                ? alpha(theme.palette.info.main, 0.1)
                : alpha(theme.palette.action.hover, theme.palette.mode === "dark" ? 0.12 : 0.6),
            color: (theme) =>
              showSemanticMarkers ? theme.palette.info.main : theme.palette.text.secondary,
            border: "1px solid",
            borderColor: (theme) =>
              showSemanticMarkers
                ? alpha(theme.palette.info.main, 0.25)
                : alpha(theme.palette.divider, 0.12),
            "&:hover": {
              bgcolor: (theme) =>
                showSemanticMarkers
                  ? alpha(theme.palette.info.main, 0.15)
                  : alpha(theme.palette.action.hover, theme.palette.mode === "dark" ? 0.2 : 0.8),
            },
          }}
        >
          <SmartToyIcon sx={{ fontSize: 16 }} />
          <span>AI</span>
          <Box
            component="span"
            sx={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              minWidth: 18,
              height: 18,
              borderRadius: "4px",
              fontSize: "0.675rem",
              fontWeight: 700,
              bgcolor: (theme) =>
                showSemanticMarkers
                  ? alpha(theme.palette.info.main, 0.15)
                  : alpha(theme.palette.text.secondary, 0.1),
              lineHeight: 1,
              px: 0.5,
            }}
          >
            {aiMarkerCount}
          </Box>
        </Box>

        {/* Spacer */}
        <Box sx={{ flex: 1 }} />

        {/* Add marker button — compact icon+text */}
        <Box
          onClick={addMarker}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              addMarker();
            }
          }}
          sx={{
            display: "inline-flex",
            alignItems: "center",
            gap: 0.5,
            px: 1.625,
            py: 0.75,
            borderRadius: "7px",
            cursor: "pointer",
            fontSize: "0.85rem",
            fontWeight: 600,
            userSelect: "none",
            transition: "background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease",
            bgcolor: (theme) => theme.palette.primary.main,
            color: (theme) => theme.palette.primary.contrastText,
            "&:hover": {
              bgcolor: (theme) => theme.palette.primary.dark,
              boxShadow: (theme) => `0 2px 8px ${alpha(theme.palette.primary.main, 0.3)}`,
            },
            "&:active": {
              transform: "scale(0.97)",
            },
          }}
        >
          <BookmarkIcon sx={{ fontSize: 16 }} />
          <span>{t("common.addMarker")}</span>
        </Box>
      </Box>

      {/* User Markers Section */}
      {showUserMarkers && (
        <Box sx={{ mb: 3 }}>
          <Typography
            variant="caption"
            sx={{
              mb: 1.5,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: 0.75,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              fontSize: "0.65rem",
              color: "text.secondary",
            }}
          >
            <PersonIcon sx={{ fontSize: 14 }} />
            User Markers ({markers?.filter((m) => m.type === "user").length || 0})
          </Typography>
          {markers?.filter((m) => m.type === "user").length === 0 ? (
            <Box
              sx={{
                p: 2.5,
                textAlign: "center",
                bgcolor: (theme) => alpha(theme.palette.background.default, 0.4),
                borderRadius: "10px",
                border: "1px dashed",
                borderColor: (theme) => alpha(theme.palette.divider, 0.3),
              }}
            >
              <BookmarkIcon
                sx={{ fontSize: 28, opacity: 0.2, mb: 0.5, display: "block", mx: "auto" }}
              />
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: "0.8rem" }}>
                No user markers yet. Click "Add User Marker" to create one.
              </Typography>
            </Box>
          ) : (
            markers
              .filter((m) => m.type === "user")
              .sort((a, b) => b.id.localeCompare(a.id)) // Sort by ID descending (newest first)
              .map((marker, index) => (
                <Box
                  key={marker.id}
                  onClick={() => {
                    if (seek) {
                      seek(marker.timeObservation.start);
                    }
                  }}
                  sx={{
                    mt: 1,
                    p: 1.25,
                    pr: 4,
                    position: "relative",
                    bgcolor: (theme) => alpha(marker.style.color, 0.05),
                    borderRadius: "10px",
                    border: `1px solid ${alpha(marker.style.color, 0.15)}`,
                    borderLeft: `3px solid ${marker.style.color}`,
                    cursor: "pointer",
                    transition:
                      "background-color 0.2s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
                    "&:hover": {
                      bgcolor: alpha(marker.style.color, 0.1),
                      border: `1px solid ${alpha(marker.style.color, 0.3)}`,
                      borderLeft: `3px solid ${marker.style.color}`,
                      transform: "translateX(2px)",
                      boxShadow: `0 2px 8px ${alpha(marker.style.color, 0.12)}`,
                    },
                    "& .marker-delete": { opacity: 0, pointerEvents: "none" },
                    "&:hover .marker-delete": {
                      opacity: 1,
                      pointerEvents: "auto",
                    },
                  }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 0.5,
                        flex: 1,
                        minWidth: 0,
                      }}
                    >
                      <UserAvatar size={16} fontSize="0.6rem" />
                      <Box
                        component="input"
                        type="text"
                        value={
                          marker.id in markerNames
                            ? markerNames[marker.id]
                            : marker.name || `User Marker ${index + 1}`
                        }
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                          const newName = e.target.value;
                          setMarkerNames((prev) => ({
                            ...prev,
                            [marker.id]: newName,
                          }));
                          markerAdapter?.update(marker.id, { label: newName }, "sidebar");
                        }}
                        onClick={(e: React.MouseEvent) => e.stopPropagation()}
                        onKeyDown={(e: React.KeyboardEvent) => {
                          e.stopPropagation();
                        }}
                        sx={{
                          fontWeight: 600,
                          fontStyle: "italic",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          flex: 1,
                          minWidth: 0,
                          lineHeight: 1.4,
                          outline: "none",
                          cursor: "text",
                          border: "none",
                          background: "transparent",
                          p: 0,
                          m: 0,
                          font: "inherit",
                          fontSize: "0.875rem",
                          color: "inherit",
                          width: "100%",
                          "&:focus": {
                            outline: `2px solid ${marker.style.color}`,
                            outlineOffset: "1px",
                            borderRadius: "2px",
                          },
                        }}
                      />
                    </Box>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                        flexShrink: 0,
                      }}
                    >
                      <EditableTimecode
                        value={marker.timeObservation.start}
                        markerId={marker.id}
                        field="start"
                        onUpdate={updateMarkerTime}
                      />
                      <Typography variant="caption" sx={{ color: "text.secondary" }}>
                        {" - "}
                      </Typography>
                      <EditableTimecode
                        value={marker.timeObservation.end}
                        markerId={marker.id}
                        field="end"
                        onUpdate={updateMarkerTime}
                      />
                    </Box>
                  </Box>
                  <Typography
                    variant="caption"
                    sx={{
                      color: "text.secondary",
                      fontStyle: "italic",
                      display: "block",
                      mt: 0.5,
                      fontSize: "0.7rem",
                    }}
                  >
                    Created by {userName}
                  </Typography>
                  <IconButton
                    className="marker-delete"
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteMarker(marker.id);
                    }}
                    sx={{
                      position: "absolute",
                      top: 8,
                      right: 8,
                      p: 0.25,
                      width: 22,
                      height: 22,
                      color: "text.secondary",
                      borderRadius: "6px",
                      transition:
                        "background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease",
                      "&:hover": {
                        color: "error.main",
                        bgcolor: (theme) => alpha(theme.palette.error.main, 0.1),
                      },
                    }}
                    aria-label={t("common.breadcrumb.ariaLabels.deleteMarker")}
                  >
                    <CloseIcon sx={{ fontSize: 14 }} />
                  </IconButton>
                </Box>
              ))
          )}
        </Box>
      )}

      {/* Semantic Markers Section */}
      {showSemanticMarkers && (
        <Box sx={{ mb: 2 }}>
          <Typography
            variant="caption"
            sx={{
              mb: 1.5,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: 0.75,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              fontSize: "0.65rem",
              color: "text.secondary",
            }}
          >
            <SmartToyIcon sx={{ fontSize: 14 }} />
            Semantic Markers (
            {markers?.filter((m) => m.type === "semantic" && (m.score || 0) >= scoreThreshold)
              .length || 0}
            )
          </Typography>

          {/* Confidence Level Slider - refined card */}
          <Box
            sx={{
              mb: 2,
              p: 1.5,
              bgcolor: (theme) => alpha(theme.palette.background.default, 0.5),
              borderRadius: "10px",
              border: "1px solid",
              borderColor: (theme) => alpha(theme.palette.divider, 0.08),
            }}
          >
            <Box
              sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                mb: 0.5,
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  fontWeight: 700,
                  fontSize: "0.65rem",
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  color: "text.secondary",
                }}
              >
                Confidence Level
              </Typography>
              <Typography
                variant="caption"
                sx={{ fontWeight: 600, fontSize: "0.75rem", color: "primary.main" }}
              >
                {getConfidenceLabel(scoreThreshold)} ({scoreThreshold.toFixed(3)})
              </Typography>
            </Box>
            <Box sx={{ position: "relative", px: 0.5 }}>
              <Slider
                value={scoreThreshold}
                onChange={(_, newValue) => {
                  const newThreshold = newValue as number;
                  setScoreThreshold(newThreshold);
                  saveConfidenceLevelToStorage(newThreshold);
                }}
                min={0}
                max={1}
                step={0.01}
                valueLabelDisplay="auto"
                valueLabelFormat={(value) => `${Math.round(value * 100)}%`}
                sx={{
                  "& .MuiSlider-thumb": {
                    width: 16,
                    height: 16,
                    boxShadow: (theme) => `0 1px 4px ${alpha(theme.palette.common.black, 0.2)}`,
                    "&:hover, &.Mui-focusVisible": {
                      boxShadow: (theme) => `0 0 0 6px ${alpha(theme.palette.primary.main, 0.15)}`,
                    },
                  },
                  "& .MuiSlider-track": {
                    height: 4,
                    borderRadius: 2,
                  },
                  "& .MuiSlider-rail": {
                    height: 4,
                    borderRadius: 2,
                    opacity: 0.2,
                  },
                  "& .MuiSlider-valueLabel": {
                    fontSize: "0.7rem",
                    fontWeight: 600,
                    borderRadius: "6px",
                    padding: "2px 6px",
                  },
                }}
              />
              {/* Confidence level labels */}
              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  mt: 0.5,
                  fontSize: "0.7rem",
                  color: "text.secondary",
                }}
              >
                <Typography variant="caption" color="text.secondary">
                  Low Confidence
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  High Confidence
                </Typography>
              </Box>
            </Box>
          </Box>
          {isLoadingSemanticMarkers ? (
            <Box
              sx={{
                p: 2.5,
                textAlign: "center",
                bgcolor: (theme) => alpha(theme.palette.background.default, 0.4),
                borderRadius: "10px",
                border: "1px dashed",
                borderColor: (theme) => alpha(theme.palette.divider, 0.3),
              }}
            >
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 1,
                }}
              >
                <CircularProgress size={14} thickness={5} />
                <Typography variant="body2" color="text.secondary" sx={{ fontSize: "0.8rem" }}>
                  Creating semantic markers...
                </Typography>
              </Box>
            </Box>
          ) : markers?.filter((m) => m.type === "semantic" && (m.score || 0) >= scoreThreshold)
              .length === 0 ? (
            <Box
              sx={{
                p: 2.5,
                textAlign: "center",
                bgcolor: (theme) => alpha(theme.palette.background.default, 0.4),
                borderRadius: "10px",
                border: "1px dashed",
                borderColor: (theme) => alpha(theme.palette.divider, 0.3),
              }}
            >
              <SmartToyIcon
                sx={{ fontSize: 28, opacity: 0.2, mb: 0.5, display: "block", mx: "auto" }}
              />
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: "0.8rem" }}>
                No semantic markers match the current confidence threshold.
              </Typography>
            </Box>
          ) : (
            markers
              .filter((m) => m.type === "semantic" && (m.score || 0) >= scoreThreshold)
              .sort((a, b) => (b.score || 0) - (a.score || 0)) // Sort by score descending
              .map((marker, index) => (
                <Box
                  key={marker.id}
                  onClick={() => {
                    if (seek) {
                      seek(marker.timeObservation.start);
                    }
                  }}
                  sx={{
                    mt: 1,
                    p: 1.25,
                    pr: 4, // Add padding-right to make space for reset button
                    position: "relative",
                    bgcolor: alpha(marker.style.color, 0.05),
                    borderRadius: "10px",
                    border: `1px solid ${alpha(marker.style.color, 0.15)}`,
                    borderLeft: `3px solid ${marker.style.color}`,
                    cursor: "pointer",
                    transition:
                      "background-color 0.2s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
                    "&:hover": {
                      bgcolor: alpha(marker.style.color, 0.1),
                      border: `1px solid ${alpha(marker.style.color, 0.3)}`,
                      borderLeft: `3px solid ${marker.style.color}`,
                      transform: "translateX(2px)",
                      boxShadow: `0 2px 8px ${alpha(marker.style.color, 0.12)}`,
                    },
                    "& .marker-reset": { opacity: 0, pointerEvents: "none" },
                    "&:hover .marker-reset": {
                      opacity: 1,
                      pointerEvents: "auto",
                    },
                  }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 0.5,
                        flex: 1,
                        minWidth: 0,
                      }}
                    >
                      <SmartToyIcon
                        sx={{
                          fontSize: "1rem",
                          color: "primary.main",
                          flexShrink: 0,
                        }}
                      />
                      <Typography
                        variant="body2"
                        component="span"
                        sx={{
                          fontWeight: 600,
                          fontStyle: "italic",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          flex: 1,
                          minWidth: 0,
                          lineHeight: 1.4,
                        }}
                      >
                        {(() => {
                          // Always use new format: "Clip N (Match for: SEARCH TERM)"
                          const clipNumber = index + 1;
                          const searchTerm = marker.name || "Unknown";
                          // Remove score from search term if present
                          const cleanSearchTerm = searchTerm.replace(/\s+\d+\.\d+$/, "");
                          return `Clip ${clipNumber} (Match for: ${cleanSearchTerm})`;
                        })()}
                      </Typography>
                    </Box>
                    <Box sx={{ flexShrink: 0, position: "relative" }}>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                        <EditableTimecode
                          value={marker.timeObservation.start}
                          markerId={marker.id}
                          field="start"
                          onUpdate={updateMarkerTime}
                        />
                        <Typography variant="caption" sx={{ color: "text.secondary" }}>
                          {" - "}
                        </Typography>
                        <EditableTimecode
                          value={marker.timeObservation.end}
                          markerId={marker.id}
                          field="end"
                          onUpdate={updateMarkerTime}
                        />
                      </Box>
                    </Box>
                  </Box>
                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      mt: 0.5,
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{
                        color: "primary.main",
                        fontStyle: "italic",
                        fontSize: "0.7rem",
                      }}
                    >
                      Created by {getSearchProviderName()}
                    </Typography>
                    {marker.score !== undefined && (
                      <Box
                        component="span"
                        sx={{
                          display: "inline-flex",
                          alignItems: "center",
                          px: 0.75,
                          py: 0.25,
                          borderRadius: "6px",
                          bgcolor: (theme) => alpha(theme.palette.primary.main, 0.08),
                          border: "1px solid",
                          borderColor: (theme) => alpha(theme.palette.primary.main, 0.15),
                        }}
                      >
                        <Typography
                          variant="caption"
                          sx={{
                            color: "primary.main",
                            fontWeight: 700,
                            fontSize: "0.625rem",
                            fontVariantNumeric: "tabular-nums",
                          }}
                        >
                          {Number(marker.score).toFixed(3)}
                        </Typography>
                      </Box>
                    )}
                  </Box>
                  {assetId && asset?.clips && (
                    <Tooltip title={t("common.resetMarker")}>
                      <IconButton
                        className="marker-reset"
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          resetSemanticMarker(marker.id);
                        }}
                        sx={{
                          position: "absolute",
                          top: 8,
                          right: 8,
                          p: 0.25,
                          width: 22,
                          height: 22,
                          color: "text.secondary",
                          borderRadius: "6px",
                          transition:
                            "background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease",
                          "&:hover": {
                            color: "primary.main",
                            bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1),
                          },
                        }}
                        aria-label={t("common.breadcrumb.ariaLabels.resetMarker")}
                      >
                        <RestoreIcon sx={{ fontSize: 14 }} />
                      </IconButton>
                    </Tooltip>
                  )}
                </Box>
              ))
          )}
        </Box>
      )}
    </Box>
  );
};

// Collaboration content component (unused but kept for future use)
// eslint-disable-next-line @typescript-eslint/no-unused-vars, no-unused-vars
const _AssetCollaboration: React.FC<AssetCollaborationProps> = ({
  comments = [],
  onAddComment,
}) => {
  const { t } = useTranslation();
  const [newComment, setNewComment] = useState("");
  const theme = useTheme();

  const handleSubmitComment = () => {
    if (newComment.trim() && onAddComment) {
      onAddComment(newComment);
      setNewComment("");
    }
  };

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <Box sx={{ flex: 1, overflowY: "auto", p: 2 }}>
        {comments.length === 0 ? (
          <Paper
            variant="outlined"
            sx={{
              p: 3,
              textAlign: "center",
              bgcolor: alpha(theme.palette.background.paper, 0.4),
            }}
          >
            <GroupsIcon color="disabled" sx={{ fontSize: 40, mb: 1, opacity: 0.7 }} />
            <Typography color="text.secondary" sx={{ mb: 1 }}>
              No comments yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Start the conversation by adding a comment below.
            </Typography>
          </Paper>
        ) : (
          <List disablePadding>
            {comments.map((comment, index) => (
              <ListItem
                key={index}
                alignItems="flex-start"
                sx={{
                  px: 1,
                  py: 1.5,
                  borderRadius: 1,
                  mb: 1,
                  bgcolor:
                    index % 2 === 0 ? "transparent" : alpha(theme.palette.background.paper, 0.4),
                }}
              >
                <ListItemIcon sx={{ minWidth: 40 }}>
                  <Avatar src={comment.avatar} alt={comment.user} sx={{ width: 32, height: 32 }}>
                    {comment.user.charAt(0)}
                  </Avatar>
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Box
                      sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <Typography variant="subtitle2" component="span">
                        {comment.user}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {comment.timestamp}
                      </Typography>
                    </Box>
                  }
                  secondary={
                    <Typography
                      variant="body2"
                      color="text.primary"
                      sx={{ mt: 0.5, whiteSpace: "pre-wrap" }}
                    >
                      {comment.content}
                    </Typography>
                  }
                />
              </ListItem>
            ))}
          </List>
        )}
      </Box>

      <Divider />

      <Box sx={{ p: 2, bgcolor: alpha(theme.palette.background.paper, 0.3) }}>
        <TextField
          variant="outlined"
          size="small"
          fullWidth
          multiline
          rows={2}
          placeholder={t("common.placeholders.addComment")}
          value={newComment}
          onChange={(e) => setNewComment(e.target.value)}
          sx={{
            mb: 1,
            "& .MuiOutlinedInput-root": {
              backgroundColor: theme.palette.background.paper,
            },
          }}
        />
        <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
          <Tooltip title={t("common.postComment")}>
            <span>
              <Button
                variant="contained"
                size="small"
                endIcon={<SendIcon />}
                disabled={!newComment.trim()}
                onClick={handleSubmitComment}
              >
                Post
              </Button>
            </span>
          </Tooltip>
        </Box>
      </Box>
    </Box>
  );
};

// Pipelines content component (unused but kept for future use)
// eslint-disable-next-line @typescript-eslint/no-unused-vars, no-unused-vars
const _AssetPipelines: React.FC<AssetPipelinesProps> = () => {
  const theme = useTheme();
  const { t } = useTranslation();

  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Run processing pipelines on this asset to transform or analyze it.
      </Typography>

      <Paper
        variant="outlined"
        sx={{
          p: 2,
          mb: 2,
          borderColor: alpha(theme.palette.info.main, 0.2),
          transition: "border-color 0.2s ease, background-color 0.2s ease",
          "&:hover": {
            borderColor: theme.palette.info.main,
            boxShadow: `0 4px 8px ${alpha(theme.palette.info.main, 0.15)}`,
          },
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
          <AccountTreeIcon color="info" fontSize="small" sx={{ mr: 1 }} />
          <Typography variant="subtitle2">{t("assetSidebar.thumbnailGeneration")}</Typography>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Creates multiple thumbnail images at different resolutions.
        </Typography>
        <Tooltip title={t("common.runPipeline")}>
          <Button variant="outlined" size="small" color="info">
            Run Pipeline
          </Button>
        </Tooltip>
      </Paper>

      <Paper
        variant="outlined"
        sx={{
          p: 2,
          mb: 2,
          borderColor: alpha(theme.palette.warning.main, 0.2),
          transition: "border-color 0.2s ease, background-color 0.2s ease",
          "&:hover": {
            borderColor: theme.palette.warning.main,
            boxShadow: `0 4px 8px ${alpha(theme.palette.warning.main, 0.15)}`,
          },
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
          <AccountTreeIcon color="warning" fontSize="small" sx={{ mr: 1 }} />
          <Typography variant="subtitle2">{t("assetSidebar.aiAnalysis")}</Typography>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Extracts metadata, tags, and insights using machine learning.
        </Typography>
        <Tooltip title={t("common.runPipeline")}>
          <Button variant="outlined" size="small" color="warning">
            Run Pipeline
          </Button>
        </Tooltip>
      </Paper>

      <Tooltip title={t("common.browsePipelines")}>
        <Button variant="text" fullWidth sx={{ mt: 2 }}>
          {t("pipelines.viewAll", "View All Pipelines")}
        </Button>
      </Tooltip>
    </Box>
  );
};

// Activity content component (unused but kept for future use)
// eslint-disable-next-line @typescript-eslint/no-unused-vars, no-unused-vars
const _AssetActivity: React.FC<AssetActivityProps> = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const activities = [
    {
      user: "System",
      action: "Created asset",
      timestamp: "2023-11-15 09:30:22",
      icon: <PersonIcon color="primary" />,
    },
    {
      user: "John Doe",
      action: "Added to collection",
      timestamp: "2023-11-15 10:15:43",
      icon: <PersonIcon color="primary" />,
    },
    {
      user: "AI Pipeline",
      action: "Generated metadata",
      timestamp: "2023-11-15 11:22:17",
      icon: <TimelineIcon color="secondary" />,
    },
    {
      user: "Jane Smith",
      action: "Added comment",
      timestamp: "2023-11-15 14:05:36",
      icon: <PersonIcon color="primary" />,
    },
  ];

  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Recent activity history for this asset.
      </Typography>

      <List
        disablePadding
        sx={{
          bgcolor: alpha(theme.palette.background.paper, 0.4),
          borderRadius: 1,
          p: 1,
        }}
      >
        {activities.map((activity, index) => (
          <React.Fragment key={index}>
            <ListItem
              alignItems="flex-start"
              sx={{
                px: 1,
                py: 1.5,
                borderRadius: 1,
                "&:hover": {
                  bgcolor: alpha(theme.palette.background.paper, 0.6),
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 36 }}>{activity.icon}</ListItemIcon>
              <ListItemText
                primary={activity.action}
                secondary={
                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "space-between",
                      mt: 0.5,
                    }}
                  >
                    <Typography variant="caption" component="span">
                      {activity.user}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" component="span">
                      {activity.timestamp}
                    </Typography>
                  </Box>
                }
              />
            </ListItem>
            {index < activities.length - 1 && <Divider component="li" sx={{ my: 0.5 }} />}
          </React.Fragment>
        ))}
      </List>

      <Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
        <Tooltip title={t("common.loadMoreActivities")}>
          <Button size="small" color="primary">
            Load More
          </Button>
        </Tooltip>
      </Box>
    </Box>
  );
};
export const AssetSidebar: React.FC<AssetSidebarProps> = (props) => {
  const { t } = useTranslation();
  const { markerAdapter, isMarkerReady, seek, versions = [], assetId, asset, searchTerm } = props;
  const [currentTab, setCurrentTab] = useState(0);
  const theme = useTheme();
  const [markers, setMarkers] = useState<MarkerInfo[]>([]);
  const [clipsMarkersCreated, setClipsMarkersCreated] = useState(false);
  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
  };

  return (
    <RightSidebar alwaysVisible>
      <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
        {/* Tabs navigation - refined segmented control style */}
        <Box
          sx={{
            px: 1.5,
            pt: 1,
            pb: 0,
          }}
        >
          <Box
            sx={{
              display: "flex",
              gap: 0,
              borderBottom: "1px solid",
              borderColor: (theme) => alpha(theme.palette.divider, 0.1),
            }}
          >
            {[
              {
                icon: <BookmarkIcon sx={{ fontSize: 16 }} />,
                label: t("assetSidebar.tabs.markers"),
                index: 0,
              },
              {
                icon: <HistoryIcon sx={{ fontSize: 16 }} />,
                label: t("common.versions"),
                index: 1,
                badge: versions.length,
              },
            ].map((tab) => (
              <Box
                key={tab.index}
                onClick={() => handleTabChange(null as any, tab.index)}
                role="tab"
                id={`sidebar-tab-${tab.index}`}
                aria-controls={`sidebar-tabpanel-${tab.index}`}
                aria-selected={currentTab === tab.index}
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    handleTabChange(null as any, tab.index);
                  }
                }}
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 0.625,
                  py: 1.125,
                  px: 1.75,
                  cursor: "pointer",
                  fontSize: "0.875rem",
                  fontWeight: currentTab === tab.index ? 600 : 500,
                  color: currentTab === tab.index ? "primary.main" : "text.secondary",
                  borderBottom: "2px solid",
                  borderColor: currentTab === tab.index ? "primary.main" : "transparent",
                  mb: "-1px",
                  transition:
                    "background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease",
                  userSelect: "none",
                  "&:hover": {
                    color: currentTab === tab.index ? "primary.main" : "text.primary",
                  },
                }}
              >
                {tab.icon}
                <span>{tab.label}</span>
                {tab.badge != null && tab.badge > 0 && (
                  <Box
                    component="span"
                    sx={{
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      minWidth: 18,
                      height: 18,
                      borderRadius: "4px",
                      fontSize: "0.675rem",
                      fontWeight: 700,
                      px: 0.5,
                      bgcolor:
                        currentTab === tab.index
                          ? (theme) => alpha(theme.palette.primary.main, 0.12)
                          : (theme) => alpha(theme.palette.text.secondary, 0.08),
                      color: currentTab === tab.index ? "primary.main" : "text.secondary",
                      lineHeight: 1,
                    }}
                  >
                    {tab.badge}
                  </Box>
                )}
              </Box>
            ))}
          </Box>
        </Box>

        {/* Tab content */}
        <Box sx={{ flex: 1, overflow: "hidden" }}>
          <Box
            role="tabpanel"
            hidden={currentTab !== 0}
            id="sidebar-tabpanel-0"
            aria-labelledby="sidebar-tab-0"
            sx={{ height: "100%", overflow: "auto" }}
          >
            {currentTab === 0 && (
              <AssetMarkers
                markerAdapter={markerAdapter}
                isMarkerReady={isMarkerReady}
                seek={seek}
                markers={markers}
                setMarkers={setMarkers}
                asset={asset}
                assetId={assetId}
                assetType={asset?.DigitalSourceAsset?.Type || "video"}
                searchTerm={searchTerm}
                clipsMarkersCreated={clipsMarkersCreated}
                setClipsMarkersCreated={setClipsMarkersCreated}
              />
            )}
          </Box>

          <Box
            role="tabpanel"
            hidden={currentTab !== 1}
            id="sidebar-tabpanel-1"
            aria-labelledby="sidebar-tab-1"
            sx={{ height: "100%", overflow: "auto" }}
          >
            {currentTab === 1 && (
              <AssetVersions
                versions={versions.map((v) => {
                  // Helper function to format file size in a friendly way
                  const formatFileSize = (bytes: number): string => {
                    if (bytes === 0) return "0 B";

                    const k = 1024;
                    const sizes = ["B", "KB", "MB", "GB", "TB"];
                    const i = Math.floor(Math.log(bytes) / Math.log(k));

                    const size = bytes / Math.pow(k, i);

                    // Format with appropriate decimal places
                    if (i === 0) return `${size} B`; // Bytes - no decimals
                    if (i === 1) return `${Math.round(size)} KB`; // KB - no decimals
                    if (i === 2) return `${size.toFixed(1)} MB`; // MB - 1 decimal
                    return `${size.toFixed(2)} ${sizes[i]}`; // GB+ - 2 decimals
                  };

                  // Use the existing fileSize property from the version object
                  let size = null;

                  if (v.fileSize) {
                    // If fileSize is already formatted (contains 'KB', 'MB', etc.), check if it needs reformatting
                    if (
                      typeof v.fileSize === "string" &&
                      (v.fileSize.includes("KB") ||
                        v.fileSize.includes("MB") ||
                        v.fileSize.includes("GB"))
                    ) {
                      // Extract the numeric value and reformat it
                      const numericValue = parseFloat(v.fileSize);
                      if (!isNaN(numericValue)) {
                        // Convert back to bytes based on unit, then reformat
                        let bytes = numericValue;
                        if (v.fileSize.includes("KB")) bytes *= 1024;
                        else if (v.fileSize.includes("MB")) bytes *= 1024 * 1024;
                        else if (v.fileSize.includes("GB")) bytes *= 1024 * 1024 * 1024;
                        size = formatFileSize(bytes);
                      } else {
                        size = v.fileSize; // Keep original if parsing fails
                      }
                    } else {
                      // If fileSize is raw bytes, format it
                      const bytes = parseFloat(v.fileSize);
                      size = formatFileSize(bytes);
                    }
                  }

                  return {
                    ...v,
                    assetId: assetId,
                    size: size,
                  };
                })}
              />
            )}
          </Box>
        </Box>
      </Box>
    </RightSidebar>
  );
};

export default AssetSidebar;
