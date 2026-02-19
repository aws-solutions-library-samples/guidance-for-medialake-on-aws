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
import { RefObject } from "react";
import { VideoViewerRef } from "../common/VideoViewer";
import { randomHexColor, getMarkerColorByConfidence } from "../common/utils";
import { PERIOD_MARKER_STYLE } from "../common/OmakaseTimeLineConstants";
import { PeriodMarker } from "@byomakase/omakase-player";

interface MarkerInfo {
  id: string;
  name?: string;
  timeObservation: {
    start: number;
    end: number;
  };
  style: {
    color: string;
  };
  score?: number; // Optional score property for markers created from clips
  type: "user" | "semantic"; // Track marker origin
  createdAt?: number; // Track creation time for sorting
  model_version?: string; // Model version for model-aware confidence thresholds (e.g., "3.0", "2.7")
}

// localStorage utilities for marker persistence
const getMarkerStorageKey = (assetId: string): string => `medialake_markers_${assetId}`;

const loadUserMarkersFromStorage = (assetId: string): MarkerInfo[] => {
  try {
    const key = getMarkerStorageKey(assetId);
    const stored = localStorage.getItem(key);
    return stored ? JSON.parse(stored) : [];
  } catch (error) {
    console.warn("Failed to load markers from localStorage:", error);
    return [];
  }
};

const saveUserMarkersToStorage = (assetId: string, userMarkers: MarkerInfo[]): void => {
  try {
    const key = getMarkerStorageKey(assetId);
    const markersToSave = userMarkers.filter((m) => m.type === "user");
    localStorage.setItem(key, JSON.stringify(markersToSave));
  } catch (error) {
    console.error("Failed to save markers to localStorage:", error);
  }
};

// Storage utilities for semantic marker modifications
const getSemanticModificationsStorageKey = (assetId: string): string =>
  `medialake_semantic_modifications_${assetId}`;

const loadSemanticModificationsFromStorage = (
  assetId: string
): Record<string, Partial<MarkerInfo>> => {
  try {
    const key = getSemanticModificationsStorageKey(assetId);
    const stored = localStorage.getItem(key);
    const result = stored ? JSON.parse(stored) : {};
    return result;
  } catch (error) {
    console.warn("Failed to load semantic modifications from localStorage:", error);
    return {};
  }
};

const saveSemanticModificationsToStorage = (
  assetId: string,
  modifications: Record<string, Partial<MarkerInfo>>
): void => {
  try {
    const key = getSemanticModificationsStorageKey(assetId);
    localStorage.setItem(key, JSON.stringify(modifications));
  } catch (error) {
    console.error("Failed to save semantic modifications to localStorage:", error);
  }
};

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

const clearMarkersFromStorage = (assetId: string): void => {
  try {
    const key = getMarkerStorageKey(assetId);
    localStorage.removeItem(key);

    // Also clear semantic modifications
    const semanticKey = getSemanticModificationsStorageKey(assetId);
    localStorage.removeItem(semanticKey);
  } catch (error) {
    console.error("Failed to clear markers from localStorage:", error);
  }
};

// Editable Timecode Component
const EditableTimecode: React.FC<{
  value: number;
  markerId: string;
  field: "start" | "end";
  onUpdate: (markerId: string, field: "start" | "end", newTimeSeconds: number) => void;
  videoViewerRef?: RefObject<VideoViewerRef>;
}> = ({ value, markerId, field, onUpdate, videoViewerRef }) => {
  const { t } = useTranslation();
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState("");

  const handleStartEdit = () => {
    const formattedTime =
      videoViewerRef?.current?.formatToTimecode(value) || formatSecondsToTimecode(value);
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
      {videoViewerRef?.current?.formatToTimecode(value) || formatSecondsToTimecode(value)}
    </Typography>
  );
};

interface AssetSidebarProps {
  versions?: any[];
  comments?: any[];
  onAddComment?: (comment: string) => void;
  videoViewerRef?: RefObject<VideoViewerRef>;
  assetId?: string;
  asset?: any;
  assetType?: string;
  searchTerm?: string; // Add searchTerm prop
}

interface AssetVersionProps {
  versions: any[];
}

interface AssetMarkersProps {
  onMarkerAdd?: () => void;
  videoViewerRef?: RefObject<VideoViewerRef>; // Add this
  markers?: MarkerInfo[];
  setMarkers?: React.Dispatch<React.SetStateAction<MarkerInfo[]>>;
  asset: any;
  assetId?: string; // Add assetId prop for localStorage
  assetType: string;
  searchTerm?: string; // Add searchTerm prop
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
                transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
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
  videoViewerRef,
  asset,
  assetId,

  searchTerm,
  clipsMarkersCreated,
  setClipsMarkersCreated,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  // Store all marker references in a Map
  const markerRefsMap = useRef(new Map<string, PeriodMarker>());
  // State to track editable marker names
  const [markerNames, setMarkerNames] = useState<Record<string, string>>({});
  // State for score threshold slider (start with a low value to show all clips by default)
  const [scoreThreshold, setScoreThreshold] = useState<number>(0);
  // State to track if score threshold has been initialized
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

  // Track semantic modifications for reset button visibility
  const [semanticModifications, setSemanticModifications] = useState<
    Record<string, Partial<MarkerInfo>>
  >({});

  // Flag to prevent subscription events during reset operations
  const isResettingMarker = useRef<Set<string>>(new Set());
  // Track retry timeouts for marker creation so they can be cleaned up on unmount
  const markerRetryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
    if (!asset?.clips || !Array.isArray(asset.clips) || scoreThresholdInitialized) {
      return;
    }

    // First, try to load from localStorage
    const storedThreshold = loadConfidenceLevelFromStorage();
    if (storedThreshold !== null) {
      setScoreThreshold(storedThreshold);
      setScoreThresholdInitialized(true);
      return;
    }

    // If no stored value, calculate default based on clips
    // Support both Marengo 2.7 ("visual-text") and Marengo 3.0 ("visual") embedding types
    const visualTextClips = asset.clips.filter(
      (clip) =>
        (clip.embedding_option === "visual-text" || clip.embedding_option === "visual") &&
        clip.score !== null &&
        clip.score !== undefined
    );

    if (visualTextClips.length > 0) {
      // Set threshold slightly below the minimum score to show all clips by default
      const minScore = Math.min(...visualTextClips.map((clip) => clip.score || 0));
      const defaultThreshold = Math.max(0, minScore - 0.1); // 0.1 below minimum score
      setScoreThreshold(defaultThreshold);
      // Save the initial threshold to localStorage
      saveConfidenceLevelToStorage(defaultThreshold);
      setScoreThresholdInitialized(true);
    }
  }, [asset?.clips, scoreThresholdInitialized]);

  // Load user markers from localStorage on component mount (state only)
  useEffect(() => {
    if (!assetId) {
      return;
    }

    const storedMarkers = loadUserMarkersFromStorage(assetId);

    // Load semantic modifications
    const storedModifications = loadSemanticModificationsFromStorage(assetId);
    setSemanticModifications(storedModifications);

    if (storedMarkers.length > 0) {
      // Add stored markers to state
      setMarkers((prevMarkers) => {
        // Filter out any existing user markers to avoid duplicates
        const nonUserMarkers = prevMarkers.filter((m) => m.type !== "user");
        return [...nonUserMarkers, ...storedMarkers];
      });

      // Add marker names
      const markerNames = {};
      storedMarkers.forEach((marker) => {
        markerNames[marker.id] = marker.name || `Marker ${marker.id}`;
      });
      setMarkerNames((prev) => ({ ...prev, ...markerNames }));
    }
  }, [assetId]);

  // Create timeline markers for user markers when videoViewerRef becomes available
  useEffect(() => {
    if (!videoViewerRef?.current || !assetId) return;

    const userMarkers = markers.filter((m) => m.type === "user");
    if (userMarkers.length === 0) return;

    const lane = videoViewerRef.current.getMarkerLane();
    if (!lane) {
      console.warn("Marker lane not available for user markers");
      return;
    }

    // Get existing markers in the lane to avoid duplicate additions
    const existingLaneMarkers = lane.getMarkers();
    const existingLaneMarkerIds = new Set(existingLaneMarkers.map((m) => m.id));

    userMarkers.forEach((marker) => {
      // Skip if marker already exists in our ref map
      if (markerRefsMap.current.has(marker.id)) {
        return;
      }

      // Skip if marker already exists in the lane (e.g. player persisted across navigation)
      if (existingLaneMarkerIds.has(marker.id)) {
        // Re-populate the ref map so other logic (subscriptions, delete, etc.) still works
        const existingMarker = existingLaneMarkers.find((m) => m.id === marker.id);
        if (existingMarker) {
          markerRefsMap.current.set(marker.id, existingMarker as PeriodMarker);
        }
        return;
      }

      const periodMarker = new PeriodMarker({
        timeObservation: marker.timeObservation,
        editable: true,
        id: marker.id,
        style: {
          ...PERIOD_MARKER_STYLE,
          color: marker.style.color,
        },
      });

      markerRefsMap.current.set(marker.id, periodMarker);
      lane.addMarker(periodMarker);
    });

    // Trigger visibility update after a short delay to ensure markers are added
    setTimeout(() => {
      // Call updateMarkerVisibility directly without dependency to avoid circular reference
      if (!videoViewerRef?.current) return;

      const lane = videoViewerRef.current.getMarkerLane();
      if (!lane) return;

      markers.forEach((marker) => {
        const markerRef = markerRefsMap.current.get(marker.id);
        if (markerRef) {
          const shouldShow =
            (marker.type === "user" && showUserMarkers) ||
            (marker.type === "semantic" &&
              showSemanticMarkers &&
              (marker.score || 0) >= scoreThreshold);

          if (shouldShow) {
            // Add marker to timeline if not already there
            const existingMarkers = lane.getMarkers();
            if (!existingMarkers.some((m) => m.id === marker.id)) {
              lane.addMarker(markerRef);
            }
          } else {
            // Remove marker from timeline
            lane.removeMarker(marker.id);
          }
        }
      });
    }, 100);
  }, [videoViewerRef, markers, assetId, showUserMarkers, showSemanticMarkers, scoreThreshold]);

  // Save user markers to localStorage whenever markers change
  useEffect(() => {
    if (!assetId) return;

    const userMarkers = markers.filter((m) => m.type === "user");
    if (userMarkers.length > 0) {
      saveUserMarkersToStorage(assetId, userMarkers);
    }
  }, [markers, assetId]);

  // Set up subscriptions for all markers
  useEffect(() => {
    const subscriptions: any[] = [];

    // Get all markers from the lane
    if (videoViewerRef?.current) {
      const lane = videoViewerRef.current.getMarkerLane();
      if (lane) {
        markerRefsMap.current.forEach((periodMarker, id) => {
          try {
            const subscription = periodMarker.onChange$.subscribe({
              next: (event) => {
                // Skip processing if this marker is being reset
                if (isResettingMarker.current.has(id)) {
                  return;
                }

                setMarkers((prevMarkers) => {
                  const updatedMarkers = prevMarkers.map((marker) =>
                    marker.id === id
                      ? {
                          ...marker,
                          timeObservation: {
                            start: event.timeObservation.start,
                            end: event.timeObservation.end,
                          },
                        }
                      : marker
                  );

                  // If this is a semantic marker and we have an assetId, save the modification
                  const changedMarker = updatedMarkers.find((m) => m.id === id);
                  if (changedMarker?.type === "semantic" && assetId) {
                    const currentModifications = loadSemanticModificationsFromStorage(assetId);
                    const newModifications = {
                      ...currentModifications,
                      [id]: {
                        timeObservation: {
                          start: event.timeObservation.start,
                          end: event.timeObservation.end,
                        },
                      },
                    };
                    saveSemanticModificationsToStorage(assetId, newModifications);
                    setSemanticModifications(newModifications);
                  }

                  return updatedMarkers;
                });
              },
              error: (error) => {
                console.error("Subscription error for marker", id, error);
              },
            });
            subscriptions.push(subscription);
          } catch (error) {
            console.error(`Failed to subscribe to marker ${id}:`, error);
          }
        });
      } else {
        // Marker lane not initialized yet — subscriptions will be set up on next render
      }
    } else {
      console.warn("No videoViewerRef available for subscriptions");
    }

    // Cleanup subscriptions
    return () => {
      subscriptions.forEach((sub) => {
        try {
          if (sub && !sub.closed) {
            sub.unsubscribe();
          }
        } catch (error) {
          console.warn("Error unsubscribing from marker subscription:", error);
        }
      });
    };
  }, [videoViewerRef, setMarkers, assetId, markers.length]);

  // Save marker names to localStorage when they change
  useEffect(() => {
    if (!assetId) return;

    const userMarkers = markers.filter((m) => m.type === "user");
    if (userMarkers.length > 0) {
      // Update marker names from markerNames state
      const markersWithNames = userMarkers.map((marker) => ({
        ...marker,
        name: markerNames[marker.id] || marker.name,
      }));

      saveUserMarkersToStorage(assetId, markersWithNames);
    }
  }, [markerNames, assetId, markers]);

  const deleteMarker = (markerId: string) => {
    if (!videoViewerRef?.current) return;

    try {
      const lane = videoViewerRef.current.getMarkerLane();
      if (!lane) {
        console.warn("Marker lane is not available");
        return;
      }

      // Get the marker reference
      const markerRef = markerRefsMap.current.get(markerId);
      if (markerRef) {
        // Remove from timeline
        lane.removeMarker(markerId);

        // Remove from markerRefsMap
        markerRefsMap.current.delete(markerId);

        // Remove from markerNames first
        setMarkerNames((prev) => {
          const newNames = { ...prev };
          delete newNames[markerId];
          return newNames;
        });

        // Remove from markers state and update localStorage
        setMarkers((prevMarkers) => {
          const updatedMarkers = prevMarkers.filter((marker) => marker.id !== markerId);

          // Update localStorage after deletion
          if (assetId) {
            const remainingUserMarkers = updatedMarkers.filter((m) => m.type === "user");

            if (remainingUserMarkers.length === 0) {
              // If no user markers left, clear storage
              clearMarkersFromStorage(assetId);
            } else {
              // Save remaining user markers with current names
              const markersWithCurrentNames = remainingUserMarkers.map((marker) => ({
                ...marker,
                name: markerNames[marker.id] || marker.name,
              }));
              saveUserMarkersToStorage(assetId, markersWithCurrentNames);
            }
          }

          return updatedMarkers;
        });
      }
    } catch (error) {
      console.error("Error deleting marker:", error);
    }
  };

  // Function to reset a specific semantic marker to original values
  const resetSemanticMarker = (markerId: string) => {
    if (!assetId || !videoViewerRef?.current) return;

    try {
      // Find the original clip data for this marker
      const marker = markers.find((m) => m.id === markerId && m.type === "semantic");
      if (!marker) return;

      // Find the original clip from asset.clips
      const originalClip = asset?.clips?.find((clip) => {
        // Handle both timecode and time formats safely
        const startTime = clip.start_time || clip.start_timecode;
        const endTime = clip.end_time || clip.end_timecode;

        if (!startTime || !endTime) {
          return false;
        }

        const clipId = `clip_${startTime}_${endTime}`;
        const startTimeStr = startTime.toString();

        return markerId.includes(clipId) || markerId.includes(startTimeStr);
      });

      if (!originalClip) {
        console.warn("Could not find original clip for marker:", markerId);
        return;
      }

      // Calculate original time observation - handle both timecode formats
      const startTime = originalClip.start_time || originalClip.start_timecode;
      const endTime = originalClip.end_time || originalClip.end_timecode;

      if (!startTime || !endTime) {
        console.warn("Could not find valid start/end time for clip:", originalClip);
        return;
      }

      const startSeconds = timecodeToSeconds(startTime);
      const endSeconds = timecodeToSeconds(endTime);

      // Remove this marker's modification from localStorage
      const storedModifications = loadSemanticModificationsFromStorage(assetId);

      if (storedModifications[markerId]) {
        const updatedModifications = { ...storedModifications };
        delete updatedModifications[markerId];
        saveSemanticModificationsToStorage(assetId, updatedModifications);
        setSemanticModifications(updatedModifications);
      } else {
        // Force update the state anyway to ensure consistency
        setSemanticModifications(storedModifications);
      }

      // Update the marker in timeline
      const lane = videoViewerRef.current.getMarkerLane();
      const markerRef = markerRefsMap.current.get(markerId);
      if (lane && markerRef) {
        // Set flag to prevent subscription from firing during reset
        isResettingMarker.current.add(markerId);

        // Update the timeline marker position
        markerRef.timeObservation = {
          start: startSeconds,
          end: endSeconds,
        };

        // Clear flag after a short delay to allow the change to propagate
        setTimeout(() => {
          isResettingMarker.current.delete(markerId);
        }, 100);
      }

      // Update the marker in state
      setMarkers((prevMarkers) =>
        prevMarkers.map((m) =>
          m.id === markerId
            ? {
                ...m,
                timeObservation: {
                  start: startSeconds,
                  end: endSeconds,
                },
              }
            : m
        )
      );
    } catch (error) {
      console.error("Error resetting semantic marker:", error);
    }
  };

  // Function to update marker time (start or end) for both user and semantic markers
  const updateMarkerTime = (markerId: string, field: "start" | "end", newTimeSeconds: number) => {
    if (!videoViewerRef?.current || !assetId) {
      console.warn("Missing videoViewerRef or assetId:", {
        videoViewerRef: !!videoViewerRef?.current,
        assetId,
      });
      return;
    }

    try {
      const lane = videoViewerRef.current.getMarkerLane();
      if (!lane) {
        console.warn("Marker lane is not available");
        return;
      }

      // Find the marker in our state
      const marker = markers.find((m) => m.id === markerId);
      if (!marker) {
        console.warn(
          "Marker not found:",
          markerId,
          "Available markers:",
          markers.map((m) => m.id)
        );
        return;
      }

      // Get the marker reference from timeline
      const markerRef = markerRefsMap.current.get(markerId);
      if (!markerRef) {
        console.warn(
          "Marker reference not found:",
          markerId,
          "Available refs:",
          Array.from(markerRefsMap.current.keys())
        );
        return;
      }

      // Calculate new time observation
      const currentTimeObservation = marker.timeObservation;
      const newTimeObservation = {
        start: field === "start" ? newTimeSeconds : currentTimeObservation.start,
        end: field === "end" ? newTimeSeconds : currentTimeObservation.end,
      };

      // Validate that start < end
      if (newTimeObservation.start >= newTimeObservation.end) {
        console.warn("Invalid time range: start must be less than end", newTimeObservation);
        return;
      }

      // Update the marker in the timeline
      markerRef.timeObservation = newTimeObservation;

      // Update the marker in our state
      setMarkers((prevMarkers) => {
        const updatedMarkers = prevMarkers.map((m) =>
          m.id === markerId ? { ...m, timeObservation: newTimeObservation } : m
        );
        return updatedMarkers;
      });

      // Handle persistence based on marker type
      if (marker.type === "user") {
        // For user markers, update localStorage
        const userMarkers = markers.filter((m) => m.type === "user");
        const updatedUserMarkers = userMarkers.map((m) =>
          m.id === markerId
            ? {
                ...m,
                timeObservation: newTimeObservation,
                name: markerNames[m.id] || m.name,
              }
            : { ...m, name: markerNames[m.id] || m.name }
        );
        saveUserMarkersToStorage(assetId, updatedUserMarkers);
      } else if (marker.type === "semantic") {
        // For semantic markers, track as modification
        const currentModifications = loadSemanticModificationsFromStorage(assetId);
        const newModifications = {
          ...currentModifications,
          [markerId]: {
            ...currentModifications[markerId],
            timeObservation: newTimeObservation,
          },
        };
        saveSemanticModificationsToStorage(assetId, newModifications);
        setSemanticModifications(newModifications);
      }
    } catch (error) {
      console.error("Error updating marker time:", error);
    }
  };

  const addMarker = () => {
    if (!videoViewerRef?.current) return;

    try {
      const lane = videoViewerRef.current.getMarkerLane();
      if (!lane) {
        console.warn("Marker lane is not available");
        return;
      }

      const currentTime = videoViewerRef.current.getCurrentTime();
      // Generate a unique ID based on timestamp to ensure uniqueness
      const newId = `marker_${Date.now()}_${Math.floor(Math.random() * 1000)}`;

      const periodMarker = new PeriodMarker({
        timeObservation: {
          start: currentTime,
          end: currentTime + 5,
        },
        editable: true,
        id: newId,
        style: {
          ...PERIOD_MARKER_STYLE,
          color: randomHexColor(),
        },
      });

      // Store the marker reference
      markerRefsMap.current.set(newId, periodMarker);

      // Note: Subscription will be handled by the useEffect hook
      // to avoid duplicate subscriptions and ObjectUnsubscribedError

      lane.addMarker(periodMarker);

      // Use the same default name format, counting only user markers
      const userMarkerCount = markers.filter((m) => m.type === "user").length;
      const defaultName = `Marker ${userMarkerCount + 1}`;

      // Add default name for the new marker
      setMarkerNames((prev) => ({
        ...prev,
        [newId]: defaultName,
      }));

      setMarkers((prev) => [
        ...prev,
        {
          id: newId,
          name: defaultName,
          timeObservation: {
            start: currentTime,
            end: currentTime + 5,
          },
          style: {
            color: periodMarker.style.color,
          },
          type: "user" as const,
        },
      ]);
    } catch (error) {
      console.error("Error adding marker:", error);
    }
  };

  // Helper function to convert timecode to seconds using actual asset frame rate
  const timecodeToSeconds = (timecode: string): number => {
    // Split the timecode into components
    const [hours, minutes, seconds, frames] = timecode.split(":").map(Number);

    // Extract frame rate from asset metadata
    let framesPerSecond = 25; // Default fallback

    try {
      // Try to get frame rate from video metadata
      const videoMetadata = asset?.Metadata?.EmbeddedMetadata?.video;
      if (videoMetadata && Array.isArray(videoMetadata) && videoMetadata[0]) {
        const frameRate = videoMetadata[0].FrameRate;
        if (frameRate && typeof frameRate === "string") {
          framesPerSecond = parseFloat(frameRate);
        } else if (frameRate && typeof frameRate === "number") {
          framesPerSecond = frameRate;
        }
      }

      // Also try general metadata as fallback
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
    } catch (error) {
      console.warn("Could not extract frame rate from asset metadata, using default 25 FPS", error);
    }

    // Convert to seconds
    return hours * 3600 + minutes * 60 + seconds + frames / framesPerSecond;
  };

  // Helper function to convert score threshold to human-friendly confidence label
  const getConfidenceLabel = (threshold: number): string => {
    if (threshold >= 0.9) return "Very High";
    if (threshold >= 0.7) return "High";
    if (threshold >= 0.5) return "Medium";
    if (threshold >= 0.3) return "Low";
    return "Very Low";
  };

  // Function to update timeline marker visibility based on threshold
  const updateTimelineMarkerVisibility = useCallback(
    (newThreshold: number) => {
      if (!videoViewerRef?.current) return;

      try {
        const lane = videoViewerRef.current.getMarkerLane();
        if (!lane) {
          console.warn("Marker lane is not available for visibility update");
          return;
        }

        // Iterate through all markers and show/hide based on threshold
        markers.forEach((marker) => {
          const markerRef = markerRefsMap.current.get(marker.id);
          if (!markerRef) {
            console.warn(`❌ No marker reference found for ${marker.id}`);
            console.warn(`Available marker refs:`, Array.from(markerRefsMap.current.keys()));
            return;
          }

          // Always show user markers
          if (marker.type === "user") {
            // Ensure user markers are visible (add if not already added)
            try {
              const existingMarkers = lane.getMarkers();
              if (!existingMarkers.some((m) => m.id === marker.id)) {
                lane.addMarker(markerRef);
              }
            } catch (error) {
              // Marker might already be added, which is fine
            }
            return;
          }

          // For semantic markers, check score threshold
          const shouldShow = (marker.score || 0) >= newThreshold;

          if (shouldShow) {
            // Show marker by adding it to the lane
            try {
              const existingMarkers = lane.getMarkers();
              if (!existingMarkers.some((m) => m.id === marker.id)) {
                lane.addMarker(markerRef);
              }
            } catch (error) {
              // Marker might already be added, which is fine
            }
          } else {
            // Hide marker by removing it from the lane
            try {
              lane.removeMarker(marker.id);
            } catch (error) {
              // Marker might already be removed, which is fine
            }
          }
        });
      } catch (error) {
        console.error("Error updating timeline marker visibility:", error);
      }
    },
    [videoViewerRef, markers]
  );
  // Retry mechanism for marker creation
  const createMarkersWithRetry = useCallback(
    (retryCount = 0) => {
      const maxRetries = 50;
      const retryDelay = 100; // 100ms — fast poll instead of 1s

      try {
        const lane = videoViewerRef.current?.getMarkerLane();
        if (!lane) {
          if (retryCount < maxRetries) {
            markerRetryTimeoutRef.current = setTimeout(() => {
              createMarkersWithRetry(retryCount + 1);
            }, retryDelay);
            return;
          } else {
            console.error("Failed to get marker lane after maximum retries");
            setIsLoadingSemanticMarkers(false);
            return;
          }
        }

        // Get all visual-text clips first

        const allVisualTextClips = asset.clips
          .filter((clip) => {
            // Support embedding types from different providers:
            // - Marengo 2.7: "visual-text"
            // - Marengo 3.0: "visual"
            // - TwelveLabs Bedrock: embedding_scope === "clip"
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

        //   "All visual-text clips:",
        //   allVisualTextClips.map((c) => ({
        //     score: c.score,
        //     embedding_option: c.embedding_option,
        //     embedding_scope: c.embedding_scope,
        //     start: c.start_timecode || c.start_time,
        //     end: c.end_timecode || c.end_time,
        //   })),
        // );

        // Create markers for all clips (filtering will be done at render time)
        const selectedClips = allVisualTextClips;

        selectedClips.forEach((clip, index) => {
          // Handle both timecode formats - fallback to start_time if start_timecode is not available
          const startTime = clip.start_timecode || clip.start_time;
          const endTime = clip.end_timecode || clip.end_time;

          // Convert timecodes to seconds
          const startSeconds = timecodeToSeconds(startTime);
          const endSeconds = timecodeToSeconds(endTime);

          // Extract score from clip if available
          const clipScore = clip.score !== undefined ? clip.score : null;

          // Generate a consistent ID based on timecode and index to ensure uniqueness
          const newId = `clip_${startTime}_${endTime}_${index}`;

          // Use confidence-based color for semantic markers
          // Pass model_version for model-aware thresholds (3.0 vs 2.7)
          const markerColor = getMarkerColorByConfidence(
            clipScore ?? undefined,
            clip.model_version
          );

          const periodMarker = new PeriodMarker({
            timeObservation: {
              start: startSeconds,
              end: endSeconds,
            },
            editable: true,
            id: newId,
            style: {
              ...PERIOD_MARKER_STYLE,
              color: markerColor,
            },
          });

          markerRefsMap.current.set(newId, periodMarker);

          // Note: Subscription will be handled by the useEffect hook
          // to avoid duplicate subscriptions and ObjectUnsubscribedError

          lane.addMarker(periodMarker);

          // Use searchTerm for marker names if available, otherwise use default
          const defaultName = searchTerm ? searchTerm : `Marker ${newId}`;

          // Add default name for clip markers
          setMarkerNames((prev) => ({
            ...prev,
            [newId]: defaultName,
          }));

          setMarkers((prev) => [
            ...prev,
            {
              id: newId,
              name: defaultName,
              timeObservation: {
                start: startSeconds,
                end: endSeconds,
              },
              style: {
                color: markerColor,
              },
              score: clipScore !== null ? clipScore : undefined, // Add score only if it exists
              type: "semantic" as const,
              model_version: clip.model_version, // Pass model version for model-aware thresholds
            },
          ]);
        });

        // Mark that we've created markers from clips and stop loading
        setClipsMarkersCreated(true);
        setIsLoadingSemanticMarkers(false);

        // Load and apply stored semantic modifications
        if (assetId) {
          const storedModifications = loadSemanticModificationsFromStorage(assetId);
          if (storedModifications && Object.keys(storedModifications).length > 0) {
            // Apply modifications to both state and timeline markers
            setMarkers((prevMarkers) =>
              prevMarkers.map((marker) => {
                if (marker.type === "semantic" && storedModifications[marker.id]) {
                  const modification = storedModifications[marker.id];
                  const updatedMarker = {
                    ...marker,
                    ...(modification.timeObservation && {
                      timeObservation: modification.timeObservation,
                    }),
                  };

                  // Also update the timeline marker
                  const markerRef = markerRefsMap.current.get(marker.id);
                  if (markerRef && modification.timeObservation) {
                    markerRef.timeObservation = modification.timeObservation;
                  }

                  return updatedMarker;
                }
                return marker;
              })
            );
          }
        }

        // Apply initial visibility based on current threshold
        setTimeout(() => {
          updateTimelineMarkerVisibility(scoreThreshold);
        }, 100); // Small delay to ensure markers are fully added

        // Force subscription setup for newly created semantic markers
        setTimeout(() => {
          // This will trigger the subscription useEffect by updating markers length
          setMarkers((prevMarkers) => [...prevMarkers]);
        }, 200); // Slightly longer delay to ensure everything is settled
      } catch (error) {
        console.error("Error creating markers from clips:", error);
        if (retryCount < maxRetries) {
          markerRetryTimeoutRef.current = setTimeout(() => {
            createMarkersWithRetry(retryCount + 1);
          }, retryDelay);
        }
      }
    },
    [
      asset?.clips,
      videoViewerRef,
      timecodeToSeconds,
      setMarkers,
      setMarkerNames,
      setClipsMarkersCreated,
      searchTerm,
      scoreThreshold,
      updateTimelineMarkerVisibility,
    ]
  );

  useEffect(() => {
    // Debug logging for asset and clips

    if (!videoViewerRef?.current || !asset?.clips || !Array.isArray(asset.clips)) {
      // console.warn("Skipping marker creation - missing requirements:", {
      //   hasVideoViewerRef: !!videoViewerRef?.current,
      //   hasClips: !!asset?.clips,
      //   isClipsArray: Array.isArray(asset?.clips),
      // });
      return;
    }

    // Skip if markers have already been created from clips
    if (clipsMarkersCreated) {
      return;
    }

    // Set loading state and start marker creation immediately with fast polling
    setIsLoadingSemanticMarkers(true);
    // Start immediately — createMarkersWithRetry will fast-poll (100ms) for the lane
    createMarkersWithRetry();

    return () => {
      // Clear any in-progress retry timeouts
      if (markerRetryTimeoutRef.current) {
        clearTimeout(markerRetryTimeoutRef.current);
        markerRetryTimeoutRef.current = null;
      }
    };
  }, [asset?.clips, videoViewerRef, clipsMarkersCreated, createMarkersWithRetry, scoreThreshold]);

  // Function to update marker visibility in timeline
  const updateMarkerVisibility = useCallback(() => {
    if (!videoViewerRef?.current) return;

    const lane = videoViewerRef.current.getMarkerLane();
    if (!lane) return;

    markers.forEach((marker) => {
      let markerRef = markerRefsMap.current.get(marker.id);

      const shouldShow =
        (marker.type === "user" && showUserMarkers) ||
        (marker.type === "semantic" &&
          showSemanticMarkers &&
          (marker.score || 0) >= scoreThreshold);

      if (shouldShow) {
        // Create marker reference if it doesn't exist
        if (!markerRef) {
          // Determine the color - always use score from payload for semantic markers
          let markerColor;
          if (marker.type === "user") {
            markerColor = marker.style?.color || theme.palette.primary.main;
          } else {
            // For semantic markers, always use confidence-based color from the clip's score
            // This ensures colors are based on the actual score from the payload, not the filter threshold
            // Pass model_version for model-aware thresholds (3.0 vs 2.7)
            markerColor = getMarkerColorByConfidence(marker.score, marker.model_version);
          }

          markerRef = new PeriodMarker({
            id: marker.id,
            timeObservation: marker.timeObservation,
            editable: true,
            style: {
              ...PERIOD_MARKER_STYLE,
              color: markerColor,
            },
          });
          markerRefsMap.current.set(marker.id, markerRef);
        }

        // Add marker to timeline if not already there
        const existingMarkers = lane.getMarkers();
        if (!existingMarkers.some((m) => m.id === marker.id)) {
          lane.addMarker(markerRef);
        }
      } else if (markerRef) {
        // Remove marker from timeline
        lane.removeMarker(marker.id);
        // Remove from markerRefsMap to prevent subscription cleanup issues
        markerRefsMap.current.delete(marker.id);
      }
    });
  }, [markers, showUserMarkers, showSemanticMarkers, scoreThreshold, videoViewerRef]);

  // Update timeline visibility when show/hide states change
  useEffect(() => {
    updateMarkerVisibility();
  }, [updateMarkerVisibility]);

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
            transition: "all 0.15s ease",
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
            transition: "all 0.15s ease",
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
            transition: "all 0.15s ease",
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
                    if (videoViewerRef?.current?.seek) {
                      videoViewerRef.current.seek(marker.timeObservation.start);
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
                    transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
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
                          setMarkers((prevMarkers) =>
                            prevMarkers.map((m) =>
                              m.id === marker.id ? { ...m, name: newName } : m
                            )
                          );
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
                        videoViewerRef={videoViewerRef}
                      />
                      <Typography variant="caption" sx={{ color: "text.secondary" }}>
                        {" - "}
                      </Typography>
                      <EditableTimecode
                        value={marker.timeObservation.end}
                        markerId={marker.id}
                        field="end"
                        onUpdate={updateMarkerTime}
                        videoViewerRef={videoViewerRef}
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
                      transition: "all 0.15s ease",
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
                  // Save to localStorage for persistence
                  saveConfidenceLevelToStorage(newThreshold);
                  updateTimelineMarkerVisibility(newThreshold);
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
                    if (videoViewerRef?.current?.seek) {
                      videoViewerRef.current.seek(marker.timeObservation.start);
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
                    transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
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
                          videoViewerRef={videoViewerRef}
                        />
                        <Typography variant="caption" sx={{ color: "text.secondary" }}>
                          {" - "}
                        </Typography>
                        <EditableTimecode
                          value={marker.timeObservation.end}
                          markerId={marker.id}
                          field="end"
                          onUpdate={updateMarkerTime}
                          videoViewerRef={videoViewerRef}
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
                  {(() => {
                    const shouldShow = assetId && semanticModifications[marker.id];
                    return shouldShow;
                  })() && (
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
                          transition: "all 0.15s ease",
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
          transition: "all 0.2s ease",
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
          transition: "all 0.2s ease",
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
  const { videoViewerRef, versions = [], assetId, asset, searchTerm } = props;
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
                  transition: "all 0.15s ease",
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
                videoViewerRef={videoViewerRef}
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
