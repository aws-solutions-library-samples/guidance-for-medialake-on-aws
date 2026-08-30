import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
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
  Menu,
  MenuItem,
} from "@mui/material";
import { useSnackbar } from "notistack";
import { RightSidebar } from "../common/RightSidebar";
import { useGetPipelines } from "../../features/pipelines/api/pipelinesController";
import { PipelinesService } from "../../features/pipelines/api/pipelinesService";
import { useFeatureFlag } from "../../contexts/FeatureFlagsContext";

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
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import ArrowDropDownIcon from "@mui/icons-material/ArrowDropDown";
import AspectRatioIcon from "@mui/icons-material/AspectRatio";
import { getMarkerColorByConfidence, randomHexColor, stableColorForId } from "../common/utils";
import type { UseDetailPlayerResult } from "../player/useDetailPlayer";
import type { DetailMarker } from "../player/markerTracks";
import { getPlayerCurrentTime } from "../player/playerTimeStore";
import {
  formatDuration,
  formatSmpte,
  formatTimeRange,
  getAssetFrameRate,
  parseTimecode,
} from "@/utils/timecode";

/**
 * Marker display info used by the sidebar UI.
 *
 * Extends the player's `DetailMarker` read model with display-only fields. The
 * marker itself lives on a `MarkerTrack`; this is a projection, so nothing here
 * is authoritative.
 */
interface MarkerInfo extends DetailMarker {
  name?: string;
  style: { color: string };
  createdAt?: number;
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
//
// Both directions delegate to the shared `utils/timecode` module. The local
// implementations they replace hardcoded 30fps, while the rest of the app -- the
// player load options, the keyboard-shortcut shuttle, `markerHelpers` -- assumed
// 25, so a marker's displayed frame number disagreed with the frame the player
// actually seeked to. The frame rate is now the asset's real one where the
// metadata reports it.

// Editable Timecode Component
const EditableTimecode: React.FC<{
  value: number;
  markerId: string;
  field: "start" | "end";
  /** The asset's frame rate, when known. Falls back to DEFAULT_FPS. */
  fps?: number;
  onUpdate: (markerId: string, field: "start" | "end", newTimeSeconds: number) => void;
}> = ({ value, markerId, field, fps, onUpdate }) => {
  const { t } = useTranslation();
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState("");

  const handleStartEdit = () => {
    setEditValue(formatSmpte(value, fps) ?? "");
    setIsEditing(true);
  };

  const handleSaveEdit = () => {
    const newTimeSeconds = parseTimecode(editValue, fps);

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
      {formatSmpte(value, fps)}
    </Typography>
  );
};

interface AssetSidebarProps {
  versions?: any[];
  comments?: any[];
  onAddComment?: (comment: string) => void;
  playerMarkers?: UseDetailPlayerResult | null;
  isMarkerReady?: boolean;
  seek?: (time: number) => void;
  /**
   * Seconds of the clip the user arrived from (the `?t=` deep link). The marker
   * covering this time is emphasised and scrolled into view, so a semantic result
   * click lands on the matching entry instead of the top of a 38-item list.
   */
  focusTime?: number;
  assetId?: string;
  asset?: any;
  assetType?: string;
  searchTerm?: string;
  // Versions-tab "View" switcher: flips the main player between playable
  // renditions (proxy / smartcrop). Provided by the media detail page.
  onViewVersion?: (version: any) => void;
  viewedVersionId?: string;
}

interface AssetVersionProps {
  versions: any[];
  onViewVersion?: (version: any) => void;
  viewedVersionId?: string;
}

// Parse a smartcrop Segment string ("HH:MM:SS:FF/HH:MM:SS:FF") into a compact
// display like "00:02 – 00:08 · 6s".
//
// Frames are deliberately dropped: this is a duration summary on a version card,
// where frame precision is noise. The range and the duration both come from the
// shared formatters so the range matches every other clip surface.
const formatSegmentInfo = (segment?: string): string | null => {
  if (!segment || typeof segment !== "string" || !segment.includes("/")) return null;

  const [startTc, endTc] = segment.split("/");
  const start = parseTimecode(startTc?.replace(/;/g, ":"));
  const end = parseTimecode(endTc?.replace(/;/g, ":"));
  if (start === null || end === null || end <= start) return null;

  const range = formatTimeRange(start, end);
  const duration = formatDuration(end - start);
  if (!range) return null;

  return duration ? `${range} \u00b7 ${duration}` : range;
};

interface AssetMarkersProps {
  onMarkerAdd?: () => void;
  playerMarkers?: UseDetailPlayerResult | null;
  isMarkerReady?: boolean;
  seek?: (time: number) => void;
  /** See `AssetSidebarProps.focusTime`. */
  focusTime?: number;
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
const AssetVersions: React.FC<AssetVersionProps> = ({
  versions = [],
  onViewVersion,
  viewedVersionId,
}) => {
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
                {/* Smartcrop details: target aspect ratio + output resolution */}
                {(version.aspectRatio || version.resolution) && (
                  <Typography variant="body2" color="text.secondary" sx={{ fontSize: "0.8rem" }}>
                    <strong>{t("assetSidebar.cropSize", "Crop:")}</strong>{" "}
                    {[
                      version.aspectRatio,
                      version.resolution?.Width && version.resolution?.Height
                        ? `${version.resolution.Width}\u00d7${version.resolution.Height}`
                        : null,
                    ]
                      .filter(Boolean)
                      .join(" \u00b7 ")}
                  </Typography>
                )}
                {/* Segment range + duration for segment-based smartcrops;
                    whole-asset smartcrops are marked full length. */}
                {version.type?.toLowerCase() === "smartcrop" && (
                  <Typography variant="body2" color="text.secondary" sx={{ fontSize: "0.8rem" }}>
                    <strong>{t("assetSidebar.segmentDuration", "Duration:")}</strong>{" "}
                    {formatSegmentInfo(version.segment) ||
                      t("assetSidebar.fullLength", "Full length")}
                  </Typography>
                )}
                <Box sx={{ display: "flex", mt: 1.5 }}>
                  {/* View: flip the main player to this rendition (proxy or
                      smartcrop). Click again to return to the default proxy. */}
                  {onViewVersion &&
                    version.url &&
                    !version.type?.toLowerCase().includes("thumb") &&
                    version.type?.toLowerCase() !== "original" && (
                      <Button
                        variant={viewedVersionId === version.id ? "contained" : "outlined"}
                        size="small"
                        color="secondary"
                        sx={{
                          mr: 1,
                          textTransform: "none",
                          borderRadius: "8px",
                          fontSize: "0.775rem",
                          fontWeight: 500,
                        }}
                        onClick={() => onViewVersion(version)}
                        startIcon={<PlayCircleOutlineIcon sx={{ fontSize: 16 }} />}
                        data-testid="view-version-button"
                      >
                        {viewedVersionId === version.id
                          ? t("assetSidebar.viewing", "Viewing")
                          : t("assetSidebar.view", "View")}
                      </Button>
                    )}
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

/**
 * Per-segment workflow menu shown on each marker card. Lists pipelines the API
 * flagged with `per_segment_execution` (derived server-side from the manual
 * trigger node's "Per Segment Execution" parameter) and runs the selected one
 * against this segment's time range (passed as start_time/end_time params).
 * Renders nothing when the feature is unavailable or there are no eligible
 * pipelines. Gated by the caller via the segment-workflows feature flag.
 */
const SegmentWorkflowMenu: React.FC<{
  pipelines: any[];
  assetId?: string;
  startTime: number;
  endTime: number;
}> = ({ pipelines, assetId, startTime, endTime }) => {
  const { t } = useTranslation();
  const { enqueueSnackbar } = useSnackbar();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [runningId, setRunningId] = useState<string | null>(null);

  if (!assetId || pipelines.length === 0) return null;

  const runPipeline = async (pipeline: any) => {
    setRunningId(pipeline.id);
    try {
      const response = await PipelinesService.triggerPipeline(pipeline.id, [
        {
          inventory_id: assetId,
          params: { start_time: startTime, end_time: endTime },
        },
      ]);
      if ((response?.successful_executions ?? 0) > 0) {
        enqueueSnackbar(
          t("segmentWorkflows.started", {
            defaultValue: 'Started "{{name}}" on segment',
            name: pipeline.name,
          }),
          { variant: "success" }
        );
      } else {
        enqueueSnackbar(
          response?.message ||
            t("segmentWorkflows.failed", { defaultValue: "Failed to start workflow" }),
          { variant: "error" }
        );
      }
    } catch (error: any) {
      const status = error?.response?.status;
      enqueueSnackbar(
        status === 403
          ? t("segmentWorkflows.forbidden", {
              defaultValue: "You don't have permission to run this workflow",
            })
          : t("segmentWorkflows.failed", { defaultValue: "Failed to start workflow" }),
        { variant: "error" }
      );
    } finally {
      setRunningId(null);
      setAnchorEl(null);
    }
  };

  return (
    <>
      <Tooltip
        title={t("segmentWorkflows.menuTooltip", {
          defaultValue: "Run a workflow on this segment",
        })}
      >
        <Button
          size="small"
          onClick={(e) => {
            e.stopPropagation();
            setAnchorEl(e.currentTarget);
          }}
          startIcon={<PlayArrowIcon sx={{ fontSize: 14 }} />}
          endIcon={<ArrowDropDownIcon sx={{ fontSize: 14 }} />}
          sx={{
            px: 0.75,
            py: 0,
            height: 22,
            minWidth: 0,
            flexShrink: 0,
            textTransform: "none",
            fontSize: "0.7rem",
            fontWeight: 600,
            lineHeight: 1,
            color: "text.secondary",
            borderRadius: "6px",
            "& .MuiButton-startIcon": { mr: 0.25, ml: 0 },
            "& .MuiButton-endIcon": { ml: 0, mr: -0.25 },
            "&:hover": {
              color: "primary.main",
              bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1),
            },
          }}
          aria-label={t("segmentWorkflows.menuTooltip", {
            defaultValue: "Run a workflow on this segment",
          })}
          aria-haspopup="menu"
        >
          {t("segmentWorkflows.runButton", { defaultValue: "Run" })}
        </Button>
      </Tooltip>
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={(e: React.SyntheticEvent) => {
          e.stopPropagation?.();
          setAnchorEl(null);
        }}
        onClick={(e) => e.stopPropagation()}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        slotProps={{
          paper: {
            elevation: 3,
            sx: {
              minWidth: 200,
              borderRadius: 2,
              border: "1px solid",
              borderColor: "divider",
              "& .MuiMenuItem-root": { fontSize: "0.82rem", py: 0.75, gap: 1 },
            },
          },
        }}
      >
        <MenuItem disabled sx={{ opacity: 1, py: 0.5 }}>
          <Typography
            variant="caption"
            sx={{
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
              color: "text.secondary",
            }}
          >
            {t("segmentWorkflows.header", { defaultValue: "Run on segment" })}
          </Typography>
        </MenuItem>
        {pipelines.map((pipeline) => (
          <MenuItem
            key={pipeline.id}
            onClick={() => runPipeline(pipeline)}
            disabled={runningId !== null}
          >
            <ListItemIcon>
              {runningId === pipeline.id ? (
                <CircularProgress size={16} />
              ) : (
                <AspectRatioIcon fontSize="small" />
              )}
            </ListItemIcon>
            <ListItemText>{pipeline.name}</ListItemText>
          </MenuItem>
        ))}
      </Menu>
    </>
  );
};

// Markers content component
const AssetMarkers: React.FC<AssetMarkersProps> = ({
  markers,
  setMarkers,
  playerMarkers,
  isMarkerReady,
  seek,
  focusTime,
  asset,
  assetId,

  searchTerm,
  clipsMarkersCreated,
  setClipsMarkersCreated,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const { enqueueSnackbar } = useSnackbar();

  // Per-segment workflows: list pipelines the API flagged for per-segment
  // execution so each marker card can launch one against its own time range.
  // The list endpoint omits the node graph, so this flag has to come from the
  // backend -- parsing `definition` here silently matched nothing.
  // Gated behind a feature flag; the pipelines query is skipped when disabled.
  const segmentWorkflowsEnabled = useFeatureFlag("segment-workflows-enabled", false);
  const { data: segmentPipelinesData } = useGetPipelines({
    enabled: segmentWorkflowsEnabled,
  });
  const perSegmentPipelines = useMemo(() => {
    if (!segmentWorkflowsEnabled || !segmentPipelinesData?.data?.s) return [];
    // The API only sets the flag on manual-trigger pipelines, so no separate
    // trigger-type check is needed here.
    return segmentPipelinesData.data.s.filter(
      (pipeline: any) => pipeline.per_segment_execution === true
    );
  }, [segmentWorkflowsEnabled, segmentPipelinesData]);

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

  // Project the player's marker tracks into the sidebar's display model.
  //
  // The tracks are the source of truth, so this derives rather than stores: it
  // runs whenever either track changes, including for markers created by the `I`
  // shortcut or moved by dragging a marker bar. The implementation this replaces
  // only re-projected on the sidebar's own writes, so those two paths were
  // invisible here until something else forced a refresh.
  const markerNamesState = markerNames;
  useEffect(() => {
    if (!playerMarkers?.isReady) return;

    const names = markerNamesRef.current;
    const project = (marker: DetailMarker): MarkerInfo => ({
      ...marker,
      name: names[marker.id] || marker.label,
      style: {
        color:
          marker.color ??
          (marker.kind === "semantic"
            ? getMarkerColorByConfidence(marker.score, marker.modelVersion)
            : // A user marker always carries a colour from creation. This branch is
              // a last resort, and uses a stable hash of the id rather than
              // `randomHexColor()` — the old code re-randomised on every
              // projection, so such markers changed colour as you used the page.
              stableColorForId(marker.id)),
      },
    });

    setMarkers?.([
      ...playerMarkers.userMarkers.map(project),
      ...playerMarkers.semanticMarkers.map(project),
    ]);
  }, [
    playerMarkers?.isReady,
    playerMarkers?.userMarkers,
    playerMarkers?.semanticMarkers,
    markerNamesState,
    setMarkers,
  ]);

  const assetFps = useMemo(() => getAssetFrameRate(asset), [asset]);

  // The marker the user arrived at, from the `?t=` deep link.
  //
  // Containment rather than equality: `t` is the clip's start, but a rounded or
  // reformatted value should still resolve to the clip it names. Ties go to the
  // latest start, which is the innermost span when clips overlap.
  const focusedMarkerId = useMemo(() => {
    if (focusTime === undefined || !markers?.length) return null;

    const EPSILON = 0.001;
    let best: MarkerInfo | null = null;
    for (const marker of markers) {
      const covers =
        focusTime >= marker.startTime - EPSILON && focusTime <= marker.endTime + EPSILON;
      if (!covers) continue;
      if (!best || marker.startTime > best.startTime) best = marker;
    }
    return best?.id ?? null;
  }, [focusTime, markers]);

  // Bring the focused marker into view once it exists. Semantic lists run to
  // dozens of entries, so without this the deep link lands on a list scrolled to
  // the top with the relevant entry somewhere below the fold.
  const focusedMarkerRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!focusedMarkerId) return;
    focusedMarkerRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [focusedMarkerId]);

  // Helper function to convert timecode to seconds using actual asset frame rate
  const timecodeToSeconds = useCallback(
    (timecode: string): number => parseTimecode(timecode, assetFps) ?? 0,
    [assetFps]
  );

  // Publish the asset's clips onto the semantic marker track.
  //
  // The whole clip set goes on the track regardless of the confidence threshold —
  // thresholding is a rendering decision applied below. The implementation this
  // replaces removed and re-added markers on every threshold change, which reset
  // their revisions and discarded any edits.
  useEffect(() => {
    if (!playerMarkers?.isReady || !asset?.clips || !Array.isArray(asset.clips)) return;
    if (clipsMarkersCreated) return;

    const clips = asset.clips
      .filter((clip: any) => {
        const isValidEmbedding =
          clip.embedding_option === "visual-text" ||
          clip.embedding_option === "visual" ||
          clip.embedding_scope === "clip";
        const hasValidScore = clip.score !== null && clip.score !== undefined;
        const hasValidTimes =
          (clip.start_timecode || clip.start_time) && (clip.end_timecode || clip.end_time);
        return isValidEmbedding && hasValidScore && hasValidTimes;
      })
      .map((clip: any) => {
        const startTime = timecodeToSeconds(clip.start_timecode || clip.start_time);
        const endTime = timecodeToSeconds(clip.end_timecode || clip.end_time);
        return {
          startTime,
          endTime,
          label: searchTerm || "Clip",
          color: getMarkerColorByConfidence(clip.score, clip.model_version),
          score: clip.score,
          modelVersion: clip.model_version,
        };
      })
      .filter((clip: any) => clip.endTime > clip.startTime);

    playerMarkers.setSemanticMarkers(clips);
    setClipsMarkersCreated(true);
  }, [
    playerMarkers,
    asset?.clips,
    clipsMarkersCreated,
    searchTerm,
    setClipsMarkersCreated,
    timecodeToSeconds,
  ]);

  const deleteMarker = (markerId: string) => {
    playerMarkers?.removeUserMarker(markerId);
    setMarkerNames((prev) => {
      const next = { ...prev };
      delete next[markerId];
      return next;
    });
  };

  /**
   * Restore a semantic marker to the clip range the pipeline produced.
   *
   * Matching is by time proximity rather than by a reconstructed id: marker ids
   * are Omakase uuids now, so the old string-built `clip-{start}-{end}-{assetId}`
   * id no longer exists to compare against.
   */
  const resetSemanticMarker = (markerId: string) => {
    if (!playerMarkers || !asset?.clips) return;

    const marker = markers.find((m) => m.id === markerId);
    if (!marker) return;

    let best: { startTime: number; endTime: number } | null = null;
    let bestDelta = Number.POSITIVE_INFINITY;

    for (const clip of asset.clips as any[]) {
      const rawStart = clip.start_timecode || clip.start_time;
      const rawEnd = clip.end_timecode || clip.end_time;
      if (!rawStart || !rawEnd) continue;

      const startTime = timecodeToSeconds(rawStart);
      const endTime = timecodeToSeconds(rawEnd);
      if (endTime <= startTime) continue;

      const delta = Math.abs(startTime - marker.startTime);
      if (delta < bestDelta) {
        bestDelta = delta;
        best = { startTime, endTime };
      }
    }

    if (best) {
      playerMarkers.updateMarker(markerId, { startTime: best.startTime, endTime: best.endTime });
    }
  };

  const updateMarkerTime = (markerId: string, field: "start" | "end", newTimeSeconds: number) => {
    // The track rejects an inverted range, so no guard is needed here.
    playerMarkers?.updateMarker(
      markerId,
      field === "start" ? { startTime: newTimeSeconds } : { endTime: newTimeSeconds }
    );
  };

  const addMarker = () => {
    if (!playerMarkers?.isReady) return;

    const time = getPlayerCurrentTime();
    const userMarkerCount = markers.filter((m) => m.kind === "user").length;
    const defaultName = `Marker ${userMarkerCount + 1}`;

    const created = playerMarkers.addUserMarker({
      startTime: time,
      endTime: time + 5,
      label: defaultName,
      color: randomHexColor(),
    });

    if (created) {
      setMarkerNames((prev) => ({ ...prev, [created.id]: defaultName }));
    }
  };

  /**
   * The asset's real frame rate, when its metadata reports one.
   *
   * Memoized on the asset rather than lazily cached in a ref: the previous
   * version used `if (fps === 25)` as a "not found yet" sentinel, so an asset
   * genuinely shot at 25fps fell through to the general-metadata lookup.
   * `getAssetFrameRate` returns undefined for unknown instead, and also handles
   * the ffprobe rational form ("30000/1001") that the old parser produced NaN for.
   */

  // Helper function to convert score threshold to human-friendly confidence label
  const getConfidenceLabel = (threshold: number): string => {
    if (threshold >= 0.9) return "Very High";
    if (threshold >= 0.7) return "High";
    if (threshold >= 0.5) return "Medium";
    if (threshold >= 0.3) return "Low";
    return "Very Low";
  };

  const userMarkerCount = markers?.filter((m) => m.kind === "user").length || 0;
  const aiMarkerCount =
    markers?.filter((m) => m.kind === "semantic" && (m.score || 0) >= scoreThreshold).length || 0;

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
            User Markers ({markers?.filter((m) => m.kind === "user").length || 0})
          </Typography>
          {markers?.filter((m) => m.kind === "user").length === 0 ? (
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
              .filter((m) => m.kind === "user")
              .sort((a, b) => b.id.localeCompare(a.id)) // Sort by ID descending (newest first)
              .map((marker, index) => (
                <Box
                  key={marker.id}
                  ref={marker.id === focusedMarkerId ? focusedMarkerRef : undefined}
                  onClick={() => {
                    if (seek) {
                      seek(marker.startTime);
                    }
                  }}
                  sx={{
                    mt: 1,
                    p: 1.25,
                    pr: 4,
                    position: "relative",
                    bgcolor: (theme) =>
                      alpha(marker.style.color, marker.id === focusedMarkerId ? 0.14 : 0.05),
                    borderRadius: "10px",
                    border: `1px solid ${alpha(marker.style.color, marker.id === focusedMarkerId ? 0.5 : 0.15)}`,
                    borderLeft: `3px solid ${marker.style.color}`,
                    cursor: "pointer",
                    ...(marker.id === focusedMarkerId
                      ? { boxShadow: `0 0 0 2px ${alpha(marker.style.color, 0.35)}` }
                      : {}),
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
                          playerMarkers?.updateMarker(marker.id, { label: newName });
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
                        value={marker.startTime}
                        markerId={marker.id}
                        field="start"
                        fps={assetFps}
                        onUpdate={updateMarkerTime}
                      />
                      <Typography variant="caption" sx={{ color: "text.secondary" }}>
                        {" - "}
                      </Typography>
                      <EditableTimecode
                        value={marker.endTime}
                        markerId={marker.id}
                        field="end"
                        fps={assetFps}
                        onUpdate={updateMarkerTime}
                      />
                    </Box>
                  </Box>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 0.5,
                      mt: 0.5,
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{
                        color: "text.secondary",
                        fontStyle: "italic",
                        fontSize: "0.7rem",
                      }}
                    >
                      Created by {userName}
                    </Typography>
                    <SegmentWorkflowMenu
                      pipelines={perSegmentPipelines}
                      assetId={assetId}
                      startTime={marker.startTime}
                      endTime={marker.endTime}
                    />
                  </Box>
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
            {markers?.filter((m) => m.kind === "semantic" && (m.score || 0) >= scoreThreshold)
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
          ) : markers?.filter((m) => m.kind === "semantic" && (m.score || 0) >= scoreThreshold)
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
              .filter((m) => m.kind === "semantic" && (m.score || 0) >= scoreThreshold)
              .sort((a, b) => (b.score || 0) - (a.score || 0)) // Sort by score descending
              .map((marker, index) => (
                <Box
                  key={marker.id}
                  ref={marker.id === focusedMarkerId ? focusedMarkerRef : undefined}
                  onClick={() => {
                    if (seek) {
                      seek(marker.startTime);
                    }
                  }}
                  sx={{
                    mt: 1,
                    p: 1.25,
                    pr: 4, // Add padding-right to make space for reset button
                    position: "relative",
                    bgcolor: alpha(marker.style.color, marker.id === focusedMarkerId ? 0.14 : 0.05),
                    borderRadius: "10px",
                    border: `1px solid ${alpha(marker.style.color, marker.id === focusedMarkerId ? 0.5 : 0.15)}`,
                    borderLeft: `3px solid ${marker.style.color}`,
                    cursor: "pointer",
                    // The clip the user clicked through from. Emphasised so a deep
                    // link lands somewhere obvious in a long list.
                    ...(marker.id === focusedMarkerId
                      ? { boxShadow: `0 0 0 2px ${alpha(marker.style.color, 0.35)}` }
                      : {}),
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
                          value={marker.startTime}
                          markerId={marker.id}
                          field="start"
                          fps={assetFps}
                          onUpdate={updateMarkerTime}
                        />
                        <Typography variant="caption" sx={{ color: "text.secondary" }}>
                          {" - "}
                        </Typography>
                        <EditableTimecode
                          value={marker.endTime}
                          markerId={marker.id}
                          field="end"
                          fps={assetFps}
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
                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
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
                      <SegmentWorkflowMenu
                        pipelines={perSegmentPipelines}
                        assetId={assetId}
                        startTime={marker.startTime}
                        endTime={marker.endTime}
                      />
                    </Box>
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
// eslint-disable-next-line @typescript-eslint/no-unused-vars
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
// eslint-disable-next-line @typescript-eslint/no-unused-vars
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
// eslint-disable-next-line @typescript-eslint/no-unused-vars
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
  const {
    playerMarkers,
    isMarkerReady,
    seek,
    focusTime,
    versions = [],
    assetId,
    asset,
    searchTerm,
    onViewVersion,
    viewedVersionId,
  } = props;
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
                playerMarkers={playerMarkers}
                isMarkerReady={isMarkerReady}
                seek={seek}
                focusTime={focusTime}
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
                onViewVersion={onViewVersion}
                viewedVersionId={viewedVersionId}
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
